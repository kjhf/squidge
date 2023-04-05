import json
from dataclasses import dataclass, field
from typing import Union


@dataclass
class BadWords:
    whitelist: list[str] = field(default_factory=list)
    false_triggers: list[str] = field(default_factory=list)

    @staticmethod
    def from_json(obj: Union[str, dict]):
        if isinstance(obj, str):
            json_ob = json.loads(obj)
        elif isinstance(obj, dict):
            json_ob = obj
        else:
            assert False, f"BadWords: Unknown type passed to from_json: {type(obj)}"

        assert isinstance(json_ob, dict)
        return BadWords(
            whitelist=json_ob.get("whitelist", []),
            false_triggers=json_ob.get("false_triggers", [])
        )

    def as_dict(self):
        return self.__dict__
