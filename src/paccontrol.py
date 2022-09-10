
import logging
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from os import getcwd
from types import TracebackType
from typing import Iterator, NamedTuple, Type

from selenium import webdriver
from selenium.common.exceptions import (
    InvalidSelectorException, TimeoutException, WebDriverException)
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.expected_conditions import (
    any_of, element_to_be_clickable, invisibility_of_element,
    invisibility_of_element_located, visibility_of_element_located)
from selenium.webdriver.support.wait import WebDriverWait
from time import sleep

from courts import Court, Courts
from pacargs import PacArgs
from players import Players, User
from times import CourtTime, CourtTimes


class CourtAndTime(NamedTuple):
    court: Court
    courtTime: CourtTime
    startTime: str

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
    NO_COURTS_MSG = "No available courts found"
    PAC_LOG_IN = "https://app.courtreserve.com/"
    LOGIN_FORM_LOCATOR = By.CSS_SELECTOR, "form#loginForm"
    USERNAME_LOCATOR = By.CSS_SELECTOR, "input#Username"
    PASSWORD_LOCATOR = By.CSS_SELECTOR, "input#Password"
    MY_ACCOUNT = By.CSS_SELECTOR, "li#my-account-li-web"
    PAC_LOG_OUT = By.LINK_TEXT, "Log Out"
    SCH_DATE_LOCATOR = By.CSS_SELECTOR, "span.k-lg-date-format"
    RESERVE_LOCATOR_A = By.LINK_TEXT, "Reservations"
    RESERVE_LOCATOR_B = By.LINK_TEXT, "Book a Court"
    NEXT_DAY_LOCATOR = By.CSS_SELECTOR, "button.k-nav-next"
    ONE_DAY = timedelta(days=1)
    RES_TYPE_LOCATOR = By.CSS_SELECTOR, "span[aria-controls='ReservationTypeId_listbox']"
    RES_FORM_LOCATOR = By.CSS_SELECTOR, "form#createReservation-Form"
    RES_TYPE_ITEM_LOCATOR = \
        By.CSS_SELECTOR, "ul#ReservationTypeId_listbox[aria-hidden='false'] > li"
    RES_DURATION_LOCATOR = By.CSS_SELECTOR, "span[aria-controls='Duration_listbox']"
    RES_DURATION_ITEM_LOCATOR = \
        By.CSS_SELECTOR, "ul#Duration_listbox[aria-hidden='false'] > li"
    ADD_NAME_LOCATOR = By.CSS_SELECTOR, "input[name='OwnersDropdown_input']"
    ADD_NAME_ITEM_LOCATOR = By.CSS_SELECTOR, "ul#OwnersDropdown_listbox > li"
    ERROR_WIN_LOCATOR = By.CSS_SELECTOR, "div.swal2-icon-error, div#error-modal"
    DISMISS_ERROR_LOCATOR = By.CSS_SELECTOR, "button.swal2-confirm, button[type='reset']"
    RES_CONFIRM_LOCATOR = By.CSS_SELECTOR, "button.btn-submit"
    RES_CANCEL_LOCATOR = By.CSS_SELECTOR, "button[type='reset']"

    def __init__(self, args: PacArgs):
        self.webDriver: WebDriver | None = None
        self.logOutHref: str | None = None
        self.resForm: WebElement | None = None
        self.found: CourtAndTime | None = None
        self.playerHasAlreadyReserved = False
        self.playerItr: Iterator[User] | None = None
        try:
            self.preferredCourts = Courts.load(args.preferredCourts)
            self.preferredTimes = CourtTimes.load(args.preferredTimes)
            self.requestDate = CourtTimes.nextDateForDay(args.dayOfWeek)
            self.players = Players.load(args.players)
            self.showMode = args.showMode
            self.testMode = args.testMode
        except FileNotFoundError as e:
            raise PacException(f"Unable to open file {e.filename} from {getcwd()}.") from e
        except ValueError as e:
            raise PacException(", ".join(e.args)) from e
        self.player1 = self.players.people[0].nickname
        self.player2: str | None = None
    # end __init__(PacArgs)

    def getReqSummary(self) -> str:
        return (f"Requesting {self.preferredCourts.courtsInPreferredOrder[0].name} "
                f"at {self.preferredTimes.timesInPreferredOrder[0].strWithDate(self.requestDate)} "
                f"for {self.player1} and "
                f"{' or '.join(p.nickname for p in self.players.people[1:])}"
                f"{' in show mode' if self.showMode else ''}"
                f"{' in test mode' if self.testMode else ''}.")
    # end getReqSummary()

    def getFoundSummary(self) -> str:
        if self.found:
            return (f"Found {self.found.court.name} available "
                    f"for {self.found.courtTime.duration} minutes "
                    f"starting at {self.found.courtTime.strWithDate(self.requestDate)} "
                    f"for {self.player1} and {self.player2}.")
        else:
            return PacControl.NO_COURTS_MSG
    # end getFoundSummary()

    def openBrowser(self) -> WebDriver:
        """Get web driver and open browser"""
        try:
            crOpts = webdriver.ChromeOptions()
            crOpts.add_experimental_option("excludeSwitches", ["enable-logging"])
            self.webDriver = webdriver.Chrome(options=crOpts)

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
            liForm: WebElement = self.webDriver.find_element(*PacControl.LOGIN_FORM_LOCATOR)
            self.playerItr = iter(self.players.people)

            doingMsg = "enter first username"
            liForm.find_element(*PacControl.USERNAME_LOCATOR).send_keys(
                next(self.playerItr).username)

            doingMsg = "enter password"
            liForm.find_element(*PacControl.PASSWORD_LOCATOR).send_keys(
                self.players.password)

            doingMsg = "submit log-in form"
            liForm.submit()
            WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable(PacControl.MY_ACCOUNT),
                "Timed out waiting to log-in")

            # now on home page
            doingMsg = "saving log out reference"
            maList = self.mouseOver("hover over my account", PacControl.MY_ACCOUNT)

            self.logOutHref = maList.find_element(
                *PacControl.PAC_LOG_OUT).get_property("href")
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end logIn()

    def logOut(self) -> None:
        """Log-out from Prosperity Athletic Club"""
        doingMsg = "logging out"
        try:
            self.webDriver.get(self.logOutHref)
            WebDriverWait(self.webDriver, 15).until(
                invisibility_of_element_located(PacControl.SCH_DATE_LOCATOR),
                "Timed out waiting to log out")

            self.logOutHref = None
            # give us a chance to see we are logged out
            sleep(0.75)
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end logOut()

    def mouseOver(self, unableMsg: str, locator: tuple[str, str],
                  searchCtx: WebElement | None = None) -> WebElement:
        """Hover mouse over a located element"""
        if not searchCtx:
            searchCtx = self.webDriver
        try:
            foundElement = searchCtx.find_element(*locator)
            action = ActionChains(self.webDriver)
            action.move_to_element(foundElement)
            action.perform()

            return foundElement
        except WebDriverException as e:
            raise PacException.fromXcp(unableMsg, e) from e
    # end mouseOver(str, tuple[str, str], WebElement | None)

    def navigateToSchedule(self) -> None:
        doingMsg = "book a court on home page"
        try:
            resLink = self.mouseOver("hover over reservations", PacControl.RESERVE_LOCATOR_A)

            resLink.get_property("parentElement").find_element(
                *PacControl.RESERVE_LOCATOR_B).click()
            WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable(PacControl.NEXT_DAY_LOCATOR),
                "Timed out waiting to open court schedule page")

            doingMsg = "read initial schedule date"
            schDate = self.webDriver.find_element(
                *PacControl.SCH_DATE_LOCATOR).get_attribute("innerText")
            diff = self.requestDate - datetime.strptime(schDate, "%A, %B %d, %Y").date()

            while diff:
                doingMsg = f"request date {self.requestDate} on schedule in {diff}"
                self.webDriver.find_element(*PacControl.NEXT_DAY_LOCATOR).click()

                # can't seem to automate the loading spinner, so just wait a fixed time
                sleep(12)
                diff -= PacControl.ONE_DAY
            # end while
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end navigateToSchedule()

    def findSchBlock(self, court: Court, startTime: str) -> WebElement:
        # <button start="Wed Aug 24 2022 09:00:00 GMT-0400 (Eastern Daylight Time)" courtlabel="Court #3"
        # class="btn btn-default hide btn-expanded-slot slot-btn m-auto">Reserve</button>
        selector = f"button[start^='{startTime}'][courtlabel='{court.name}']"
        try:
            return self.webDriver.find_element(By.CSS_SELECTOR, selector)
        except InvalidSelectorException as e:
            raise InvalidSelectorException(f"{e.msg} {{{selector}}}", e.screen, e.stacktrace)
    # end findSchBlock(Court, str)

    def blockAvailable(self, court: Court, startTime: str) -> bool:
        """Return True when the specified schedule block is available"""
        schBlock = self.findSchBlock(court, startTime)

        return schBlock.is_displayed()
    # end blockAvailable(Court, str)

    def findFirstAvailableCourt(self) -> CourtAndTime:
        for courtTime in self.preferredTimes.timesInPreferredOrder:
            startTimes = courtTime.getStartTimesForDate(self.requestDate)

            for court in self.preferredCourts.courtsInPreferredOrder:

                if all(self.blockAvailable(court, st) for st in startTimes):

                    return CourtAndTime(court, courtTime, startTimes[0])
            # end for
        # end for

        raise PacException(PacControl.NO_COURTS_MSG)
    # end findFirstAvailableCourt()

    def selectAvailableCourt(self) -> None:
        doingMsg = "find court time block"
        try:
            self.found = self.findFirstAvailableCourt()

            doingMsg = "select court start time"
            self.findSchBlock(self.found.court, self.found.startTime).click()

            WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable(PacControl.RES_TYPE_LOCATOR),
                "Timed out waiting to open reservation dialog")
            self.resForm = self.webDriver.find_element(*PacControl.RES_FORM_LOCATOR)
        except WebDriverException as e:
            self.handleErrorWindow(doingMsg)

            raise PacException.fromXcp(doingMsg, e) from e
    # end selectAvailableCourt()

    def setReservationParameters(self):
        doingMsg = "select reservation type dropdown list"
        try:
            self.resForm.find_element(*PacControl.RES_TYPE_LOCATOR).click()
            WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable(PacControl.RES_TYPE_ITEM_LOCATOR),
                "Timed out waiting for reservation type dropdown list")

            doingMsg = "select reservation type"
            htmlItems: list[WebElement] = self.webDriver.find_elements(
                *PacControl.RES_TYPE_ITEM_LOCATOR)

            for htmlItem in htmlItems:
                if htmlItem.text == "Singles":
                    htmlItem.click()
                    break
            # end for
            doingMsg = "select duration dropdown list"
            self.resForm.find_element(*PacControl.RES_DURATION_LOCATOR).click()
            WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable(PacControl.RES_DURATION_ITEM_LOCATOR),
                "Timed out waiting for duration dropdown list")

            doingMsg = "select duration"
            htmlItems = self.resForm.find_elements(*PacControl.RES_DURATION_ITEM_LOCATOR)
            duration = "1 hour & 30 minutes" if self.found.courtTime.duration == 90 else \
                "1 hour" if self.found.courtTime.duration == 60 else "30 minutes"

            for htmlItem in htmlItems:
                if htmlItem.text == duration:
                    htmlItem.click()
                    break
            # end for
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end setReservationParameters()

    def addPlayer(self) -> None:
        try:
            if player := next(self.playerItr, None):
                self.playerHasAlreadyReserved = False
                self.selectPlayer(player.username)
                WebDriverWait(self.webDriver, 15).until(
                    element_to_be_clickable(PacControl.ADD_NAME_LOCATOR),
                    "Timed out waiting for player entry field")
                self.player2 = player.nickname
            else:
                raise PacException("Need another player for reservation")
        except WebDriverException as e:
            raise PacException.fromXcp("see updated player list", e) from e
    # end addPlayer()

    def selectPlayer(self, playerName: str) -> None:
        retrys = 0
        doingMsg = ""
        try:
            while True:
                doingMsg = "key-in player for reservation"
                inputFld = self.resForm.find_element(*PacControl.ADD_NAME_LOCATOR)
                inputFld.clear()
                inputFld.send_keys(playerName)

                try:
                    doingMsg = "find player"
                    WebDriverWait(self.webDriver, 15).until(
                        element_to_be_clickable(PacControl.ADD_NAME_ITEM_LOCATOR),
                        f"Timed out waiting for {playerName} in list")

                    doingMsg = f"add player {playerName} to reservation"
                    htmlItems = self.webDriver.find_elements(*PacControl.ADD_NAME_ITEM_LOCATOR)

                    for htmlItem in htmlItems:
                        if htmlItem.text == playerName:
                            # found the player, stop retrying
                            htmlItem.click()
                            return
                    # end for

                    raise PacException(f"Unable to find player {playerName}")
                except TimeoutException as e:
                    if (retrys := retrys + 1) == 3:
                        raise e
                    logging.warning(f"Try again to add player {playerName} to reservation")
            # end while
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end selectPlayer(str)

    def handleErrorWindow(self, unableMsg: str) -> None:
        """Look for an error window;
            can be caused by looking too far in the future,
            and by listing a player who has a reservation around the same time"""
        errWins: list[WebElement] = self.webDriver.find_elements(*PacControl.ERROR_WIN_LOCATOR)
        errWinMsgs: list[str] = []

        for errWin in errWins:
            if errWin.is_displayed():
                errorMsg = errWin.text
                doingMsg = "dismissing error"
                try:
                    errWin.find_element(*PacControl.DISMISS_ERROR_LOCATOR).click()
                    WebDriverWait(self.webDriver, 15).until(
                        invisibility_of_element(errWin),
                        "Timed out waiting to dismiss error")
                except WebDriverException as e:
                    raise PacException.fromXcp(doingMsg, e) from e

                if "requires 1 additional player" in errorMsg \
                        or "not allowed on this reservation" in errorMsg:
                    self.playerHasAlreadyReserved = True
                    logging.warning(errorMsg)
                    self.cancelPendingReservation()
                else:
                    errWinMsgs.append(errorMsg)
        # end for

        if errWinMsgs:
            raise PacException.fromAlert(unableMsg, "; ".join(errWinMsgs))
    # end handleErrorWindow(str)

    def reserveCourt(self) -> None:
        doingMsg = "verify reservation is good"
        try:
            if not self.needsToTryAgain():
                if self.testMode:
                    butt = self.resForm.find_element(*PacControl.RES_CONFIRM_LOCATOR)
                    logging.info(f"{butt.get_attribute('innerText')} enabled: {butt.is_enabled()}")
                else:
                    doingMsg = "confirming reservation"
                    self.resForm.find_element(*PacControl.RES_CONFIRM_LOCATOR).click()
                    WebDriverWait(self.webDriver, 15).until(any_of(
                        invisibility_of_element(self.resForm),
                        visibility_of_element_located(PacControl.ERROR_WIN_LOCATOR)),
                        "Timed out waiting to confirm reservation")

                    self.handleErrorWindow("confirm reservation is good")
                    self.resForm = None

                    if not self.needsToTryAgain():
                        logging.info("Reservation confirmed")
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e
    # end reserveCourt()

    def needsToTryAgain(self) -> bool:
        """Tell if there is any reason we need to try this reservation another time"""

        return self.playerHasAlreadyReserved
    # end needsToTryAgain()

    def cancelPendingReservation(self) -> None:
        doingMsg = "canceling pending reservation"
        try:
            self.resForm.find_element(*PacControl.RES_CANCEL_LOCATOR).click()
            WebDriverWait(self.webDriver, 15).until(
                invisibility_of_element(self.resForm),
                "Timed out waiting to cancel pending reservation")

            self.resForm = None
        except WebDriverException as e:
            raise PacException.fromXcp(doingMsg, e) from e

        # give us a chance to see reservation cancelled
        sleep(0.5)
    # end cancelPendingReservation()

    def __exit__(self, exc_type: Type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback: TracebackType | None) -> bool | None:

        try:
            if self.resForm:
                self.cancelPendingReservation()
                logging.info("Reservation not confirmed")
        finally:
            if self.logOutHref:
                self.logOut()

        return None
    # end __exit__(Type[BaseException] | None, BaseException | None, TracebackType | None)

    def main(self):
        logging.info(self.getReqSummary())
        with self.openBrowser(), self:
            self.logIn()
            self.navigateToSchedule()

            if self.showMode:
                sleep(20)
            else:
                needsReservation = True

                while needsReservation:
                    self.selectAvailableCourt()
                    self.setReservationParameters()
                    self.addPlayer()
                    self.reserveCourt()
                    needsReservation = self.needsToTryAgain()
                # end while
                logging.info(self.getFoundSummary())
                sleep(9)
        # end with
    # end main()

# end class PacControl
