from dataclasses import dataclass, field

from src.squidge.savedata.bad_words import BadWords
from src.squidge.savedata.niwa_permissions import NIWAPermissions
from src.squidge.savedata.wiki_permissions import WikiPermissions


@dataclass(init=True)
class SaveData:
    wiki_permissions: WikiPermissions = field(default_factory=WikiPermissions)
    bad_words: BadWords = field(default_factory=BadWords)
    niwa_permissions: NIWAPermissions = field(default_factory=NIWAPermissions)
