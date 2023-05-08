import asyncio
import json
from dataclasses import dataclass, field
from typing import Union, Optional

from discord import User, Member, Message, DMChannel, TextChannel
from discord.ext.commands import Context


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

    def toggle_highlight(self, user: int, phrase: str) -> Optional[str]:
        """Toggles the highlight for a given user. Returns the phrase if added, None if removed."""
        user_id = self._standardise_user_id(user)
        phrase = phrase.casefold().replace('\\b', ' ')
        if user_id in self.highlights:
            if phrase in self.highlights[user_id]:
                self.highlights[user_id].remove(phrase)
                return None
            else:
                self.highlights[user_id].append(phrase)
                return phrase
        # else
        self.highlights[user_id] = [phrase]
        return phrase

    async def process_highlight(self, ctx: Context):
        """Send a highlight message if appropriate"""
        for user_id, watched in self.highlights.items():
            if self.should_highlight(user_id, ctx.message):
                user_id_int = int(user_id)
                channel: TextChannel = ctx.channel
                # Make sure the user can see this channel!
                if any(user_id_int == member.id for member in channel.members):
                    user = ctx.bot.get_user(user_id_int)
                    await user.send("Hey! One of your highlights was mentioned at: " + ctx.message.jump_url)
            await asyncio.sleep(0.001)  # yield

    def should_highlight(self, user, message: Message) -> bool:
        """Get if the message should be highlighted for the user"""
        user_id = self._standardise_user_id(user)
        if message.author.bot or message.author.id == user_id or isinstance(message.channel, DMChannel):
            return False

        if user_id in self.highlights and message.content:
            content = " " + message.content.casefold() + " "
            if any(highlight in content for highlight in self.highlights[user_id]):
                return True
        return False

    @staticmethod
    def _standardise_user_id(user: Union[User, str, int]) -> str:
        """Return the user/user id object as an id str."""
        user_id = str(user.id) if isinstance(user, User) else str(user)
        assert user_id.isnumeric(), "Passed str is not numeric."
        return user_id
