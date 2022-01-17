
from argparse import ArgumentParser, Namespace
from contextlib import AbstractContextManager
from datetime import date, datetime
from os import getcwd
from pathlib import Path
from time import sleep
from types import TracebackType
from typing import Iterator, NamedTuple, Type
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import (
    NoAlertPresentException, TimeoutException, WebDriverException)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.expected_conditions import (
    element_to_be_clickable, invisibility_of_element_located)
from selenium.webdriver.support.wait import WebDriverWait

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
    def fromXcp(cls, unableMsg: str, xcption: WebDriverException):
        """Factory method for WebDriverExceptions"""
        return cls(f"Unable to {unableMsg}, {xcption.__class__.__name__}: {xcption.msg}")
    # end fromXcp(str, WebDriverException)

    @classmethod
    def fromAlert(cls, unableMsg: str, alertText: str):
        """Factory method for alerts or similar"""
        return cls(f"Unable to {unableMsg} due to: {alertText}")
    # end fromAlert(str, str)

# end class PacException


class PacControl(AbstractContextManager["PacControl"]):
    """Controls Prosperity Athletic Club web pages"""
    PAC_LOG_IN = "https://crcn.clubautomation.com"
    PAC_LOG_OUT = "/user/logout"
    NO_COURTS_MSG = "No available courts found"
    LOGIN_FORM_LOCATOR = By.CSS_SELECTOR, "form#caSignInLoginForm, form#signin_login_form"
    USERNAME_LOCATOR = By.NAME, "login"
    RESERVE_LOCATOR_A = By.LINK_TEXT, "Reserve a Court"
    LOADING_SPLASH_LOCATOR = By.CSS_SELECTOR, "div#ui-id-1"
    SCHED_DATE_LOCATOR = By.CSS_SELECTOR, "input#date"
    RESERVE_LOCATOR_B = By.CSS_SELECTOR, "a#reserve-permanent-member-button"
    ADD_NAME_LOCATOR = By.CSS_SELECTOR, "input#fakeUserName"
    ERROR_WIN_LOCATOR = By.CSS_SELECTOR, "div#confirm-user-popup, div#alert-dialog-1"
    RES_SUMMARY_LOCATOR = By.LINK_TEXT, "Reservation Summary"
    RES_CANCEL_LOCATOR = By.LINK_TEXT, "Cancel Reservation"

    def __init__(self) -> None:
        self.webDriver: WebDriver | None = None
        self.loggedIn = False
        self.reservationStarted = False
        self.found: CourtAndTime | None = None
        self.reserved = False
        self.retryLater = False
        self.playerItr: Iterator[User] | None = None
        args = PacControl.parseArgs()
        try:
            self.preferredCourts = Courts.load(PacControl.parmFile(args.preferredCourts))
            self.preferredTimes = CourtTimes.load(PacControl.parmFile(args.preferredTimes))
            self.requestDate = CourtTimes.nextDateForDay(args.dayOfWeek)
            self.players = Players.load(PacControl.parmFile(args.players))
        except FileNotFoundError as e:
            raise PacException(f"Unable to open file {e.filename} from {getcwd()}.") from e
        except ValueError as e:
            raise PacException(", ".join(e.args)) from e
    # end __init__()

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

    @staticmethod
    def parmFileStems(curDir: Path, pattern: str) -> list[str]:
        """Get a list of file name stems matching the specified pattern"""

        return [f.stem for f in curDir.glob(PacControl.parmFile(pattern))]
    # end parmFileStems(Path, str)

    @staticmethod
    def parseArgs() -> Namespace:
        """Parse the command line arguments"""
        cd = Path(".")
        ap = ArgumentParser(description="Module to assist scheduling")
        ap.add_argument("preferredCourts", help="preferred courts",
                        choices=PacControl.parmFileStems(cd, "court*"))
        ap.add_argument("preferredTimes", help="preferred times",
                        choices=PacControl.parmFileStems(cd, "time*"))
        ap.add_argument("dayOfWeek", help="day of week abbreviation",
                        choices=[date(2023, 1, dm).strftime("%a") for dm in range(1, 8)])
        ap.add_argument("players", help="players for reservation",
                        choices=PacControl.parmFileStems(cd, "playWith*"))

        return ap.parse_args()
    # end parseArgs()

    def openBrowser(self) -> WebDriver:
        """Get web driver and open browser"""
        try:
            self.webDriver = webdriver.Chrome()

            return self.webDriver
        except WebDriverException as e:
            raise PacException.fromXcp("open browser", e) from e
    # end openBrowser()

    def logIn(self) -> None:
        """Log-in to Prosperity Athletic Club home page"""
        doingMsg = "open log-in page " + PacControl.PAC_LOG_IN
        try:
            self.webDriver.get(PacControl.PAC_LOG_IN)

            doingMsg = "find log-in form"
            liForm = self.webDriver.find_element(*PacControl.LOGIN_FORM_LOCATOR)
            self.playerItr = iter(self.players.people)

            doingMsg = "enter first username"
            liForm.find_element(*PacControl.USERNAME_LOCATOR).send_keys(
                next(self.playerItr).username, Keys.TAB)

            doingMsg = "enter password"
            self.webDriver.switch_to.active_element.send_keys(self.players.password)

            doingMsg = "submit log-in"
            liForm.submit()

            doingMsg = "complete log-in"
            WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable(PacControl.RESERVE_LOCATOR_A),
                "Timed out waiting to log-in")
            self.loggedIn = True
            # now on home page
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end logIn()

    def logOut(self) -> None:
        """Log-out from Prosperity Athletic Club"""
        loUrl = urljoin(self.webDriver.current_url, PacControl.PAC_LOG_OUT)
        try:
            self.webDriver.get(loUrl)
            self.loggedIn = False
            # give us a chance to see we are logged out
            sleep(0.75)
        except WebDriverException as e:
            raise PacException.fromXcp("log-out via " + loUrl, e) from e
    # end logOut()

    def waitOutLoadingSplash(self, doingMsg: str) -> None:
        """Wait for loading splash screen to hide"""
        WebDriverWait(self.webDriver, 15).until(
            invisibility_of_element_located(PacControl.LOADING_SPLASH_LOCATOR),
            "Timed out waiting to " + doingMsg)
    # end waitOutLoadingSplash(str)

    def clickAndLoad(self, action: str, locator: tuple[str, str]) -> None:
        """Click a located element, then wait for loading splash screen to hide"""
        doingMsg = "request " + action
        try:
            self.webDriver.find_element(*locator).click()

            doingMsg = "load " + action
            self.waitOutLoadingSplash(doingMsg)
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end clickAndLoad(str, tuple[str, str])

    def navigateToSchedule(self) -> None:
        doingMsg = "read initial schedule date"
        try:
            self.clickAndLoad("reserve court on home page", PacControl.RESERVE_LOCATOR_A)

            schDate = self.webDriver.find_element(
                *PacControl.SCHED_DATE_LOCATOR).get_attribute("value")
            diff = self.requestDate - datetime.strptime(schDate, "%m/%d/%Y").date()

            if diff:
                doingMsg = f"request date {self.requestDate} on schedule in {diff}"
                self.webDriver.execute_script(
                    f"calendarAddDay($('date'), {diff.days}, 'mm/dd/yyyy');")

                doingMsg = "load selected schedule date"
                self.waitOutLoadingSplash(doingMsg)
            # end if

            self.clickAndLoad("reserve court on schedule page", PacControl.RESERVE_LOCATOR_B)
            self.reservationStarted = True
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end navigateToSchedule()

    def addPlayers(self) -> None:
        try:
            while player := next(self.playerItr, None):
                self.addPlayer(player.username)
                WebDriverWait(self.webDriver, 15).until(
                    element_to_be_clickable(PacControl.ADD_NAME_LOCATOR),
                    "Timed out waiting for player entry field")
            # end while
        except WebDriverException as e:
            raise PacException.fromXcp("see updated player list", e) from e
    # end addPlayers()

    def addPlayer(self, playerName: str) -> None:
        retrys = 0
        doingMsg = ""
        try:
            while True:
                doingMsg = "key-in player for reservation"
                inputFld = self.webDriver.find_element(*PacControl.ADD_NAME_LOCATOR)
                inputFld.clear()
                inputFld.send_keys(playerName)

                try:
                    doingMsg = "find player"
                    playerLnk: WebElement = WebDriverWait(self.webDriver, 15).until(
                        element_to_be_clickable((By.LINK_TEXT, playerName)),
                        f"Timed out waiting for {playerName} in list")

                    doingMsg = f"add player {playerName} to reservation"
                    playerLnk.click()

                    # found the player, stop retrying
                    break
                except TimeoutException as e:
                    if (retrys := retrys + 1) == 3:
                        raise e
                    print(f"Try again to add player {playerName} to reservation")
            # end while
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end addPlayer(str)

    def findSchBlock(self, court: Court, timeRow: str) -> WebElement:
        return self.webDriver.find_element(
            By.CSS_SELECTOR, f"td#court_{court.tId}_row_{timeRow}")
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

    def handleAlert(self, unableMsg: str) -> None:
        try:
            alert = self.webDriver.switch_to.alert

            # we get here when an alert is present
            # this alert can be caused by looking too many days in the future
            alertText = alert.text
            alert.dismiss()
            self.retryLater = True

            raise PacException.fromAlert(unableMsg, alertText)
        except NoAlertPresentException:
            # good to not have an alert
            pass
    # end handleAlert(str)

    def selectAvailableCourt(self) -> None:
        doingMsg = "find court time block"
        try:
            self.found = self.findFirstAvailableCourt()

            doingMsg = "select court time block"
            for timeRow in self.found.courtTime.getTimeRows():
                self.findSchBlock(self.found.court, timeRow).click()
                self.handleAlert(doingMsg)
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end selectAvailableCourt()

    def handleErrorWindow(self, unableMsg: str) -> None:
        """Look for an error window;
            can be caused by looking too early on a future day
            and by looking earlier than run time on run day"""
        errWins = self.webDriver.find_elements(*PacControl.ERROR_WIN_LOCATOR)

        if errWins:
            trueErrWins = [errWin for errWin in errWins if errWin.is_displayed()]

            if trueErrWins:
                raise PacException.fromAlert(
                    unableMsg,
                    "; ".join(errorWindow.text for errorWindow in trueErrWins))
    # end handleErrorWindow(str)

    def reserveCourt(self) -> None:
        doingMsg = "verify reservation is good"
        try:
            self.clickAndLoad("reservation summary", PacControl.RES_SUMMARY_LOCATOR)
            self.handleErrorWindow(doingMsg)
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end reserveCourt()

    def cancelPendingReservation(self):
        self.clickAndLoad("cancel pending reservation", PacControl.RES_CANCEL_LOCATOR)
        self.reservationStarted = False
        # give us a chance to see reservation cancelled
        sleep(0.25)
    # end cancelPendingReservation()

    def __exit__(self, exc_type: Type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback: TracebackType | None) -> bool | None:

        try:
            if self.reservationStarted:
                self.cancelPendingReservation()
        finally:
            if self.loggedIn:
                self.logOut()

        return None
    # end __exit__(Type[BaseException] | None, BaseException | None, TracebackType | None)

# end class PacControl


if __name__ == "__main__":
    try:
        pacCtrl = PacControl()
        print(pacCtrl.getReqSummary())

        with pacCtrl.openBrowser(), pacCtrl:
            pacCtrl.logIn()
            pacCtrl.navigateToSchedule()
            pacCtrl.addPlayers()
            pacCtrl.selectAvailableCourt()
            pacCtrl.reserveCourt()
            print(pacCtrl.getFoundSummary())
            sleep(9)
        # end with
    except PacException as xcpt:
        print(xcpt)
