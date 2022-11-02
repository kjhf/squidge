"""Wiki commands that use slash commands cog."""
import logging
from typing import Tuple

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord.ui import View

from src.squidge.entry.SquidgeBot import SquidgeBot


class YesNoView(View):
    def __init__(self, bot: 'SquidgeBot', args: Tuple[str, str, str, str]):
        """Constructor for YesNoView"""
        super().__init__()
        logging.debug("Created YesNo view")
        self.bot = bot
        self.category_no_ns, self.operation, self.namespace, self.rule_title = args

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green, emoji="👍")
    async def ok_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.squidge.cogs.wiki_commands import WikiCommands
        logging.debug(f"OK clicked, button={button!r}, interation={interaction!r}")
        wiki: WikiCommands = self.bot.wiki_commands
        await interaction.edit_original_response(
            content=f"Working on it! "
                    f"Adding `Category:{self.category_no_ns}` to {self.namespace or 'article'} page titles that {self.operation} `{self.rule_title}`.")
        await wiki.add_categories_with_perm_check(interaction, self.category_no_ns, self.operation, self.namespace, self.rule_title)
        await interaction.edit_original_response(
            content=f"Finished adding `Category:{self.category_no_ns}` to {self.namespace or 'article'} page titles that {self.operation} `{self.rule_title}`."
                    f"\nContribs: <https://splatoonwiki.org/wiki/Special:Contributions/SquidgeBot>")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="🗑️")
    async def cancel_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        logging.debug(f"Cancel clicked, button={button!r}, interation={interaction!r}")
        await interaction.delete_original_response()
        self.stop()


class WikiSlashCommands(commands.GroupCog, name="squidge"):
    """A grouping of wiki slash commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logging.debug("WikiSlashCommands constructed")
        super().__init__()

    @commands.hybrid_command(name="ping")
    async def ping_command(self, ctx: commands.Context) -> None:
        """
        This command is actually used as an app command AND a message command.
        This means it is invoked with `~ping` and `/ping` (once synced, of course).
        We use `ctx.send` and this will handle both the message command and app command of sending.
        Added note: you can check if this command is invoked as an app command by checking the `ctx.interaction` attribute.
        """
        await ctx.send("Hello!")

    @app_commands.command(name="add_category", description="Manipulate categories on the wiki")
    @app_commands.describe(operation='What is the operation? Page titles that ...')
    @app_commands.choices(operation=[
        Choice(name='are named', value="are named"),
        Choice(name='start with', value="start with"),
        Choice(name='end with', value="end with"),
        Choice(name='contain', value="contain"),
    ])
    @app_commands.describe(rule_argument="What is the page title or fragment that you're looking for?")
    @app_commands.describe(category="The category to add")
    @app_commands.guilds(*SquidgeBot.squidge_guilds())
    async def add_categories(self, interaction: discord.Interaction, operation: Choice[str], rule_argument: str, category: str):
        logging.debug("Add categories invoked")
        if category.lower().startswith("category:"):
            category = category[len("category:"):]
        category_no_ns = category.replace('_', ' ')

        (namespace, sep, title) = rule_argument.partition(':')
        if not sep:
            title = namespace
            namespace = None

        title = title.replace('_', ' ')
        await interaction.response.send_message(
            f"Add `Category:{category_no_ns}` to {namespace or 'article'} page titles that {operation.value} `{title}`. Does that look correct?",
            view=YesNoView(self.bot, (category_no_ns, operation.name, namespace, title)), ephemeral=True)
