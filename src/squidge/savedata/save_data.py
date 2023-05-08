import json
import os
from dataclasses import dataclass, field

from discord.abc import Messageable
from discord.ext.commands import Context

from src.squidge.savedata.bad_words import BadWords
from src.squidge.savedata.niwa_permissions import NIWAPermissions
from src.squidge.savedata.wiki_permissions import WikiPermissions
from src.squidge.savedata.highlights import Highlights


@dataclass(init=True)
class SaveData:
    wiki_permissions: WikiPermissions = field(default_factory=WikiPermissions)
    bad_words: BadWords = field(default_factory=BadWords)
    niwa_permissions: NIWAPermissions = field(default_factory=NIWAPermissions)
    highlights: Highlights = field(default_factory=Highlights)

    @staticmethod
    def from_json(save_data_json):
        sd = SaveData(
            wiki_permissions=WikiPermissions.from_json(save_data_json),
            bad_words=BadWords.from_json(save_data_json),
            niwa_permissions=NIWAPermissions.from_json(save_data_json),
            highlights=Highlights.from_json(save_data_json)
        )
        return sd

    async def save(self, ctx_or_channel: Messageable):
        if isinstance(ctx_or_channel, Context):
            channel = ctx_or_channel.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
        else:
            channel = ctx_or_channel
        to_save = (self.wiki_permissions.as_dict()
                   | self.bad_words.as_dict()
                   | self.niwa_permissions.as_dict()
                   | self.highlights.as_dict())
        await channel.send(json.dumps(to_save))
