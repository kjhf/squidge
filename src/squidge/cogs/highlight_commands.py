import asyncio
import re
from typing import Union, Optional

from discord import User, Message, DMChannel, TextChannel
from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.entry.consts import COMMAND_SYMBOL
from src.squidge.savedata.highlights import Highlights


class HighlightCommands(commands.Cog):
    """A grouping of functions that supports Squidge's highlight functionality."""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @commands.command(
        name='highlight',
        description="Notifies you for a given phrase.",
        brief="Toggles a highlight notifier for you.",
        aliases=['hilight'],
        help=f'{COMMAND_SYMBOL}highlight <phrase>. Use \\b to mark a boundary at the start/end.',
        pass_ctx=True)
    async def highlight(self, ctx: Context, *, phrase: str):
        added = toggle_highlight(self.bot.save_data.highlights, ctx.author.id, phrase)
        if added:
            no_space_warning = "" if '\\b' in phrase else \
                "Note: your phrase doesn't have \\b in it, so will match inside words. " \
                "Use \\b for boundary if you don't want this."
            await ctx.send(f"You are now watching `{added}`. {no_space_warning}")
        else:
            await ctx.send(f"You are no longer watching `{phrase}`.")
        await self.bot.save_data.save(ctx)

    async def process_highlight(self, ctx: Context):
        """Send a highlight message if appropriate"""
        saved_highlights = self.bot.save_data.highlights
        for user_id, watched in saved_highlights.highlights.items():
            if should_highlight(saved_highlights, user_id, ctx.message):
                user_id_int = int(user_id)
                channel: TextChannel = ctx.channel
                # Make sure the user can see this channel!
                if any(user_id_int == member.id for member in channel.members):
                    user = ctx.bot.get_user(user_id_int)
                    await user.send("Hey! One of your highlights was mentioned at: " + ctx.message.jump_url)
            await asyncio.sleep(0.001)  # yield


def standardise_user_id(user: Union[User, str, int]) -> str:
    """Return the user/user id object as an id str."""
    user_id = str(user.id) if isinstance(user, User) else str(user)
    assert user_id.isnumeric(), "Passed str is not numeric."
    return user_id


def toggle_highlight(saved_highlights: Highlights, user: int, phrase: str) -> Optional[str]:
    """Toggles the highlight for a given user. Returns the phrase if added, None if removed."""
    user_id = standardise_user_id(user)
    phrase = phrase.casefold().replace(' ', '\\b')
    if user_id in saved_highlights.highlights:
        if phrase in saved_highlights.highlights[user_id]:
            saved_highlights.highlights[user_id].remove(phrase)
            return None
        else:
            saved_highlights.highlights[user_id].append(phrase)
            return phrase
    # else
    saved_highlights.highlights[user_id] = [phrase]
    return phrase


def should_highlight(saved_highlights: Highlights, user, message: Message) -> bool:
    """Get if the message should be highlighted for the user"""
    user_id = standardise_user_id(user)
    if message.author.bot or str(message.author.id) == user_id or isinstance(message.channel, DMChannel):
        return False

    if user_id in saved_highlights.highlights and message.content:
        content = " " + message.content + " "
        if any(bool(re.search(highlight, content, re.IGNORECASE)) for highlight in saved_highlights.highlights[user_id]):
            return True
    return False