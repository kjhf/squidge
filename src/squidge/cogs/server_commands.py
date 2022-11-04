"""Server-affecting admin/mod commands cog."""
from typing import Optional

from discord import Role, Member
from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.discordsupport.discord_server_helper import check_guild, get_members, conditional_perform_fetch, \
    has_role, get_formatted_user_roles
from src.squidge.discordsupport.format_helper import truncate
from src.squidge.entry.consts import COMMAND_SYMBOL


class ServerCommands(commands.Cog):
    """A grouping of server-affecting admin/mod commands."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name='CountMembers',
        description="Count number of members with a role specified, or leave blank for all in the server.",
        brief="Member counting.",
        aliases=['members', 'count_members'],
        help=f'{COMMAND_SYMBOL}members [role]',
        pass_ctx=True)
    async def count_members(self, ctx: Context, role: Optional[Role]):
        if not await check_guild(ctx):
            return

        await conditional_perform_fetch(ctx.guild)
        if not await self._check_author_permission(ctx):
            return

        for role in [role] if role else ctx.guild.roles:
            guild_members = await get_members(ctx.guild, role)
            message = ", ".join([member.__str__() for member in guild_members])
            message = truncate(f"{len(guild_members)}/{ctx.guild.member_count} users in server with {role.name}!\n{message}")
            await ctx.send(message)

    @commands.command(
        name='GetRoles',
        description="Get all the roles this server member has.",
        brief="Roles for a User.",
        aliases=['roles', 'getroles', 'get_roles'],
        help=f'{COMMAND_SYMBOL}roles [member]',
        pass_ctx=True)
    async def get_roles(self, ctx: Context, user: Optional[Member]):
        if not await check_guild(ctx):
            return

        await conditional_perform_fetch(ctx.guild)
        if not await self._check_author_permission(ctx):
            return

        if not user:
            user = ctx.author
        roles = [f"{r.__str__()}".replace("@", "") for r in user.roles]
        await self.print_roles(ctx, roles)

    @commands.command(
        name='HasRole',
        description="Get if the user has a role.",
        brief="Get if the user has a role",
        aliases=['hasrole', 'has_role', 'has_role_command'],
        help=f'{COMMAND_SYMBOL}hasrole <role> [member]',
        pass_ctx=True)
    async def has_role_command(self, ctx: Context, role: str, user: Optional[Member]):
        if not await check_guild(ctx):
            return

        await conditional_perform_fetch(ctx.guild)
        if not await self._check_author_permission(ctx):
            return

        result = has_role(user or ctx.author, role)
        await ctx.send(f"{user.display_name} has {role}!" if result else f"{user.display_name} does not have {role}!")

        if not result:
            await self.print_roles(ctx, get_formatted_user_roles(user))

    @staticmethod
    async def print_roles(ctx, roles):
        await ctx.send(', '.join([f"`{r}`" for r in roles]))

    @staticmethod
    async def _check_author_permission(ctx):
        if not ctx.author.guild_permissions.manage_roles:
            await ctx.send("⛔ You need Manage Roles permission for this command.")
            return False
        # else
        return True
