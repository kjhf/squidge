from typing import Optional, Sequence

from discord import Guild, Role, Member
from discord.app_commands import commands


async def get_members(guild: Guild, role: Optional[Role] = None) -> Sequence[Member]:
    await conditional_perform_fetch(guild)
    if role:
        return [member for member in guild.members if role in member.roles]
    return guild.members


def has_role(user: Member, role: Optional[str] = "everyone"):
    return (role or "everyone").lstrip('@').__str__() in get_formatted_user_roles(user)


def get_formatted_user_roles(user: Member):
    return (f"{r.__str__().lstrip('@')}" for r in user.roles)


async def check_guild(ctx):
    guild: Optional[Guild] = ctx.guild
    if guild:
        return True
    # else
    await ctx.send("⛔ We're not in a server!")
    return False


async def conditional_perform_fetch(guild: Guild):
    if len(guild.roles) < 2 or len(guild.members) < 2:
        await guild.fetch_roles()
        guild.fetch_members(limit=None)
