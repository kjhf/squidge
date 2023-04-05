import json
from dataclasses import dataclass, field
from typing import Union


@dataclass
class NIWAPermissions:
    wob_maintainer: list[str] = field(default_factory=list)

    @staticmethod
    def from_json(obj: Union[str, dict]):
        if isinstance(obj, str):
            json_ob = json.loads(obj)
        elif isinstance(obj, dict):
            json_ob = obj
        else:
            assert False, f"NIWAPermissions: Unknown type passed to from_json: {type(obj)}"

        assert isinstance(json_ob, dict)
        return NIWAPermissions(
            wob_maintainer=json_ob.get("wob_maintainer", [])
        )

    def as_dict(self):
        return self.__dict__
