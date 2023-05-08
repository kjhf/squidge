"""Bot Utility commands cog."""
import os
import random

from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.entry.consts import COMMAND_SYMBOL
from src.squidge.savedata.highlights import Highlights
from src.squidge.savedata.topics import TOPICS


class BotUtilCommands(commands.Cog):
    """A grouping of bot utility commands."""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @commands.command(
        name='Hello',
        description="Says hello.",
        brief="Says hi.",
        aliases=['hello', 'hi', 'hey'],
        help=f'{COMMAND_SYMBOL}hello',
        pass_ctx=True)
    async def hello(self, ctx: Context):
        await ctx.send("Hello, {}".format(ctx.message.author.mention))

    @commands.command(
        name='Invite',
        description="Grab an invite link.",
        brief="Grab an invite link.",
        aliases=['invite'],
        help=f'{COMMAND_SYMBOL}invite',
        pass_ctx=True)
    async def invite(self, ctx: Context):
        await ctx.send(f"https://discordapp.com/oauth2/authorize?client_id={os.getenv('DISCORD_BOT_CLIENT_ID')}&scope=bot%20applications.commands&permissions=2147483648")

    @commands.command(
        name='Random topic',
        description="Gives you a random topic to discuss.",
        brief="Gives you a random topic to discuss.",
        aliases=['topic'],
        help=f'{COMMAND_SYMBOL}topic',
        pass_ctx=True)
    async def topic(self, ctx: Context):
        topic_to_discuss = random.choice(TOPICS)
        await ctx.send(f"You should discuss... `{topic_to_discuss}` ...Go!")

    @commands.command(
        name='Highlight phrase',
        description="Toggles a highlight notifier for you.",
        brief="Toggles a highlight notifier for you.",
        aliases=['highlight', 'hilight'],
        help=f'{COMMAND_SYMBOL}highlight <phrase>',
        pass_ctx=True)
    async def highlight(self, ctx: Context, *, phrase: str):
        added = self.bot.save_data.highlights.toggle_highlight(ctx.author.id, phrase)
        if added:
            no_space_warning = "" if '\\b' in phrase else \
                "Note: your phrase doesn't have \\b in it, so will match inside words. " \
                "Use \\b for boundary if you don't want this."
            await ctx.send(f"You are now watching `{added}`. {no_space_warning}")
        else:
            await ctx.send(f"You are no longer watching `{phrase}`.")
        await self.bot.save_data.save(ctx)
