import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands
from discord.ext.commands import Bot, CommandNotFound, UserInputError, MissingRequiredArgument, Context

from src.squidge.cogs.bot_util_commands import BotUtilCommands


class SquidgeBot(Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = False  # We don't need this just yet, but we may do for roles/auth in the future
        intents.presences = False
        intents.typing = False
        super().__init__(
            command_prefix=None,
            intents=intents
        )

        # Load Cogs
        self.try_add_cog(BotUtilCommands)

    def try_add_cog(self, cog: commands.cog):
        try:
            new_cog = cog(self)
            self.add_cog(new_cog)
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
            if message.author.id.__str__() == "508484047383691264":
                message_to_send = await self.wiki_notifier_commands.handle_webhook(message)
                await message.channel.send(message_to_send)
            return

        # Process the message in the normal way
        ctx = await self.get_context(message)
        await self.invoke(ctx)
        ###

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name}, id {self.user.id}')

        # noinspection PyUnreachableCode
        if __debug__:
            logging.getLogger().setLevel(level="DEBUG")
            presence = "--=IN DEV=--"
        else:
            presence = "in the cloud ⛅"

        if 'pydevd' in sys.modules or 'pdb' in sys.modules or '_pydev_bundle.pydev_log' in sys.modules:
            presence += ' (Debug Attached)'

        await self.change_presence(activity=discord.Game(name=presence))

    def do_the_thing(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            asyncio.gather(
                self.start(os.getenv("DISCORD_BOT_TOKEN"))
            )
        )
