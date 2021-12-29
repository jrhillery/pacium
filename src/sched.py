
from contextlib import AbstractContextManager
from datetime import datetime
from os import getcwd
from time import sleep
from types import TracebackType
from typing import Iterator, NamedTuple, Type
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import (TimeoutException,
                                        UnexpectedAlertPresentException,
                                        WebDriverException)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.expected_conditions import (
    element_to_be_clickable, invisibility_of_element_located,
    visibility_of_element_located)
from selenium.webdriver.support.ui import WebDriverWait

from courts import Court, Courts
from players import Players, User
from times import CourtTime, CourtTimes


class CourtAndTime(NamedTuple):
    court: Court
    courtTime: CourtTime

# end class CourtAndTime


class PacException(Exception):
    """Class for handled exceptions"""

    @classmethod
    def fromXcp(cls, txtMsg: str, xcption: WebDriverException):
        """Factory method for WebDriverExceptions"""

        return cls(f"{txtMsg}, {xcption.__class__.__name__}: {xcption.msg}")
    # end fromXcp(str, WebDriverException)

# end class PacException


class PacControl(AbstractContextManager["PacControl"]):
    """Controls Prosperity Athletic Club web pages"""
    PAC_LOG_IN = "https://crcn.clubautomation.com"
    PAC_LOG_OUT = "/user/logout"
    NO_COURTS_MSG = "No available courts found"
    RES_SUMMARY = "Reservation Summary"

    def __init__(self, preferredCourtsArg: str, preferredTimesArg: str,
                 dayOfWeekArg: str, playersArg: str) -> None:
        self.webDriver: WebDriver | None = None
        self.loggedIn = False
        self.reservationStarted = False
        self.found: CourtAndTime | None = None
        self.retryLater = False
        self.playerItr: Iterator[User] | None = None
        try:
            self.preferredCourts = Courts.load(self.parmFile(preferredCourtsArg))
            self.preferredTimes = CourtTimes.load(self.parmFile(preferredTimesArg))
            self.requestDate = CourtTimes.nextDateForDay(dayOfWeekArg)
            self.players = Players.load(self.parmFile(playersArg))
        except FileNotFoundError as e:
            raise PacException(f"Unable to open file {e.filename} from {getcwd()}.") from e
    # end __init__(str, str, str, str)

    def getReqSummary(self) -> str:

        return (f"Requesting {self.preferredCourts.courtsInPreferredOrder[0].name} "
                f"at {self.preferredTimes.timesInPreferredOrder[0].strWithDate(self.requestDate)} "
                f"for {' and '.join(p.nickname for p in self.players.people)}.")
    # end getReqSummary()

    def getFoundSummary(self) -> str:
        if self.found:

            return (f"Found {self.found.court.name} available "
                    f"for {self.found.courtTime.duration} minutes "
                    f"starting at {self.found.courtTime.strWithDate(self.requestDate)}.")
        else:

            return PacControl.NO_COURTS_MSG
    # end getFoundSummary()

    @staticmethod
    def parmFile(fileNm: str) -> str:

        return f"parmFiles/{fileNm}.json"
    # end parmFile(str)

    def openBrowser(self) -> None:
        """Get web driver and open browser"""
        try:
            crOpts = webdriver.ChromeOptions()
            crOpts.add_experimental_option("excludeSwitches", ["enable-logging"])
            self.webDriver = webdriver.Chrome(options=crOpts)
        except WebDriverException as e:
            raise PacException.fromXcp("Unable to open browser", e) from e
    # end openBrowser()

    def logIn(self) -> WebElement | None:
        """Log-in to Prosperity Athletic Club home page"""
        ifXcptionMsg = "Unable to open log-in page " + PacControl.PAC_LOG_IN
        try:
            self.webDriver.get(PacControl.PAC_LOG_IN)

            ifXcptionMsg = "Unable to find log-in form"
            liForm: WebElement = self.webDriver.find_element(By.CSS_SELECTOR,
                                                             "form#caSignInLoginForm, form#signin_login_form")
            self.playerItr = iter(self.players.people)

            ifXcptionMsg = "Unable to enter first username"
            liForm.find_element(By.NAME, "login").send_keys(
                next(self.playerItr).username, Keys.TAB)

            ifXcptionMsg = "Unable to enter password"
            self.webDriver.switch_to.active_element.send_keys(self.players.password)

            ifXcptionMsg = "Unable to submit log-in"
            liForm.submit()

            ifXcptionMsg = "Timed out waiting to log-in"
            link = WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable((By.LINK_TEXT, "Reserve a Court")))
            self.loggedIn = True

            # now on home page
            return link
        except WebDriverException as e:
            raise PacException.fromXcp(ifXcptionMsg, e) from e
    # end logIn()

    def logOut(self) -> None:
        """Log-out from Prosperity Athletic Club"""
        loUrl = urljoin(self.webDriver.current_url, PacControl.PAC_LOG_OUT)
        try:
            self.webDriver.get(loUrl)
            self.loggedIn = False
        except WebDriverException as e:
            raise PacException.fromXcp("Unable to log-out via " + loUrl, e) from e
    # end logOut()

    def navigateToSchedule(self, reserveLink: WebElement) -> None:
        ifXcptionMsg = "Unable to select home page link to reserve a court"
        try:
            reserveLink.click()

            ifXcptionMsg = "Timed out waiting to display court schedule"
            schDate: str = WebDriverWait(self.webDriver, 15).until(
                visibility_of_element_located(
                    (By.CSS_SELECTOR, "input#date"))).get_attribute("value")
            diff = self.requestDate - datetime.strptime(schDate, "%m/%d/%Y").date()

            if diff:
                ifXcptionMsg = f"Unable to select date {self.requestDate} on schedule in {diff}"
                self.webDriver.execute_script(
                    f"calendarAddDay($('date'), {diff.days}, 'mm/dd/yyyy');")

            ifXcptionMsg = "Timed out waiting to display selected date"
            reserveLink = WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable((By.CSS_SELECTOR, "a#reserve-permanent-member-button")))

            ifXcptionMsg = "Unable to start reserving a court"
            self.webDriver.execute_script("arguments[0].click();", reserveLink)
            self.reservationStarted = True
        except WebDriverException as e:
            raise PacException.fromXcp(ifXcptionMsg, e) from e
    # end navigateToSchedule(WebElement)

    def addPlayers(self) -> None:
        addNameLocator = By.CSS_SELECTOR, "input#fakeUserName"
        ifXcptionMsg = ""
        try:
            while player := next(self.playerItr, None):
                ifXcptionMsg = "Timed out waiting for player entry field"
                inputFld: WebElement = WebDriverWait(self.webDriver, 15).until(
                    element_to_be_clickable(addNameLocator))

                ifXcptionMsg = "Unable to key-in players for reservation"
                inputFld.send_keys(player.username)

                ifXcptionMsg = "Timed out waiting for player name in list"
                playerLnk: WebElement = WebDriverWait(self.webDriver, 15).until(
                    element_to_be_clickable((By.LINK_TEXT, player.username)))

                ifXcptionMsg = f"Unable to add player {player.username} for reservation"
                playerLnk.click()
            # end while

            ifXcptionMsg = "Timed out waiting for schedule to redisplay"
            WebDriverWait(self.webDriver, 15).until(element_to_be_clickable(addNameLocator))
        except WebDriverException as e:
            raise PacException.fromXcp(ifXcptionMsg, e) from e
    # end addPlayers()

    def findSchBlock(self, court: Court, timeRow: str) -> WebElement:

        return self.webDriver.find_element(By.CSS_SELECTOR,
                                           f"td#court_{court.tId}_row_{timeRow}")
    # end findSchBlock(Court, str)

    def blockAvailable(self, court: Court, timeRow: str) -> bool:
        """Return True when the specified schedule block is available"""
        schBlock = self.findSchBlock(court, timeRow)

        return "notenabled" not in schBlock.get_attribute("class")
    # end blockAvailable(Court, str)

    def findFirstAvailableCourt(self) -> CourtAndTime:
        for courtTime in self.preferredTimes.timesInPreferredOrder:
            timeRows = courtTime.getTimeRows()

            for court in self.preferredCourts.courtsInPreferredOrder:

                if all(self.blockAvailable(court, tr) for tr in timeRows):

                    return CourtAndTime(court, courtTime)
            # end for
        # end for

        raise PacException(PacControl.NO_COURTS_MSG)
    # end findFirstAvailableCourt()

    def checkForErrorWindow(self) -> None:
        """Look for an error window;
            can be caused by looking too early on a future day
            and by looking earlier than run time on run day"""
        try:
            errorWindow: WebElement = WebDriverWait(self.webDriver, 2.5).until(
                visibility_of_element_located(
                    (By.CSS_SELECTOR, "div#confirm-user-popup, div#alert-dialog-1")))
            raise PacException(f"Encountered error: {errorWindow.text}")
        except TimeoutException:
            # no error window - this is good
            pass
    # end checkForErrorWindow()

    def selectAvailableCourt(self) -> None:
        ifXcptionMsg = "Unable to find court time block"
        try:
            fac = self.findFirstAvailableCourt()

            ifXcptionMsg = "Unable to select court time block"
            for timeRow in fac.courtTime.getTimeRows():
                self.findSchBlock(fac.court, timeRow).click()

            ifXcptionMsg = "Unable to view reservation summary"
            self.webDriver.find_element(By.LINK_TEXT, PacControl.RES_SUMMARY).click()

            ifXcptionMsg = "Unable to verify reservation is good"
            self.checkForErrorWindow()
            self.found = fac
        except UnexpectedAlertPresentException as e:
            # this can be caused by looking too many days in the future
            self.retryLater = True

            raise PacException(e.alert_text) from e
        except WebDriverException as e:
            raise PacException.fromXcp(ifXcptionMsg, e) from e
    # end selectAvailableCourt()

    def cancelPendingReservation(self):
        ifXcptionMsg = "Unable to cancel pending reservation"
        try:
            self.webDriver.find_element(By.LINK_TEXT, "Cancel Reservation").click()

            ifXcptionMsg = "Timed out waiting for cancel"
            WebDriverWait(self.webDriver, 15).until(
                invisibility_of_element_located((By.LINK_TEXT, PacControl.RES_SUMMARY)))
            self.reservationStarted = False
        except WebDriverException as e:
            raise PacException.fromXcp(ifXcptionMsg, e) from e
    # end cancelPendingReservation()

    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None,
                 traceback: TracebackType | None) -> bool | None:

        if self.reservationStarted:
            self.cancelPendingReservation()

        if self.loggedIn:
            self.logOut()
        sleep(3)

        if self.webDriver:
            self.webDriver.quit()
            self.webDriver = None

        return super().__exit__(exc_type, exc_value, traceback)
    # end __exit__(Type[BaseException] | None, BaseException | None, TracebackType | None)

# end class PacControl


if __name__ == "__main__":
    try:
        with PacControl("court6First", "time1000First", "Thu", "playWithBecky") as pacCtrl:
            print(pacCtrl.getReqSummary())
            pacCtrl.openBrowser()

            reserveLink = pacCtrl.logIn()
            pacCtrl.navigateToSchedule(reserveLink)
            pacCtrl.addPlayers()
            pacCtrl.selectAvailableCourt()
            print(pacCtrl.getFoundSummary())
            sleep(12)
        # end with
    except PacException as e:
        print(e)
