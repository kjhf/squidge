"""Bot Utility commands cog."""
import os
import random
from collections import deque
from time import time
from typing import Deque

from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.entry.consts import COMMAND_SYMBOL
from src.squidge.savedata.topics import TOPICS, TOPICS_FR, THROTTLE_TOPICS


class BotUtilCommands(commands.Cog):
    """A grouping of bot utility commands."""
    topic_limiter: Deque[float]
    LIMIT = 180  # 3 mins

    def __init__(self, bot):
        self.bot = bot
        self.topic_limiter = deque(maxlen=3)
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
        await ctx.send(
            f"https://discordapp.com/oauth2/authorize?client_id={os.getenv('DISCORD_BOT_CLIENT_ID')}&scope=bot%20applications.commands&permissions=2147483648")

    @commands.command(
        name='Random topic',
        description="Gives you a random topic to discuss.",
        brief="Gives you a random topic to discuss.",
        aliases=['topic'],
        help=f'{COMMAND_SYMBOL}topic',
        pass_ctx=True)
    async def topic(self, ctx: Context):
        if self._within_limit():
            topic_to_discuss = random.choice(TOPICS)
            await ctx.send(f"You should discuss... `{topic_to_discuss}` ...Go!")
        else:
            topic_to_discuss = random.choice(THROTTLE_TOPICS)
            await ctx.send(topic_to_discuss)

    @commands.command(
        name='Sujet de discussion aléatoire',
        description="Vous donne un sujet de discussion aléatoire.",
        brief="Gives you a random topic to discuss.",
        aliases=['sujet', 'topic_fr'],
        help=f'{COMMAND_SYMBOL}sujet',
        pass_ctx=True)
    async def sujet(self, ctx: Context):
        topic_to_discuss = random.choice(TOPICS_FR)
        await ctx.send(f"Vous devriez discuter... `{topic_to_discuss}` ...C'est parti !")

    def _within_limit(self) -> bool:
        """Check if rate limit has been exceeded."""
        now = time()

        # Remove calls older than time window
        while self.topic_limiter and now - self.topic_limiter[0] > self.LIMIT:
            self.topic_limiter.popleft()

        # Check if we've hit the limit (3 calls within LIMIT)
        if len(self.topic_limiter) >= 3:
            oldest_call = self.topic_limiter[0]
            if now - oldest_call <= self.LIMIT:
                return False

        self.topic_limiter.append(now)
        return True
