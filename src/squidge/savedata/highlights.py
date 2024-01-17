import json
from dataclasses import dataclass, field
from typing import Union


@dataclass
class Highlights:
    highlights: dict[str, list[str]] = field(default_factory=dict)

    @staticmethod
    def from_json(obj: Union[str, dict]):
        if isinstance(obj, str):
            json_ob = json.loads(obj)
        elif isinstance(obj, dict):
            json_ob = obj
        else:
            assert False, f"Highlights: Unknown type passed to from_json: {type(obj)}"

        assert isinstance(json_ob, dict)
        return Highlights(
            highlights=json_ob.get("highlights", {})
        )

    def as_dict(self):
        return self.__dict__
