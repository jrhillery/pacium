
import json
from datetime import date, datetime, time, timedelta
from functools import cache
from pathlib import Path
from time import strptime
from typing import NamedTuple, Type, TypeVar


class CourtTime(NamedTuple):
    """Represents desired court time"""
    startTime: time
    duration: int
    DT_FORMAT = "%I:%M %p %a %b %d, %Y"
    THIRTY_MINUTES = timedelta(minutes=30)

    def strWithDate(self, dt: date) -> str:
        cDt = datetime.combine(dt, self.startTime)

        return cDt.strftime(CourtTime.DT_FORMAT)
    # end strWithDate(date)

    @cache
    def getTimeRows(self) -> list[str]:
        """Return the time portions of the schedule table CSS selectors"""
        rTime = datetime.combine(date.today(), self.startTime)
        endTime = rTime + timedelta(minutes=self.duration)
        tRows: list[str] = []

        while rTime < endTime:
            # colons need to be escaped in CSS selectors
            tRows.append(rTime.time().isoformat(timespec="minutes").replace(":", "\:"))
            rTime += CourtTime.THIRTY_MINUTES
        # end while

        return tRows
    # end getTimeRows()

    def getStartTimesForDate(self, dt: date) -> list[str]:
        """Return the start timestamp portions of the schedule table CSS selectors"""
        rTime = datetime.combine(dt, self.startTime)
        endTime = rTime + timedelta(minutes=self.duration)
        startTimes: list[str] = []

        while rTime < endTime:
            # example: Wed Aug 24 2022 09:00:00
            startTimes.append(rTime.strftime("%a %b %d %Y %H:%M:%S "))
            rTime += CourtTime.THIRTY_MINUTES
        # end while

        return startTimes
    # end getStartTimesForDate(date)

# end class CourtTime


class CourtTimes(NamedTuple):
    """Represents our court times in our preferred order"""
    timesInPreferredOrder: list[CourtTime]
    T = TypeVar("T")

    @classmethod
    def load(cls: Type[T], fileNm: Path) -> T:
        with open(fileNm, "r", encoding="utf-8") as file:

            return json.load(file, object_hook=decodeCourtTimes)
    # end load(str)

    def save(self, fileNm: Path) -> None:
        with open(fileNm, "w", encoding="utf-8") as file:
            dct = {"timesInPreferredOrder":
                   [{"startTime": ct.startTime.isoformat(timespec="minutes"),
                     "duration": ct.duration} for ct in self.timesInPreferredOrder]}
            json.dump(dct, file, ensure_ascii=False, indent=3)
    # end save(str)

    @staticmethod
    def nextDateForDay(dayOfWeekArg: str) -> date:
        """Return the next date with the specified day of week abbreviation"""
        try:
            dayOfWeekInt = strptime(dayOfWeekArg, "%a").tm_wday
        except ValueError as e:
            raise ValueError(
                f"Invalid day of week abbreviation [{dayOfWeekArg}]", *e.args) from e

        nd = date.today()
        daysFromToday = (dayOfWeekInt - nd.weekday()) % 7

        if daysFromToday:
            nd += timedelta(daysFromToday)

        return nd
    # end nextDateForDay(str)

# end class CourtTimes


def decodeCourtTimes(jsonDict: dict):
    """Decodes CourtTimes JSON"""
    if all(fld in jsonDict for fld in CourtTime._fields):

        return CourtTime(time.fromisoformat(jsonDict["startTime"]),
                         jsonDict["duration"])
    elif all(fld in jsonDict for fld in CourtTimes._fields):

        return CourtTimes._make(jsonDict.values())
    else:

        return jsonDict
# end decodeCourtTimes(dict)


if __name__ == "__main__":
    data = CourtTimes([CourtTime(time(8, 30), 90),
                       CourtTime(time(9, 0), 90),
                       CourtTime(time(8, 0), 90)])
    dFileNm = Path("data.json")
    data.save(dFileNm)

    readBack = CourtTimes.load(dFileNm)

    print(type(readBack), readBack)

    for cTime in readBack.timesInPreferredOrder:
        print("time rows", cTime.getTimeRows())
        print("start times", cTime.getStartTimesForDate(CourtTimes.nextDateForDay("Wed")))
# end if
