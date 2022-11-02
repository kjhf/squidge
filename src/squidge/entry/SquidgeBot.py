import asyncio
import logging
import os
import sys
from typing import List

import discord
from discord.ext import commands
from discord.ext.commands import Bot, CommandNotFound, UserInputError, MissingRequiredArgument, Context

from src.squidge.cogs.bot_util_commands import BotUtilCommands
from src.squidge.cogs.wiki_commands import WikiCommands
from src.squidge.entry.consts import COMMAND_SYMBOL


class SquidgeBot(Bot):

    def __init__(self):
        self.wiki_commands = None
        self.presence = ""
        intents = discord.Intents.default()
        intents.members = True  # Needed to call fetch_members for username & tag recognition (grant/deny)
        intents.message_content = True
        intents.presences = False
        intents.typing = False
        super().__init__(
            command_prefix=COMMAND_SYMBOL,
            intents=intents
        )

    @staticmethod
    def squidge_guilds() -> List[discord.Object]:
        return [discord.Object(id=1020502841544151141), discord.Object(id=770990831569862656)]

    async def setup_hook(self) -> None:
        # Load cogs here; must be done before on_ready
        # noinspection PyUnreachableCode
        if __debug__:
            logging.getLogger().setLevel(level="DEBUG")
            self.presence = "--=IN DEV=-- (use " + COMMAND_SYMBOL + ")"
        else:
            self.presence = "in the cloud ⛅ (use " + COMMAND_SYMBOL + ")"
        if 'pydevd' in sys.modules or 'pdb' in sys.modules or '_pydev_bundle.pydev_log' in sys.modules:
            self.presence += ' (Debug Attached)'

        # Load Cogs
        await self.try_add_cog(BotUtilCommands)
        self.wiki_commands = await self.try_add_cog(WikiCommands)

        from src.squidge.cogs.wiki_slash_commands import WikiSlashCommands
        _ = await self.try_add_cog(WikiSlashCommands)

        # Sync slash commands
        assert self.tree.get_commands(), "No commands were registered"
        for guild in SquidgeBot.squidge_guilds():
            self.tree.copy_global_to(guild=guild)

    async def try_add_cog(self, cog: commands.cog):
        try:
            new_cog = cog(self)
            await self.add_cog(new_cog)
            return new_cog
        except Exception as e:
            logging.error(f"Failed to load {cog=}: {e=}")

    async def on_command_error(self, ctx: Context, error, **kwargs):
        if isinstance(error, CommandNotFound):
            return
        elif isinstance(error, UserInputError):
            await ctx.send(error.__str__())
        elif isinstance(error, MissingRequiredArgument):
            await ctx.send(error.__str__())
        else:
            raise error

    async def on_message(self, message: discord.Message, **kwargs):
        # We do not want the bot to reply to itself
        if message.author == self.user:
            return

        # If it's the WikiNotifier bot, do stuff.
        # else, don't respond to bot messages.
        if message.author.bot:
            # If WikiNotifier
            if message.author.id.__str__() == "1027464071362121728":
                # If #recent-changes channel in Inkipedia
                if message.channel.id.__str__() == "1020516169146454037":
                    message_to_send = await self.wiki_commands.handle_inkipedia_event(message)
                    if message_to_send:
                        # Reply in #squidge-alerts
                        bot_spam = message.channel.guild.get_channel(1033866281549582376)
                        await bot_spam.send(message_to_send)
            return

        # Process the message in the normal way
        ctx = await self.get_context(message)
        await self.invoke(ctx)
        ###

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name}, id {self.user.id}')
        await self.change_presence(activity=discord.Game(name=self.presence))

    def do_the_thing(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            asyncio.gather(
                self.start(os.getenv("DISCORD_BOT_TOKEN"))
            )
        )
