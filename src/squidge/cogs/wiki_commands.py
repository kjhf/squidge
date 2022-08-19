"""Bot Utility commands cog."""
import os

from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.entry.consts import COMMAND_SYMBOL


class BotUtilCommands(commands.Cog):
    """A grouping of bot utility commands."""

    def __init__(self, bot):
        self.bot = bot

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
        await ctx.send(f"https://discordapp.com/oauth2/authorize?client_id={os.getenv('DISCORD_BOT_CLIENT_ID')}&scope=bot")
