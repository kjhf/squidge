"""Nintendo Independent Wiki Alliance (NIWA) link cog."""
import json
from io import BytesIO
from typing import TypedDict, Optional

import discord
import requests
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.discordsupport.pagination_view import PaginationView
from src.squidge.discordsupport.slash_compat import defer_if_interaction, send_or_edit
from src.squidge.entry.SquidgeBot import SquidgeBot
from src.squidge.savedata.niwa_permissions import NIWAPermissions

WOB_JSON_LINK = "https://raw.githubusercontent.com/invalidCards/WikiOperatingBuddy/master/_wikis.json"
WIKI_LOOKUP_JSON_LINK = "https://raw.githubusercontent.com/GameWikis/WikiLookup/master/WikiLookup.json"


class WLWiki(TypedDict):
    """Wiki Lookup Wiki"""
    name: str
    homepage: str
    lang: str
    api: str
    companies: Optional[list[str]]
    games: Optional[list[str]]
    genres: Optional[list[str]]
    series: Optional[list[str]]
    systems: Optional[list[str]]


class WOBWiki(TypedDict):
    """Wiki Operating Buddy Wiki"""
    key: str
    name: str
    url: str
    articleUrl: str
    aliases: list[str]
    setOnly: list[str]


class NIWALinkCommands(commands.Cog):
    wob_wikis: list[WOBWiki]
    wl_wikis: list[WLWiki]

    def __init__(self, bot):
        self.bot = bot
        self.wob_wikis = []
        self.wl_wikis = []
        super().__init__()

    @property
    def permissions(self) -> NIWAPermissions:
        return self.bot.save_data.niwa_permissions

    @app_commands.describe(name="The wiki's full display name. If it includes spaces you may use _ or quotes around it \"full name\"")
    @app_commands.describe(homepage="The wiki's homepage URL, e.g. https://examplewiki.com/wiki/Main_Page")
    @app_commands.describe(lang='The wiki code / MediaWiki language, e.g. en.')
    @app_commands.describe(api="Full URL to the wiki's api file, e.g. https://examplewiki.com/w/api.php")
    # @app_commands.describe(companies="Optional: the companies covered by the wiki.")
    # @app_commands.describe(games="Optional: the games covered by the wiki.")
    # @app_commands.describe(genres="Optional: the genres covered by the wiki.")
    # @app_commands.describe(series="Optional: the series covered by the wiki.")
    # @app_commands.describe(systems="Optional: the systems covered by the wiki.")
    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wl_add',
        description="Add a wiki to the local configured list.")
    async def wl_add(self, ctx: Context, name: str, homepage: str, lang: str, api: str):
        await defer_if_interaction(ctx)
        message = ""
        name = name.replace('_', ' ')

        if not self.wl_wikis:
            message += "⚠ WARNING: You are adding to a currently empty list. Use wl_pull.\n"

        if any(wiki["name"] == name for wiki in self.wl_wikis):
            message += f"❌ WARNING: Your new name={name} is non-unique.\n"

        self.wl_wikis.append(
            WLWiki(name=name, homepage=homepage, lang=lang, api=api,
                   companies=[], games=[], genres=[], series=[], systems=[])
        )
        message += \
            "✅ Added successfully. Use `wl_option " + name + " parameter value1 value2...` to add additional optional fields. " \
            "Use wl_dump when you're done."
        await send_or_edit(ctx, message)

    @app_commands.describe(name="The wiki's name to amend")
    @app_commands.describe(option="The option to add. Can be companies, games, genres, series, systems.")
    @app_commands.describe(values='The things to add as a space (and optional comma) separated list.')
    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wl_option',
        description="Add optionals to an added wiki")
    async def wl_option(self, ctx: Context, name: str, option: str, *, values: str):
        await defer_if_interaction(ctx)
        message = ""
        name = name.replace('_', ' ')

        if not self.wl_wikis:
            message += "❌ ERROR: Empty list. Use wl_pull.\n"
        else:
            wiki = next((wiki for wiki in self.wl_wikis if wiki["name"].lower() == name.lower()), None)
            if wiki:
                option_lower = option.lower()
                new_values = [val.strip("\'\" ") for val in dict.fromkeys(values.split(','))]
                if option_lower == "companies":
                    wiki["companies"] = new_values
                    message += "✅ Added companies successfully. Use wl_dump when you're done."
                elif option_lower == "games":
                    wiki["games"] = new_values
                    message += "✅ Added games successfully. Use wl_dump when you're done."
                elif option_lower == "genres":
                    wiki["genres"] = new_values
                    message += "✅ Added genres successfully. Use wl_dump when you're done."
                elif option_lower == "series":
                    wiki["series"] = new_values
                    message += "✅ Added series successfully. Use wl_dump when you're done."
                elif option_lower == "systems":
                    wiki["systems"] = new_values
                    message += "✅ Added systems successfully. Use wl_dump when you're done."
                else:
                    message += "❌ ERROR: The option you specified is not recognised. Use: `companies`, `games`, `genres`, `series`, `systems`\n"
            else:
                message += "❌ ERROR: Wiki not found with that name.`\n"
        await send_or_edit(ctx, message)

    @app_commands.describe(key='Key to file the wiki under. This must be unique across all wikis that WikiLookup supports.')
    @app_commands.describe(name="The wiki's full display name")
    @app_commands.describe(url="The wiki's base url for the API, e.g. https://examplewiki.com/w")
    @app_commands.describe(article_url="The wiki's base article url for pages, e.g. https://examplewiki.com/wiki")
    @app_commands.describe(aliases="The aliases to invoke the WOB for this wiki. Give as a space (or comma and space) separated list.")
    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_add',
        description="Add a wiki to the local configured list.")
    async def wob_add(self, ctx: Context, key: str, name: str, url: str, article_url: str, *, aliases: str):
        await defer_if_interaction(ctx)
        message = ""
        name = name.replace('_', ' ')

        if not self.wob_wikis:
            message += "⚠ WARNING: You are adding to a currently empty list. Use wob_pull.\n"

        if any(wiki["key"] == key for wiki in self.wob_wikis):
            message += "❌ WARNING: Your new key is non-unique.\n"

        new_aliases = list(dict.fromkeys(aliases.replace(',', '').split(' ')))

        if any(len(set(wiki["aliases"]) & set(new_aliases)) > 0 for wiki in self.wob_wikis):
            message += "❌ WARNING: Your new alias(es) are non-unique.\n"

        self.wob_wikis.append(
            WOBWiki(key=key, name=name, url=url, articleUrl=article_url, aliases=new_aliases, setOnly=[])
        )
        message += "✅ Added successfully. Use wl_pull when you're done."
        await send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wl_dump',
        description="Dump the local Wiki Lookup configured wikis to JSON")
    async def wl_dump(self, ctx: Context):
        await defer_if_interaction(ctx)
        message = ""

        if self.wl_wikis:
            bytes_buffer = BytesIO(json.dumps(self.wl_wikis).encode())
            if ctx.interaction:
                await ctx.interaction.edit_original_response(attachments=[discord.File(bytes_buffer, filename="WikiLookup.json", description="WikiLookup wikis")])
            else:
                await ctx.send(file=discord.File(bytes_buffer, filename="WikiLookup.json", description="WikiLookup wikis"))
        else:
            message += "❌ Nothing to dump. Use wl_pull.\n"
            await send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_dump',
        description="Dump the local configured wikis to JSON")
    async def wob_dump(self, ctx: Context):
        await defer_if_interaction(ctx)
        message = ""

        if self.wob_wikis:
            bytes_buffer = BytesIO(json.dumps(self.wob_wikis).encode())
            if ctx.interaction:
                await ctx.interaction.edit_original_response(attachments=[discord.File(bytes_buffer, filename="_wikis.json", description="WikiOperatingBuddy _wikis")])
            else:
                await ctx.send(file=discord.File(bytes_buffer, filename="_wikis.json", description="WikiOperatingBuddy _wikis"))
        else:
            message += "❌ Nothing to dump. Use wob_pull.\n"
            await send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wl_pull',
        description="Pulls the current JSON from WikiLookup (WL).")
    async def wl_pull(self, ctx: Context):
        await defer_if_interaction(ctx)
        message = ""

        try:
            if self.wl_wikis:
                message += "⚠ WARNING: Overwriting previously pulled wikis list. \n"

            self.wl_wikis: list[WLWiki] = requests.get(WIKI_LOOKUP_JSON_LINK, timeout=(6.1, 12)).json()
            message += f"ℹ {len(self.wl_wikis)} wikis loaded."
        except Exception as err:
            message += "❌ Error: " + str(err.args)
        await send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_pull',
        description="Pulls the current JSON from Wiki Operating Bot (WOB).")
    async def wob_pull(self, ctx: Context):
        await defer_if_interaction(ctx)
        message = ""

        try:
            if self.wob_wikis:
                message += "⚠ WARNING: Overwriting previously pulled wikis list. \n"

            self.wob_wikis: list[WOBWiki] = requests.get(WOB_JSON_LINK, timeout=(6.1, 12)).json()
            message += f"ℹ {len(self.wob_wikis)} wikis loaded."
        except Exception as err:
            message += "❌ Error: " + str(err.args)
        await send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wl_status',
        description="Begins an embed that displays the wikis currently configured locally.")
    async def wl_status(self, ctx: Context):
        await defer_if_interaction(ctx)
        message = ""
        if self.wl_wikis:
            try:
                fields = []
                for wiki in self.wl_wikis:
                    fields_per_wiki = {
                        "name": wiki["name"],
                        "homepage": wiki["homepage"],
                        "lang": wiki["lang"],
                        "api": wiki["api"],
                        "companies": ', '.join(wiki.get("companies", [])),
                        "games": ', '.join(wiki.get("games", [])),
                        "genres": ', '.join(wiki.get("genres", [])),
                        "series": ', '.join(wiki.get("series", [])),
                        "systems": ', '.join(wiki.get("systems", []))
                    }
                    fields.append(fields_per_wiki)
                context_to_use = ctx.interaction if ctx.interaction else ctx
                view = PaginationView("Wikis supported by WikiLookup",
                                      fields, fields_per_page=9)
                await view.send(context_to_use)

            except Exception as err:
                print(err)
                message += "❌ Error: " + str(err.args)
                await send_or_edit(ctx, message)
        else:
            message += "❌ Nothing to show. Use wl_pull.\n"
            await send_or_edit(ctx, message)

    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    @commands.hybrid_command(
        name='wob_status',
        description="Begins an embed that displays the wikis currently configured locally.")
    async def wob_status(self, ctx: Context):
        await defer_if_interaction(ctx)
        message = ""
        if self.wob_wikis:
            try:
                fields = []
                for wiki in self.wob_wikis:
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
                message += "❌ Error: " + str(err.args)
                await send_or_edit(ctx, message)
        else:
            message += "❌ Nothing to show. Use wob_pull.\n"
            await send_or_edit(ctx, message)
