"""Wiki commands cog."""
import asyncio
import json
import logging
import re
from itertools import chain
from typing import Optional, Union

import pywikibot.config
import requests
from discord import TextChannel, Message, User, Member

from discord.ext import commands
from discord.ext.commands import Context, Bot
# noinspection PyProtectedMember
from pywikibot import Site, Page, APISite  # APISite used for type hinting
from pywikibot.page import Revision

from src.squidge.entry.consts import COMMAND_SYMBOL

import os

DEFAULT_EDIT = f"[[User:{os.getenv('WIKI_USERNAME')}|Bot edit]] ([[User_talk:{os.getenv('WIKI_USERNAME')}|Something wrong?]])"
EDIT_WITH_AUTHORIZED_BY = f"[[User:{os.getenv('WIKI_USERNAME')}|Bot edit]] authorized by "


# Monkey-patch the input choice
from pywikibot.bot import input_choice
pywikibot.bot.input_choice = lambda: True
input_choice = lambda: True
###


class WikiCommands(commands.Cog):
    """A grouping of wiki commands."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.permissions = {}
        pywikibot.config.usernames['splatoon']['*'] = os.getenv("WIKI_USERNAME")
        pywikibot.config.default_edit_summary = DEFAULT_EDIT
        pywikibot.config.password_file = "../../../.pwd"
        pywikibot.config.put_throttle = 1  # i.e. 1 operation per second throttle

        # Disable the PyTypeChecker here as an APISite is returned from the Site interface.
        # noinspection PyTypeChecker
        self.inkipedia: APISite = Site(code='', fam='splatoon', url="https://splatoonwiki.org")

    async def conditional_load_permissions(self):
        if not self.are_permissions_loaded():
            channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
            last_message: Optional[Message] = (await channel.history(limit=1).flatten())[0]
            if last_message:
                permissions_json = json.loads(last_message.content)
                if "owner" in permissions_json and "admin" in permissions_json and "editor" in permissions_json:
                    self.permissions["owner"] = permissions_json["owner"]
                    self.permissions["admin"] = permissions_json["admin"]
                    self.permissions["editor"] = permissions_json["editor"]
                    self.permissions["patrol"] = permissions_json["patrol"]
                    author: Optional[User] = last_message.author
                    if author.id != self.bot.user.id:
                        # Repost the message so we can edit.
                        await channel.send(json.dumps(permissions_json))
                        logging.info("Permissions loaded and resent!")
                    else:
                        logging.info("Permissions loaded!")
                else:
                    logging.error("WIKI_PERMISSIONS_CHANNEL: loaded json in bad format.")
                    logging.error(permissions_json)
                    return
            else:
                raise RuntimeError("WIKI_PERMISSIONS_CHANNEL has no permissions. Cannot infer owner.")

    def are_permissions_loaded(self):
        return len(self.permissions)

    def _is_editor(self, id: Union[User, Member, str, int]):
        if self._is_admin(id) or self._is_owner(id):
            return True

        elif isinstance(id, str):
            return id in self.permissions["editor"]
        elif isinstance(id, int):
            return id.__str__() in self.permissions["editor"]
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.permissions["editor"]
        else:
            raise TypeError(f"_is_editor id unknown type: {type(id)}")

    def _is_admin(self, id):
        if self._is_owner(id):
            return True

        elif isinstance(id, str):
            return id in self.permissions["admin"]
        elif isinstance(id, int):
            return id.__str__() in self.permissions["admin"]
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.permissions["admin"]
        else:
            raise TypeError(f"_is_admin id unknown type: {type(id)}")

    def _is_owner(self, id):
        if isinstance(id, str):
            return id in self.permissions["owner"]
        elif isinstance(id, int):
            return id.__str__() in self.permissions["owner"]
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.permissions["owner"]
        else:
            raise TypeError(f"_is_owner id unknown type: {type(id)}")

    def _is_patrol(self, id):
        if isinstance(id, str):
            return id in self.permissions["patrol"]
        elif isinstance(id, int):
            return id.__str__() in self.permissions["patrol"]
        elif isinstance(id, User) or isinstance(id, Member):
            return id.id.__str__() in self.permissions["patrol"]
        else:
            raise TypeError(f"_is_patrol id unknown type: {type(id)}")

    async def _get_patrol_pings(self):
        await self.conditional_load_permissions()
        return "".join([f"<@!{i}> " for i in self.permissions["patrol"]])

    @commands.command(
        name='move_category',
        description="Moves a category an updates all references.",
        brief="Moves a category an updates all references.",
        aliases=['recat'],
        help=f'{COMMAND_SYMBOL}move_category <old> <new>',
        pass_ctx=True)
    async def move_category(self, ctx: Context, *, message: str):
        args = message.split(' ')
        if len(args) != 2:
            await ctx.send(f'`{COMMAND_SYMBOL}move_category <old> <new>`. Category names must have underscores.')
            return
        old_category = args[0]
        new_category = args[1]
        await self.conditional_load_permissions()
        if self._is_editor(ctx.author):
            if not old_category.lower().startswith("category"):
                old_category = "Category:" + old_category
            if not new_category.lower().startswith("category"):
                new_category = "Category:" + new_category

            old_category = old_category.replace('_', ' ')
            new_category = new_category.replace('_', ' ')
            summary = "Recategorising `" + old_category + "` to `" + new_category + "`"
            await ctx.send(summary)
            old_cat_page_list = pywikibot.Category(self.inkipedia, old_category)
            if Page(self.inkipedia, new_category).exists():
                await ctx.send(f"Warning: new category already exists. Skipping cat parent move.")
            elif not Page(self.inkipedia, old_category).exists():
                await ctx.send(f"Warning: old category does not exist. Skipping cat parent move.")
            else:
                old_cat_page_list.move(new_category, reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary)
            pages = chain(old_cat_page_list.articles(), old_cat_page_list.subcategories(recurse=True))
            count = 0

            new_cat_page_list = pywikibot.Category(self.inkipedia, new_category)
            for page in pages:
                changed = page.change_category(old_cat_page_list, new_cat_page_list, summary=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary)
                await asyncio.sleep(1)  # yield
                if changed:
                    count += 1
                else:
                    logging.info(f"Cats: {[c.__str__() for c in page.categories()]}")
            await ctx.send(f"Done, {count} page(s) changed.")
        else:
            await ctx.send("You don't have editor permission.")

    @commands.command(
        name='nuke',
        description="Deletes all images uploaded by a user. Reverts all edits made. Blocks.",
        brief="Nuke a user and block them.",
        aliases=['fart'],
        help=f'{COMMAND_SYMBOL}nuke <user>',
        pass_ctx=True)
    async def nuke(self, ctx: Context, *, user: str):
        await self.conditional_load_permissions()
        if self._is_admin(ctx.author):
            # Block the user
            user_to_nuke = pywikibot.User(self.inkipedia, user)
            if user_to_nuke and user_to_nuke.isRegistered(force=True):
                # Sanity check for an established user (> 2 as registered users have '*' and 'user')
                rights = user_to_nuke.groups()
                logging.info(f"Groups returned: {rights}")
                if len(rights) > 2:
                    await ctx.send("Not nuking this user as they have established rights. If you really meant to do this, demote them first.")
                else:
                    if user_to_nuke.is_blocked():
                        await ctx.send("User is already blocked, skipping...")
                    else:
                        user_to_nuke.block(expiry='never',
                                           reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + ": [[Inkipedia:Policy/Vandalism|Vandalism]]"
                                           )

                    # Get all contributions from the user
                    contributions = user_to_nuke.contributions()
                    for contrib in contributions:
                        await asyncio.sleep(1)  # yield
                        page: pywikibot.Page = contrib[0]
                        if page.is_filepage():
                            try:
                                first_revision: Revision = page.oldest_revision
                                logging.info(f"{first_revision.user=} == {user_to_nuke=} ? {first_revision.user == user_to_nuke}")
                                if first_revision.user == user_to_nuke:
                                    page.delete(reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + ": [[Inkipedia:Policy/Vandalism|Vandalism]]")
                                else:
                                    logging.info(f"Reverting page={page.title()}")
                                    self.inkipedia.rollbackpage(page, user=user_to_nuke)
                            except Exception as error:
                                logging.error(error)
                        elif page.lastNonBotUser == user_to_nuke.username:
                            # revert
                            self.inkipedia.rollbackpage(page, user=user_to_nuke)
            else:
                await ctx.send(f"User {user} was not found.")
        else:
            await ctx.send("You don't have admin permission.")

    async def handle_inkipedia_event(self, message: Message) -> Optional[str]:
        if message.embeds:
            embed = message.embeds[0]
            content = embed.title or embed.description
            if content:
                # Scan new pages and new accounts
                emotes_to_check = [":new:", "🆕", ":wave:", "👋", ":outbox_tray:", "📤"]
                if any(emote in content for emote in emotes_to_check):
                    logging.info(f"handle_inkipedia_event: Checking {content}")
                    files = {
                        'text': (None, content),
                        'lang': (None, 'en'),
                        'mode': (None, 'standard'),
                    }
                    response = requests.post('https://api.sightengine.com/1.0/text/check.json', files=files)
                    as_json = response.json()
                    logging.info(as_json)
                    # Check for success
                    status = as_json.get("status")
                    if status == "success":
                        profanity_matches = as_json.get("profanity", {}).get("matches")
                        if profanity_matches:
                            current_level = "low"
                            for match in profanity_matches:
                                if match["intensity"] == "high":
                                    current_level = "high"
                                elif match["intensity"] == "medium" and current_level != "high":
                                    current_level = "medium"

                            if current_level == "low":
                                return f"❓ Possible vandalism. {message.jump_url} " + await self._get_patrol_pings()
                            elif current_level == "medium":
                                return f"⚠ Probable vandalism, please check. {message.jump_url} " + await self._get_patrol_pings()
                            elif current_level == "high":
                                return f"🚨 Vandalism, please check. {message.jump_url} " + await self._get_patrol_pings()
                            else:
                                logging.error(f"Sight engine unknown intensity failure {current_level=}: {response.text}")
                                return f"❓ Possible vandalism, please check. {message.jump_url} " + await self._get_patrol_pings()
                        else:
                            logging.info(f"handle_inkipedia_event: ✔ Checked and determined clean")

                    elif status == "failure":
                        logging.error("Sight engine failure: " + as_json.get("error").get("message"))
                        return None
                    else:
                        logging.error("Sight engine unknown response: " + response.text)
                        return None

        else:
            logging.warning("No embeds found in Wiki Notifier message!")

    @commands.command(
        name='grant',
        description="Add yourself or another user to a bot group.",
        brief="Add yourself or another user to a bot group.",
        aliases=['add_to_group'],
        help=f'{COMMAND_SYMBOL}grant <role> [other_user]',
        pass_ctx=True)
    async def grant(self, ctx: Context, *, message: str):
        await self.conditional_load_permissions()

        user_id = ctx.author.id.__str__()
        args = message.split(' ')

        if not args:
            await ctx.send(f'{COMMAND_SYMBOL}grant <owner|admin|editor|patrol> [other_user]')
            return

        role = args[0]
        if role not in ("owner", "admin", "editor", "patrol"):
            await ctx.send(f"I don't know the role you're trying to grant: {role}")
            return

        if len(args) > 1:
            user_id = None
            target_user = " ".join(args[1:])
            if target_user.startswith("<@"):
                match = re.search(r"<@!?(\d+)>", target_user)
                if match:
                    user_id = match.group(1)
            elif "#" in target_user:
                match = re.search(r"^(\S.*#\d{4})$", target_user)
                if match:
                    username = match.group(1)
                    ctx.guild.fetch_members()
                    user = ctx.guild.get_member_named(username)
                    if user:
                        user_id = user.id.__str__()
                    else:
                        await ctx.send(f"I wasn't able to find the user by that tag: {username}")
                        return
            else:
                match = re.search(r"(\d+)", target_user)
                if match:
                    user_id = match.group(1)
                    user = await ctx.bot.fetch_user(user_id)
                    if not user:
                        await ctx.send(f"I wasn't able to find the user by that id: {user_id}")
                        return

        if user_id:
            if user_id not in self.permissions[role]:
                if role == 'patrol':
                    self.permissions["patrol"].append(user_id)
                    channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                    await channel.send(json.dumps(self.permissions))
                    await ctx.send(f"Added {user_id} to patrol!")
                else:
                    if self._is_owner(ctx.author):
                        self.permissions[role].append(user_id)
                        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                        await channel.send(json.dumps(self.permissions))
                        await ctx.send(f"Added {user_id} to {role}!")
                    else:
                        await ctx.send(f"You don't have permission to do that.")
            else:
                await ctx.send(f"The {user_id=} already has the role {role}.")
        else:
            await ctx.send(f"I wasn't able to get a target user id. You may omit other_user to target yourself, or use a mention.")

    @commands.command(
        name='deny',
        description="Remove yourself or another user from a bot group.",
        brief="Remove yourself or another user from a bot group.",
        aliases=['remove_from_group'],
        help=f'{COMMAND_SYMBOL}deny <role> [other_user]',
        pass_ctx=True)
    async def deny(self, ctx: Context, *, message: str):
        await self.conditional_load_permissions()

        user_id = ctx.author.id.__str__()
        args = message.split(' ')

        if not args:
            await ctx.send(f'{COMMAND_SYMBOL}deny <owner|admin|editor|patrol> [other_user]')
            return

        role = args[0]
        if role not in ("owner", "admin", "editor", "patrol"):
            await ctx.send(f"I don't know the role you're trying to deny: {role}")
            return

        if len(args) > 1:
            user_id = None
            target_user = " ".join(args[1:])
            if target_user.startswith("<@"):
                match = re.search(r"<@!?(\d+)>", target_user)
                if match:
                    user_id = match.group(1)
            elif "#" in target_user:
                match = re.search(r"^(\S.*#\d{4})$", target_user)
                if match:
                    username = match.group(1)
                    ctx.guild.fetch_members()
                    user = ctx.guild.get_member_named(username)
                    if user:
                        user_id = user.id
                    else:
                        await ctx.send(f"I wasn't able to find the user by that tag: {username}")
                        return
            else:
                match = re.search(r"(\d+)", target_user)
                if match:
                    user_id = match.group(1)
                    user = await ctx.bot.fetch_user(user_id)
                    if not user:
                        await ctx.send(f"I wasn't able to find the user by that id: {user_id}")
                        return

        if user_id:
            if user_id in self.permissions[role]:
                if role == 'patrol':
                    self.permissions["patrol"].remove(user_id)
                    channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                    await channel.send(json.dumps(self.permissions))
                    await ctx.send(f"Removed {user_id} from patrol!")
                else:
                    if self._is_owner(ctx.author):
                        if role == "owner" and len(self.permissions[role]) == 1 and self.permissions[role][0] == user_id:
                            await ctx.send(f"You may not remove yourself as the only owner. Add someone else first.")
                            return

                        self.permissions[role].remove(user_id)
                        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                        await channel.send(json.dumps(self.permissions))
                        await ctx.send(f"Removed {user_id} from {role}!")
                    else:
                        await ctx.send(f"You don't have permission to do that.")
            else:
                await ctx.send(f"The {user_id=} already does not have the role {role}.")
        else:
            await ctx.send(f"I wasn't able to get a target user id. You may omit other_user to target yourself, or use a mention.")
