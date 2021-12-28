
from contextlib import AbstractContextManager
from datetime import datetime
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
    pass

# end class PacException

class PacControl(AbstractContextManager["PacControl"]):
    """Controls Prosperity Athletic Club web pages"""
    PAC_LOG_IN = "https://crcn.clubautomation.com"
    PAC_LOG_OUT = "/user/logout"
    RES_SUMMARY = "Reservation Summary"

    def __init__(self, preferredCourtsArg: str, preferredTimesArg: str,
                 dayOfWeekArg: str, playersArg: str) -> None:
        self.webDriver: WebDriver | None = None
        self.loggedIn = False
        self.reservationStarted = False
        self.found: CourtAndTime | None = None
        self.playerItr: Iterator[User] | None = None
        self.preferredCourts = Courts.load(self.parmFile(preferredCourtsArg))
        self.preferredTimes = CourtTimes.load(self.parmFile(preferredTimesArg))
        self.requestDate = CourtTimes.nextDateForDay(dayOfWeekArg)
        self.players = Players.load(self.parmFile(playersArg))
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

            return "No available courts found"
    # end getFoundSummary()

    @staticmethod
    def parmFile(fileNm: str) -> str:

        return f"parmFiles/{fileNm}.json"
    # end parmFile(str)

    def getDriver(self) -> WebDriver:
        """Get web driver and open browser"""
        crOpts = webdriver.ChromeOptions()
        crOpts.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.webDriver = webdriver.Chrome(options=crOpts)

        return self.webDriver
    # end getDriver()

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
            reportError(ifXcptionMsg, e)
    # end logIn()

    def logOut(self) -> bool:
        """Log-out from Prosperity Athletic Club"""
        loUrl = urljoin(self.webDriver.current_url, PacControl.PAC_LOG_OUT)
        try:
            self.webDriver.get(loUrl)
            self.loggedIn = False

            return True
        except WebDriverException as e:
            reportError("Unable to log-out via " + loUrl, e)
    # end logOut()

    def navigateToSchedule(self, reserveLink: WebElement) -> bool:
        ifXcptionMsg = "Unable to select home page link to reserve a court"
        try:
            reserveLink.click()

            ifXcptionMsg = "Timed out waiting to display court schedule"
            schDate: str = WebDriverWait(self.webDriver, 15).until(
                visibility_of_element_located((By.CSS_SELECTOR, "input#date"))).get_attribute("value")
            diff = self.requestDate - datetime.strptime(schDate, "%m/%d/%Y").date()

            if diff:
                ifXcptionMsg = f"Unable to select date {self.requestDate} on schedule in {diff}"
                self.webDriver.execute_script(f"calendarAddDay($('date'), {diff.days}, 'mm/dd/yyyy');")

            ifXcptionMsg = "Timed out waiting to display selected date"
            reserveLink = WebDriverWait(self.webDriver, 15).until(
                element_to_be_clickable((By.CSS_SELECTOR, "a#reserve-permanent-member-button")))

            ifXcptionMsg = "Unable to start reserving a court"
            self.webDriver.execute_script("arguments[0].click();", reserveLink)
            self.reservationStarted = True

            return True
        except WebDriverException as e:
            reportError(ifXcptionMsg, e)
    # end navigateToSchedule(WebElement)

    def addPlayers(self) -> bool:
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

            return True
        except WebDriverException as e:
            reportError(ifXcptionMsg, e)
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

    def findFirstAvailableCourt(self) -> CourtAndTime | None:
        for courtTime in self.preferredTimes.timesInPreferredOrder:
            timeRows = courtTime.getTimeRows()

            for court in self.preferredCourts.courtsInPreferredOrder:

                if all(self.blockAvailable(court, tr) for tr in timeRows):

                    return CourtAndTime(court, courtTime)
            # end for
        # end for
    # end findFirstAvailableCourt()

    def errorWindowPresent(self) -> bool:
        """Look for an error window;
            can be caused by looking too early on a future day
            and by looking earlier than run time on run day"""
        try:
            errorWindow: WebElement = WebDriverWait(self.webDriver, 2.5).until(
                visibility_of_element_located((By.CSS_SELECTOR,
                    "div#confirm-user-popup, div#alert-dialog-1")))
            print(f"Encountered error: {errorWindow.text}")

            return True
        except TimeoutException:
            # no error window - this is good
            return False
    # end errorWindowPresent()

    def selectAvailableCourt(self) -> bool:
        ifXcptionMsg = "Unable to find court time block"
        try:
            if not (fac := self.findFirstAvailableCourt()):
                return False

            ifXcptionMsg = "Unable to select court time block"
            for timeRow in fac.courtTime.getTimeRows():
                self.findSchBlock(fac.court, timeRow).click()

            ifXcptionMsg = "Unable to view reservation summary"
            self.webDriver.find_element(By.LINK_TEXT, PacControl.RES_SUMMARY).click()

            ifXcptionMsg = "Unable to verify reservation is good"
            if allGood := not self.errorWindowPresent():
                self.found = fac

            return allGood
        except UnexpectedAlertPresentException as e:
            print(e.msg)
        except WebDriverException as e:
            reportError(ifXcptionMsg, e)
    # end selectAvailableCourt()

    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None,
            traceback: TracebackType | None) -> bool | None:

        if self.reservationStarted:
            ifXcptionMsg = "Unable to cancel reservation"
            try:
                self.webDriver.find_element(By.LINK_TEXT, "Cancel Reservation").click()

                ifXcptionMsg = "Timed out waiting for cancel"
                WebDriverWait(self.webDriver, 15).until(
                    invisibility_of_element_located((By.LINK_TEXT, PacControl.RES_SUMMARY)))
                self.reservationStarted = False
            except WebDriverException as e:
                reportError(ifXcptionMsg, e)

        if self.loggedIn:
            self.logOut()
        sleep(3)

        if self.webDriver:
            self.webDriver.quit()
            self.webDriver = None

        if isinstance(exc_value, PacException):
            print(exc_value)

            return True
        else:
            return super().__exit__(exc_type, exc_value, traceback)
    # end __exit__(Type[BaseException] | None, BaseException | None, TracebackType | None)

# end class PacControl

def reportError(txtMsg: str, xcption: Exception):
    print(txtMsg + ",", xcption.__class__.__name__ + ":", xcption)

# end reportError(str, Exception)

if __name__ == "__main__":
    try:
        with PacControl("court6First", "time1330First", "Fri", "playWithBecky") as pacCtrl:
            print(pacCtrl.getReqSummary())
            pacCtrl.getDriver()

            if reserveLink := pacCtrl.logIn():
                if pacCtrl.navigateToSchedule(reserveLink) \
                        and pacCtrl.addPlayers():
                    if pacCtrl.selectAvailableCourt():
                        pass
                print(pacCtrl.getFoundSummary())
                sleep(12)
        # end with
    except FileNotFoundError as e:
        print(f"Unable to open file {e.filename}.")
    except WebDriverException as e:
        reportError("Unable to open browser", e)
    except Exception as e:
        reportError("Failed", e)
        raise e
