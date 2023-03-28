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
            return BadWords(**json.loads(obj))
        elif isinstance(obj, dict):
            return BadWords(**obj)
        else:
            assert False

    def to_json(self):
        return json.dumps(self.__dict__)
