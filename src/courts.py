
import json
from pathlib import Path
from typing import NamedTuple, Type, TypeVar


class Court(NamedTuple):
    """Represents details of a tennis court"""
    name: str
    tId: str

# end class Court


class Courts(NamedTuple):
    """Represents our tennis courts"""
    courtsInPreferredOrder: list[Court]
    T = TypeVar("T")

    @classmethod
    def load(cls: Type[T], fileNm: Path) -> T:
        with open(fileNm, "r", encoding="utf-8") as file:

            return json.load(file, object_hook=decodeCourts)
    # end load(Path)

    def save(self, fileNm: Path) -> None:
        with open(fileNm, "w", encoding="utf-8", newline="\n") as file:
            dct = {"courtsInPreferredOrder":
                   [court._asdict() for court in self.courtsInPreferredOrder]}
            json.dump(dct, file, ensure_ascii=False, indent=3)
    # end save(Path)

# end class Courts


def decodeCourts(jsonDict: dict):
    """Decodes Courts JSON"""
    if all(fld in jsonDict for fld in Court._fields):

        return Court._make(jsonDict.values())
    elif all(fld in jsonDict for fld in Courts._fields):

        return Courts._make(jsonDict.values())
    else:

        return jsonDict
# end decodeCourts(dict)


if __name__ == "__main__":
    data = Courts([Court("Court #1", "178"),
                   Court("Court #3", "180"),
                   Court("Court #12", "189")])
    dFileNm = Path("data.json")
    data.save(dFileNm)

    readBack = Courts.load(dFileNm)

    print(type(readBack), readBack)
# end if
