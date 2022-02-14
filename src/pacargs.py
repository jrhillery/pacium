
from argparse import ArgumentParser, Namespace
from datetime import date
from pathlib import Path


class PacArgs(object):
    """Class to house pacium command line arguments"""

    def __init__(self):
        args = PacArgs.parseArgs()
        self.preferredCourts: Path = Path(PacArgs.parmFile(args.preferredCourts))
        self.preferredTimes: Path = Path(PacArgs.parmFile(args.preferredTimes))
        self.dayOfWeek: str = args.dayOfWeek
        self.players: Path = Path(PacArgs.parmFile(args.players))
        self.showMode: bool = args.show
        self.testMode: bool = args.test
    # end __init__()

    @staticmethod
    def parmFile(fileNm: str) -> str:

        return f"parmFiles/{fileNm}.json"
    # end parmFile(str)

    @staticmethod
    def parmFileStems(curDir: Path, pattern: str) -> list[str]:
        """Get a list of file name stems matching the specified pattern"""

        return [f.stem for f in curDir.glob(PacArgs.parmFile(pattern))]
    # end parmFileStems(Path, str)

    @staticmethod
    def parseArgs() -> Namespace:
        """Parse the command line arguments"""
        cd = Path(".")
        ap = ArgumentParser(description="Module to assist scheduling")
        ap.add_argument("preferredCourts", help="preferred courts",
                        choices=PacArgs.parmFileStems(cd, "court*"))
        ap.add_argument("preferredTimes", help="preferred times",
                        choices=PacArgs.parmFileStems(cd, "time*"))
        ap.add_argument("dayOfWeek", help="day of week abbreviation",
                        choices=[date(2023, 1, dm).strftime("%a") for dm in range(1, 8)])
        ap.add_argument("players", help="players for reservation",
                        choices=PacArgs.parmFileStems(cd, "playWith*"))
        ap.add_argument("-s", "--show", help="show mode - just show the court schedule",
                        action="store_true")
        ap.add_argument("-t", "--test", help="test mode - don't confirm reservation",
                        action="store_true")

        return ap.parse_args()
    # end parseArgs()

# end class PacArgs
