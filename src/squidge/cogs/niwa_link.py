"""Nintendo Independent Wiki Alliance (NIWA) link cog."""
from typing import TypedDict

import requests
from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.entry.consts import COMMAND_SYMBOL

WIKIS_JSON_LINK = "https://raw.githubusercontent.com/invalidCards/WikiOperatingBuddy/master/_wikis.json"


class WOBWiki(TypedDict):
    key: str
    name: str
    url: str
    articleUrl: str
    aliases: list[str]
    setOnly: list[str]


class NIWALinkCommands(commands.Cog):
    lock_flag = False

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @commands.command(
        name='Wob',
        description="Begins a Wizard and submits a pull request for Wiki Operating Bot (WOB).",
        brief="Begins a Wizard and submits a pull request for Wiki Operating Bot (WOB).",
        help=f'{COMMAND_SYMBOL}wob',
        pass_ctx=True)
    async def wob(self, ctx: Context):
        # First, download the JSON currently checked in, and parse it.
        # We must protect if this command is already in-use.
        # Then, begin the wizard.
        # The first page should have a summary.
        # Accepting from here should push the PR, if any changes have been made.
        # There should be an add, remove, and edit button.
        #
        # https://github.com/richardschwabe/discord-bot-2022-course/blob/main/pagination.py

        if not self.lock_flag:
            self.lock_flag = True
            try:
                wikis: list[WOBWiki] = requests.get(WIKIS_JSON_LINK, timeout=(6.1, 12)).json()
                await ctx.send(f"{len(wikis)} wikis loaded.")

            except Exception as err:
                await ctx.send("Error: " + str(err.args))
            finally:
                self.lock_flag = False
        else:
            await ctx.send("Command is in use.")
