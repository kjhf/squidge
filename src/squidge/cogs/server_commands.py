"""Server-affecting admin/mod commands cog."""
from typing import Optional, Union

import discord
from discord import Role, Member, Guild
from discord.ext import commands
from discord.ext.commands import Context

from src.squidge.discordsupport.discord_server_helper import check_guild, get_members, conditional_perform_fetch, \
    has_role, get_formatted_user_roles
from src.squidge.discordsupport.format_helper import truncate
from src.squidge.entry.consts import COMMAND_SYMBOL, BOT_NAME


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

    @commands.command(
        name='ColourMe',
        description="Give the user a coloured role.",
        brief="Give the user a coloured role.",
        aliases=['colorme', 'colourme', 'color_me', 'colour_me'],
        help=f'{COMMAND_SYMBOL}colourme [_colour_|random|remove]. The colour may be a common English name or hex code.',
        pass_ctx=True)
    async def colour_me(self, ctx: Context, *, colour_str: Optional[str]):
        if ctx.guild.id != 1131847158610534400:  # awkward's goo lagoon
            return

        if not colour_str:
            await ctx.send_help(self.colour_me)
            return

        colour: Optional[discord.Colour] = None
        colour_str = colour_str.strip('#').replace(" ", "_").lower()

        # First, test if the colour was given as three separate numbers
        parts = colour_str.split('_')
        if len(parts) == 3:
            # Assume hex, unless any numbers are above 3 digits.
            try:
                if any((len(s) == 3 for s in parts)):
                    hit = [int(part) for part in parts]
                else:
                    hit = [int(part, 16) for part in parts]
            except (ValueError, IndexError, TypeError):
                pass
            else:
                colour = discord.Colour.from_rgb(*hit)

        try:
            # First try some missing colours from discord's library
            lookup = {
                "aqua":       [190, 211, 229],
                "beige":      [245, 245, 220],
                "black":        [0,   0,   1],
                "brown":      [153, 102,  51],
                "cyan":         [0, 255, 255],
                "generic":      [0, 153, 255],  # Inkipedia
                "grello":     [170, 220,   0],  # Inkipedia
                "indigo":     [111,   0, 255],
                "lime":       [191, 255,   0],
                "maroon":     [128,   0,   0],
                "niwa":       [255, 128,   0],  # Inkipedia
                "octo":       [174,  21, 102],  # Inkipedia
                "olive":      [128, 128,   0],
                "peach":      [255, 229, 180],
                "pink":       [255, 192, 203],
                "salmon":     [255, 128, 128],
                "silver":     [192, 192, 192],
                "splatoon":   [170, 220,   0],  # Inkipedia
                "splatoon_2": [240,  60, 120],  # Inkipedia
                "splatoon_3": [235, 238,  61],  # Inkipedia
                "tan":        [210, 180, 140],
                "turquoise":   [64, 224, 208],
                "violet":     [143,   0, 255],
                "white":      [255, 255, 255],
                "yellow":     [255, 255,   0],

                # Special
                "remove": [0, 0, 0],
            }
            hit = lookup.get(colour_str, None)

            if hit is None:
                # Get from discord's library (including random())
                colour = getattr(discord.Colour, colour_str)()
            else:
                colour = discord.Colour.from_rgb(hit[0], hit[1], hit[2])

        except AttributeError:
            # Try parse a hex-code
            try:
                if len(colour_str) == 6:
                    colour = discord.Colour.from_rgb(
                        int(colour_str[0:2], 16),
                        int(colour_str[2:4], 16),
                        int(colour_str[4:6], 16))
                elif len(colour_str) == 3:
                    colour = discord.Colour.from_rgb(
                        int(f"{colour_str[0]}{colour_str[0]}", 16),
                        int(f"{colour_str[1]}{colour_str[1]}", 16),
                        int(f"{colour_str[2]}{colour_str[2]}", 16))
            except (ValueError, IndexError, TypeError):
                pass

        if not isinstance(colour, discord.Colour):
            await ctx.send("I didn't understand your colour. "
                           "Please specify an English colour, `random`, or a 3-digit or 6-digit hex code")
            return

        guild: Optional[Guild] = ctx.guild
        if guild:
            if not guild.me.guild_permissions.manage_roles:
                await ctx.send("I can't do that as I don't have the manage roles permission.")
                return

            await ctx.guild.fetch_roles()
            ctx.guild.fetch_members(limit=None)
            user: Union[discord.User, discord.Member] = ctx.author
            user_colour_roles = [r for r in user.roles if r.__str__().startswith(BOT_NAME + '_')]
            request_role_name = f'{BOT_NAME}_{colour.value}'
            matched_guild_role = next((r for r in guild.roles if r.__str__().lstrip('@') == request_role_name), None)

            # If the user has colour roles already, remove it
            if user_colour_roles:
                for role in user_colour_roles:
                    await user.remove_roles(role, reason=f"{BOT_NAME} (Requested change by {user.id})")

            # Remove roles that no longer have any users
            for role in user_colour_roles:
                if not any(True for user in guild.members if role in user.roles):
                    await role.delete(reason=f"{BOT_NAME} (No more users with this role)")

            # Add the requested role to the user
            if colour != discord.Colour.default():
                if matched_guild_role:
                    await user.add_roles(matched_guild_role, reason=f"{BOT_NAME} (Requested by {user.id}")
                else:
                    try:
                        new_role = await guild.create_role(name=request_role_name,
                                                           reason=f"Requested by {user.id}",
                                                           colour=colour)
                        nitro_role = next((r for r in guild.roles if r.is_premium_subscriber()), None)

                        # Base the new role's position on the nitro role position, otherwise given bottom is 0,
                        # setting to be above "everyone" at 0, and the lowest role and automatic role e.g. Nitro.
                        nitro_role_position = nitro_role.position if nitro_role else 4
                        await new_role.edit(position=nitro_role_position)
                        await user.add_roles(new_role, reason=f"{BOT_NAME} (Requested by {user.id}")
                    except discord.errors.HTTPException:
                        await ctx.send("Discord rejected your request... did you give me a bad value?")
        else:
            await ctx.send("Hmm... we're not in a server! 😅")

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
