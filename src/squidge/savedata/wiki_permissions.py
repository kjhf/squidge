import json
from dataclasses import dataclass, field
from typing import Union

from discord import User, Member


@dataclass
class WikiPermissions:
    owner: list[str] = field(default_factory=list)
    admin: list[str] = field(default_factory=list)
    editor: list[str] = field(default_factory=list)
    patrol: list[str] = field(default_factory=list)

    @staticmethod
    def from_json(obj: Union[str, dict]):

        if isinstance(obj, str):
            json_ob = json.loads(obj)
        elif isinstance(obj, dict):
            json_ob = obj
        else:
            assert False, f"WikiPermissions: Unknown type passed to from_json: {type(obj)}"

        assert isinstance(json_ob, dict)
        return WikiPermissions(
            owner=json_ob.get("owner", []),
            admin=json_ob.get("admin", []),
            editor=json_ob.get("editor", []),
            patrol=json_ob.get("patrol", [])
        )

    def as_dict(self):
        return self.__dict__

    def is_editor(self, id: Union[User, Member, str, int]):
        if self.is_admin(id) or self.is_owner(id):
            return True

        elif isinstance(id, str):
            return id in self.editor
        elif isinstance(id, int):
            return id.__str__() in self.editor
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.editor
        else:
            raise TypeError(f"_is_editor id unknown type: {type(id)}")

    def is_admin(self, id: Union[User, Member, str, int]):
        if self.is_owner(id):
            return True

        elif isinstance(id, str):
            return id in self.admin
        elif isinstance(id, int):
            return id.__str__() in self.admin
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.admin
        else:
            raise TypeError(f"_is_admin id unknown type: {type(id)}")

    def is_owner(self, id: Union[User, Member, str, int]):
        if isinstance(id, str):
            return id in self.owner
        elif isinstance(id, int):
            return id.__str__() in self.owner
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.owner
        else:
            raise TypeError(f"_is_owner id unknown type: {type(id)}")

    def is_patrol(self, id: Union[User, Member, str, int]):
        if isinstance(id, str):
            return id in self.patrol
        elif isinstance(id, int):
            return id.__str__() in self.patrol
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.patrol
        else:
            raise TypeError(f"_is_patrol id unknown type: {type(id)}")

    def get_role_list(self, role: str) -> list[str]:
        return getattr(self, role)
