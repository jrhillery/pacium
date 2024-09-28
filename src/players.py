
import json
from pathlib import Path
from typing import NamedTuple, Type, TypeVar


class User(NamedTuple):
    """Represents details of a person"""
    nickname: str
    username: str

# end class User


class Players(NamedTuple):
    """Represents our players"""
    people: list[User]
    password: str
    T = TypeVar("T")

    @classmethod
    def load(cls: Type[T], fileNm: Path) -> T:
        with open(fileNm, "r", encoding="utf-8") as file:

            return json.load(file, object_hook=decodePlayers)
    # end load(Path)

    def save(self, fileNm: Path) -> None:
        with open(fileNm, "w", encoding="utf-8", newline="\n") as file:
            dct = {"people": [user._asdict() for user in self.people],
                   "password": self.password}
            json.dump(dct, file, ensure_ascii=False, indent=3)
    # end save(Path)

    def __str__(self) -> str:
        return str(self.people)

# end class Players


def decodePlayers(jsonDict: dict):
    """Decodes Players JSON"""
    if all(fld in jsonDict for fld in User._fields):

        return User._make(jsonDict.values())
    elif all(fld in jsonDict for fld in Players._fields):

        return Players._make(jsonDict.values())
    else:

        return jsonDict
# end decodePlayers(dict)


if __name__ == "__main__":
    # noinspection SpellCheckingInspection
    data = Players([User("Diane", "dianehilleríe"),
                    User("Beckíe", "bkúmar"),
                    User("Peño", "mediterranián")], "tenis1")
    dFileNm = Path("data.json")
    data.save(dFileNm)

    readBack = Players.load(dFileNm)

    print(type(readBack), readBack)
# end if
