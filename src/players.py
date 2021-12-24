
import json
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
    def load(cls: Type[T], fileNm: str) -> T:
        with open(fileNm, "r", encoding="utf-8") as file:

            return json.load(file, object_hook=decodePlayers)
    # end load(str)

    def save(self, fileNm: str) -> None:
        with open(fileNm, "w", encoding="utf-8") as file:
            dct = {"people": [user._asdict() for user in self.people],
                   "password": self.password}
            json.dump(dct, file, ensure_ascii=False, indent=3)
    # end save(str)

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
    data = Players([User("Diane", "dianehilleríe"),
                    User("Beckíe", "bkúmar"),
                    User("Peño", "mediterranián")], "tenis1")
    data.save("data.json")

    readback = Players.load("data.json")

    print(type(readback), readback)
# end if
