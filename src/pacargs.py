
from argparse import ArgumentParser, Namespace
from datetime import date
from pathlib import Path


class PacArgs(object):
    """Class to house pacium command line arguments"""

    def __init__(self):
        self.parmPath = PacArgs.findParmPath()
        args = self.parseArgs()
        self.preferredCourts = self.parmFile(args.preferredCourts)
        self.preferredTimes = self.parmFile(args.preferredTimes)
        self.dayOfWeek: str = args.dayOfWeek
        self.players = self.parmFile(args.players)
        self.showMode: bool = args.show
        self.testMode: bool = args.test
    # end __init__()

    @staticmethod
    def findParmPath() -> Path:
        # look in child with a specific name
        pp = Path("parmFiles")

        if not pp.is_dir():
            # just use current directory
            pp = Path(".")

        return pp
    # end findParmPath()

    def parmFile(self, fileNm: Path) -> Path:
        if fileNm.exists():
            return fileNm
        else:
            pf = Path(self.parmPath, fileNm)

            return pf.with_suffix(".json")
    # end parmFile(Path)

    @staticmethod
    def parseArgs() -> Namespace:
        """Parse the command line arguments"""
        ap = ArgumentParser(description="Module to assist scheduling")
        ap.add_argument("preferredCourts", type=Path,
                        help="preferred courts (court*)")
        ap.add_argument("preferredTimes", type=Path,
                        help="preferred times (time*)")
        ap.add_argument("dayOfWeek", help="day of week abbreviation",
                        choices=[date(2023, 1, dm).strftime("%a") for dm in range(1, 8)])
        ap.add_argument("players", type=Path,
                        help="players for reservation (playWith*)")
        ap.add_argument("-s", "--show", action="store_true",
                        help="show mode - just show the court schedule")
        ap.add_argument("-t", "--test", action="store_true",
                        help="test mode - don't confirm reservation")

        return ap.parse_args()
    # end parseArgs()

# end class PacArgs
