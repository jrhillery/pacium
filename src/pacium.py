
import logging
from logging.config import dictConfig

from pacargs import PacArgs
from sched import PacControl, PacException


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
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detail",
                "filename": "pacium.tst.log" if testLog else "pacium.log",
                "maxBytes": 30000,
                "backupCount": 2,
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
