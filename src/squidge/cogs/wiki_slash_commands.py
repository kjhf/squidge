"""Wiki commands that use slash commands cog."""
from typing import Optional, Tuple

import discord
from discord import app_commands, ui
from discord.app_commands import CommandTree, commands, Choice
from discord.ext import commands
from discord.ui import Button, View


class YesNoView(View):
    def __init__(self, bot: 'SquidgeBot', args: Tuple[str, str, str, str]):
        """Constructor for YesNoView"""
        super().__init__()
        self.bot = bot
        self.category_no_ns, self.operation, self.namespace, self.rule_title = args

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green, emoji="✔")
    async def button_callback(self, button, interation: discord.Interaction):
        from src.squidge.cogs.wiki_commands import WikiCommands
        wiki: WikiCommands = self.bot.wiki_commands
        self.stop()
        await wiki.add_categories_with_perm_check(interation, self.category_no_ns, self.operation, self.namespace, self.rule_title)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def button_callback(self, button, interation):
        self.stop()


class WikiSlashCommands(commands.Cog):
    """A grouping of wiki slash commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="add_category", description="Manipulate categories on the wiki")
    @app_commands.describe(operation='What is the operation? Pages that ...')
    @app_commands.choices(operation=[
        Choice(name='equal', value="are named"),
        Choice(name='starts', value="start with"),
        Choice(name='ends', value="end with"),
        Choice(name='contains', value="contain"),
    ])
    @app_commands.describe(rule_argument="What is the pattern of the page you're looking for?")
    @app_commands.describe(category="The category to add")
    @app_commands.guilds(discord.Object(id=1020502841544151141), discord.Object(id=770990831569862656))
    async def add_categories(self, interaction: discord.Interaction, operation: Choice[str], rule_argument: str, category: str):
        if category.lower().startswith("category:"):
            category = category[len("category:"):]
        category_no_ns = category.replace('_', ' ')

        (namespace, sep, title) = rule_argument.partition(':')
        if not sep:
            title = namespace
            namespace = None

        title = title.replace('_', ' ')
        await interaction.response.send_message(
            f"Add `Category:{category_no_ns}` to {namespace or 'article'} pages that {operation.value} `{title}`. Does that look correct?",
            view=YesNoView(self.bot, (category_no_ns, operation.name, namespace, title)))

        await self.bot.wait_for("on_add_categories_button_click", timeout=10)
