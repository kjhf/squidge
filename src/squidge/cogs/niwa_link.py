"""Nintendo Independent Wiki Alliance (NIWA) link cog."""
import json
from io import BytesIO
from typing import TypedDict

import discord
import requests
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.discordsupport.pagination_view import PaginationView
from src.squidge.entry.SquidgeBot import SquidgeBot
from src.squidge.savedata.niwa_permissions import NIWAPermissions

WIKIS_JSON_LINK = "https://raw.githubusercontent.com/invalidCards/WikiOperatingBuddy/master/_wikis.json"


class WOBWiki(TypedDict):
    key: str
    name: str
    url: str
    articleUrl: str
    aliases: list[str]
    setOnly: list[str]


class NIWALinkCommands(commands.Cog):
    wikis: list[WOBWiki]

    def __init__(self, bot):
        self.bot = bot
        self.wikis = []
        super().__init__()

    @property
    def permissions(self) -> NIWAPermissions:
        return self.bot.save_data.niwa_permissions

    @app_commands.describe(key='Key to file the wiki under. This must be unique across all wikis that WOB supports.')
    @app_commands.describe(name="The wiki's full display name")
    @app_commands.describe(url="The wiki's base url for the API, e.g. https://examplewiki.com/w")
    @app_commands.describe(article_url="The wiki's base article url for pages, e.g. https://examplewiki.com/wiki")
    @app_commands.describe(aliases="The aliases to invoke the WOB for this wiki. Give as a space (or comma and space) separated list.")
    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_add',
        description="Add a wiki to the local configured list.")
    async def wob_add(self, ctx: Context, key: str, name: str, url: str, article_url: str, *, aliases: str):
        await self._defer_if_interaction(ctx)
        message = ""

        if not self.wikis:
            message = "⚠ WARNING: You are adding to a currently empty list. Use wob_pull.\n"

        if any(wiki["key"] == key for wiki in self.wikis):
            message = "❌ WARNING: Your new key is non-unique.\n"

        new_aliases = set(aliases.replace(',', '').split(' '))
        if any(len(set(wiki["aliases"]) & new_aliases) > 0 for wiki in self.wikis):
            message = "❌ WARNING: Your new alias(es) are non-unique.\n"

        self.wikis.append(
            WOBWiki(key=key, name=name, url=url, articleUrl=article_url, aliases=list(new_aliases), setOnly=[])
        )
        message += "✅ Added successfully. Use wob_dump when you're done."
        await self._send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_dump',
        description="Dump the local configured wikis to JSON")
    async def wob_dump(self, ctx: Context):
        await self._defer_if_interaction(ctx)
        message = ""

        if self.wikis:
            bytes_buffer = BytesIO(json.dumps(self.wikis).encode())
            if ctx.interaction:
                await ctx.interaction.edit_original_response(attachments=[discord.File(bytes_buffer, filename="_wikis.json", description="WikiOperatingBuddy _wikis")])
            else:
                await ctx.send(file=discord.File(bytes_buffer, filename="_wikis.json", description="WikiOperatingBuddy _wikis"))
        else:
            message = "❌ Nothing to dump. Use wob_pull.\n"
            await self._send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_pull',
        description="Pulls the current JSON from Wiki Operating Bot (WOB).")
    async def wob_pull(self, ctx: Context):
        await self._defer_if_interaction(ctx)
        message = ""

        try:
            if self.wikis:
                message += "⚠ WARNING: Overwriting previously pulled wikis list. \n"

            self.wikis: list[WOBWiki] = requests.get(WIKIS_JSON_LINK, timeout=(6.1, 12)).json()
            message += f"ℹ {len(self.wikis)} wikis loaded."
        except Exception as err:
            message = "❌ Error: " + str(err.args)
        await self._send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_status',
        description="Begins an embed that displays the wikis currently configured locally.")
    async def wob_status(self, ctx: Context):
        await self._defer_if_interaction(ctx)
        if self.wikis:
            try:
                fields = []
                for wiki in self.wikis:
                    fields_per_wiki = {
                        "key": wiki["key"],
                        "name": wiki["name"],
                        "url": wiki["url"],
                        "articleUrl": wiki["articleUrl"],
                        "aliases": ', '.join(wiki["aliases"])
                    }
                    fields.append(fields_per_wiki)
                context_to_use = ctx.interaction if ctx.interaction else ctx
                view = PaginationView("Wikis supported by Wiki Operating Bot",
                                      fields, fields_per_page=5)
                await view.send(context_to_use)

            except Exception as err:
                print(err)
                message = "❌ Error: " + str(err.args)
                await self._send_or_edit(ctx, message)
        else:
            message = "❌ Nothing to show. Use wob_pull.\n"
            await self._send_or_edit(ctx, message)

    @staticmethod
    async def _defer_if_interaction(ctx: Context):
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

    @staticmethod
    async def _send_or_edit(ctx: Context, message: str):
        if ctx.interaction:
            await ctx.interaction.edit_original_response(content=message)
        else:
            await ctx.send(content=message)
