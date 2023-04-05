import json
from dataclasses import dataclass, field

from discord.abc import Messageable

from src.squidge.savedata.bad_words import BadWords
from src.squidge.savedata.niwa_permissions import NIWAPermissions
from src.squidge.savedata.wiki_permissions import WikiPermissions


@dataclass(init=True)
class SaveData:
    wiki_permissions: WikiPermissions = field(default_factory=WikiPermissions)
    bad_words: BadWords = field(default_factory=BadWords)
    niwa_permissions: NIWAPermissions = field(default_factory=NIWAPermissions)

    @staticmethod
    def from_json(save_data_json):
        sd = SaveData(
            wiki_permissions=WikiPermissions.from_json(save_data_json),
            bad_words=BadWords.from_json(save_data_json),
            niwa_permissions=NIWAPermissions.from_json(save_data_json)
        )
        return sd

    async def save(self, channel: Messageable):
        to_save = self.wiki_permissions.as_dict() | self.bad_words.as_dict() | self.niwa_permissions.as_dict()
        await channel.send(json.dumps(to_save))
