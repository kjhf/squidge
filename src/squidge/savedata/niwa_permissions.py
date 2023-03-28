import json
from dataclasses import dataclass, field
from typing import Union


@dataclass
class NIWAPermissions:
    wob_maintainer: list[str] = field(default_factory=list)

    @staticmethod
    def from_json(obj: Union[str, dict]):
        if isinstance(obj, str):
            return NIWAPermissions(**json.loads(obj))
        elif isinstance(obj, dict):
            return NIWAPermissions(**obj)
        else:
            assert False

    def to_json(self):
        return json.dumps(self.__dict__)
