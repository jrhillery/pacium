
import logging
from io import TextIOWrapper
from logging.config import dictConfig
from logging.handlers import RotatingFileHandler

from pacargs import PacArgs
from paccontrol import PacControl, PacException


class LfRotatingFileHandler(RotatingFileHandler):

    def _open(self) -> TextIOWrapper:
        logStream = super()._open()
        logStream.reconfigure(newline="\n")

        return logStream
    # end _open()

# end class LfRotatingFileHandler


def configLogging(testLog: bool):
    # format times like: Tue Feb 08 18:25:02
    DATE_FMT_DAY_SECOND = "%a %b %d %H:%M:%S"

    dictConfig({
        "version": 1,
        "formatters": {
            "detail": {
                "format": "%(levelname)s %(asctime)s.%(msecs)03d %(module)s: %(message)s",
                "datefmt": DATE_FMT_DAY_SECOND
            },
            "simple": {
                "format": "%(asctime)s.%(msecs)03d: %(message)s",
                "datefmt": DATE_FMT_DAY_SECOND
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "pacium.LfRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detail",
                "filename": "pacium.tst.log" if testLog else "pacium.log",
                "maxBytes": 30000,
                "backupCount": 1,
                "encoding": "utf-8"
            }
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["console", "file"]
        }
    })
# end configLogging(bool)


if __name__ == "__main__":
    cLArgs = PacArgs()
    configLogging(cLArgs.showMode or cLArgs.testMode)
    try:
        pacCtrl = PacControl(cLArgs)
        pacCtrl.main()
    except PacException as xcpt:
        logging.error(xcpt)
        logging.debug("Exception suppressed:", exc_info=xcpt)
