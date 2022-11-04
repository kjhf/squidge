"""Wiki commands cog."""
import asyncio
import datetime
import json
import logging
import os
import re
from itertools import chain
from typing import Optional, Union

import pywikibot.config
import requests
from discord import TextChannel, Message, User, Member, Interaction
from discord.ext import commands
from discord.ext.commands import Context, Bot
# noinspection PyProtectedMember
from pywikibot import Site, Page, pagegenerators, APISite  # APISite used for type hinting
from pywikibot.page import Revision
from pywikibot.site._namespace import BuiltinNamespace

from src.squidge.entry.consts import COMMAND_SYMBOL
from src.squidge.pwbsupport.category import CategoryAddBot
from src.squidge.pwbsupport.interwiki import InterwikiBotConfig, InterwikiBot, InterwikiDumps

DEFAULT_EDIT = f"[[User:{os.getenv('WIKI_USERNAME')}|Bot edit]] ([[User_talk:{os.getenv('WIKI_USERNAME')}|Something wrong?]])"
EDIT_WITH_AUTHORIZED_BY = f"[[User:{os.getenv('WIKI_USERNAME')}|Bot edit]] authorized by "
REDIRECT_TEXT = "#REDIRECT [["


class WikiCommands(commands.Cog):
    """A grouping of wiki commands."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.permissions = {}
        pywikibot.config.usernames['splatoonwiki']['*'] = os.getenv("WIKI_USERNAME")
        pywikibot.config.default_edit_summary = DEFAULT_EDIT
        pywikibot.config.family = 'splatoonwiki'
        pywikibot.config.mylang = 'en'

        # Find the password file and family file
        file = ".pwd"
        for i in range(0, 10):
            if os.path.exists(file):
                pywikibot.config.password_file = file
                break
            else:
                file = "../" + file
        else:
            logging.warning("Wiki password file not found. Wiki commands that require login will not work.")

        file = "src/squidge/pwbsupport/splatoonwiki_family.py"
        for i in range(0, 10):
            if os.path.exists(file):
                pywikibot.config.family_files['splatoonwiki'] = file
                # Disable the PyTypeChecker here as an APISite is returned from the Site interface.
                # noinspection PyTypeChecker
                self.inkipedia: APISite = Site(code='en', fam='splatoonwiki')
                break
            else:
                file = "../" + file
        else:
            logging.warning("Family file not found. Interwiki commands will not work.")
            # Disable the PyTypeChecker here as an APISite is returned from the Site interface.
            # noinspection PyTypeChecker
            self.inkipedia: APISite = Site(fam='splatoonwiki', url="https://splatoonwiki.org")

        pywikibot.config.put_throttle = 1  # i.e. 1 operation per second throttle
        self.recent_vandals = set()
        super().__init__()

    async def conditional_load_permissions(self):
        if not self.are_permissions_loaded():
            channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
            last_message: Optional[Message] = await channel.fetch_message(channel.last_message_id)
            if last_message:
                permissions_json = json.loads(last_message.content)
                if "owner" in permissions_json and "admin" in permissions_json and "editor" in permissions_json:
                    self.permissions["owner"] = permissions_json["owner"]
                    self.permissions["admin"] = permissions_json["admin"]
                    self.permissions["editor"] = permissions_json["editor"]
                    self.permissions["patrol"] = permissions_json.get("patrol", [])
                    self.permissions["whitelist"] = permissions_json.get("whitelist", [])  # Words that are picked up but shouldn't be, e.g. 'dink'
                    self.permissions["false-triggers"] = permissions_json.get("false-triggers", [])  # Words that trigger a false detection of another word, e.g. 'button'
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
        self.inkipedia.login()  # Do a login here if not already
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
        description="Moves a category and updates all references.",
        brief="Moves a category and updates all references.",
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
        name='delete_category',
        description="Deletes a category and removes its references.",
        brief="Deletes a category and removes its references.",
        aliases=['delcat'],
        help=f'{COMMAND_SYMBOL}delete_category <cat>',
        pass_ctx=True)
    async def delete_category(self, ctx: Context, *, category_title: str):
        await self.conditional_load_permissions()
        if self._is_admin(ctx.author):
            if not category_title.lower().startswith("category"):
                category_title = "Category:" + category_title

            category_title = category_title.replace('_', ' ')
            summary = "Removing `" + category_title + "`"
            await ctx.send(summary)
            cat_page = pywikibot.Category(self.inkipedia, category_title)
            if not Page(self.inkipedia, category_title).exists():
                await ctx.send(f"Warning: the category does not exist.")
            else:
                cat_page.delete(reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary, prompt=False, deletetalk=True)

            pages = chain(cat_page.articles(), cat_page.subcategories(recurse=True))
            count = 0

            for page in pages:
                changed = page.change_category(cat_page, None, summary=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary)
                await asyncio.sleep(1)  # yield
                if changed:
                    count += 1
                else:
                    logging.info(f"Cats: {[c.__str__() for c in page.categories()]}")
            await ctx.send(f"Done, {count} page(s) changed.")
        else:
            await ctx.send("You don't have admin permission.")

    @commands.command(
        name='nuke',
        description="Deletes all images uploaded by a user. Reverts all edits made. Blocks.",
        brief="Nuke a user and block them.",
        aliases=['revert'],
        help=f'{COMMAND_SYMBOL}nuke <user>',
        pass_ctx=True)
    async def nuke(self, ctx: Context, *, user: str):
        await self.conditional_load_permissions()

        # Get the user to nuke
        user_to_nuke = pywikibot.User(self.inkipedia, user)

        if not user_to_nuke or not user_to_nuke.isRegistered(force=True):
            await ctx.send(f"User {user} was not found.")
            return

        # Sanity check for an established user (> 2 as registered users have '*' and 'user')
        rights = user_to_nuke.groups()
        logging.info(f"Groups returned: {rights}")
        if len(rights) > 2:
            await ctx.send(
                "Not nuking this user as they have established rights. If you really meant to do this, demote them first.")
            return

        if self._is_admin(ctx.author):
            await self._nuke(ctx, user_to_nuke)
        elif self._is_editor(ctx.author):
            # We have already checked the user's autoconfirmed status.
            first_edit_ts: pywikibot.Timestamp = user_to_nuke.first_edit[2]
            one_day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
            if first_edit_ts < one_day_ago:  # If the first edit was older than a day ago
                await ctx.send(f"You don't have admin permission for this: {user_to_nuke.username}'s first contribution is more than a day old.")
                return

            if user_to_nuke.username not in self.recent_vandals:
                await ctx.send(f"You don't have admin permission for this: {user_to_nuke.username}'s has not tripped the anti-vandalism detection.")
                return

            await self._nuke(ctx, user_to_nuke)
        else:
            await ctx.send("You don't have admin permission.")

    async def handle_inkipedia_event(self, message: Message) -> Optional[str]:
        await self.conditional_load_permissions()
        if message.embeds:
            embed = message.embeds[0]
            content = embed.title or embed.description
            if content:
                # Scan new pages and new accounts
                emotes_to_check = [":new:", "🆕", ":wave:", "👋", ":outbox_tray:", "📤"]
                if any(emote in content for emote in emotes_to_check):
                    source_user = re.search(r"\[([^\]]+)]", content)
                    if source_user:
                        source_user = source_user.group(1)
                    else:
                        logging.warning(f"handle_inkipedia_event: There were no [] in the message and so a source user was not found.")
                        return

                    # As insurance, also check that the source user indeed appears as a link, to make sure
                    # we haven't tripped over any funny symbols in the user's name
                    source_user_as_page = Page(self.inkipedia, source_user, BuiltinNamespace.USER)
                    if source_user_as_page.title(underscore=True) not in content:
                        logging.error(f"handle_inkipedia_event: Determined the source user to be {source_user} but {source_user_as_page} is not in the content.")
                        return

                    logging.debug(f"handle_inkipedia_event: Checking {content}")

                    # Remove square brackets as they are primarily links, and also fool some detection (e.g. [ is a c)
                    content = content.replace("[", "").replace("]", "")

                    # In each false trigger, if it's a whole word, remove it
                    # (?:\s|\b) is there to clean up the double space if not at the end of the string
                    for word in self.permissions["false-triggers"]:
                        content = re.sub(r"\b(" + word + r")(?:\s|\b)", "", content, flags=re.I)

                    logging.info(f"handle_inkipedia_event: Querying {content}")
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
                            matched_phrases = set()
                            current_level = "low"
                            for match in profanity_matches:
                                phrase = match["match"]
                                if phrase not in self.permissions["whitelist"]:
                                    matched_phrases.add(phrase)
                                    if match["intensity"] == "high":
                                        current_level = "high"
                                    elif match["intensity"] == "medium" and current_level != "high":
                                        current_level = "medium"

                            if matched_phrases:
                                self.recent_vandals.add(source_user)
                                if current_level == "low":
                                    return f"❓ Possible vandalism, matched: ||[{', '.join(matched_phrases)}]|| {message.jump_url} " + await self._get_patrol_pings()
                                elif current_level == "medium":
                                    return f"⚠ Probable vandalism, matched: ||[{', '.join(matched_phrases)}]|| {message.jump_url} " + await self._get_patrol_pings()
                                elif current_level == "high":
                                    return f"🚨 Vandalism, matched: ||[{', '.join(matched_phrases)}]|| {message.jump_url} " + await self._get_patrol_pings()
                                else:
                                    logging.error(f"Sight engine unknown intensity failure {current_level=}: {response.text}")
                                    return f"❓ Possible vandalism, matched: ||[{', '.join(matched_phrases)}]||. {message.jump_url} " + await self._get_patrol_pings()
                            else:
                                logging.info(f"handle_inkipedia_event: ✔ Checked but had only whitelisted phrases")
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
        name='false',
        description="Add a false trigger to the filter. These are word(s) that trigger false detection of another word, e.g. 'button'",
        brief="Add a false trigger to the swear filter to allow it.",
        aliases=['false_triggers'],
        help=f'{COMMAND_SYMBOL}false <phrase>',
        pass_ctx=True)
    async def false(self, ctx: Context, *, phrase: str):
        await self.conditional_load_permissions()

        if not self._is_admin(ctx.author):
            await ctx.send(f'You do not have permission to do this.')

        args = phrase.split(' ')

        if not args:
            await ctx.send(f'{COMMAND_SYMBOL}false <phrase>')
            return

        self.permissions["false-triggers"].append(phrase)
        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
        await channel.send(json.dumps(self.permissions))
        await ctx.send(f"Added {phrase} to false triggers!")

    @commands.command(
        name='whitelist',
        description="Add a detected swear to the whitelist. These are words that trigger detection but are okay, e.g. 'stringer'",
        brief="Add a detected swear to the swear filter to allow it.",
        aliases=['false-whitelist'],
        help=f'{COMMAND_SYMBOL}whitelist <word>',
        pass_ctx=True)
    async def whitelist(self, ctx: Context, *, word: str):
        await self.conditional_load_permissions()

        if not self._is_admin(ctx.author):
            await ctx.send(f'You do not have permission to do this.')

        args = word.split(' ')

        if not args:
            await ctx.send(f'{COMMAND_SYMBOL}whitelist <word>')
            return

        self.permissions["whitelist"].append(word)
        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
        await channel.send(json.dumps(self.permissions))
        await ctx.send(f"Added {word} to whitelist!")

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

    async def _nuke(self, ctx, user_to_nuke: pywikibot.User):
        # Block the user
        if user_to_nuke.is_blocked():
            await ctx.send(f"{user_to_nuke.username} is already blocked, skipping block step.")
        else:
            user_to_nuke.block(expiry='never',
                               reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + ": [[Inkipedia:Policy/Vandalism|Vandalism]]"
                               )

        # Get all contributions from the user
        contributions = user_to_nuke.contributions()
        for contrib in contributions:
            await asyncio.sleep(1)  # yield
            page: pywikibot.Page = contrib[0]
            if page.exists():
                page.revisions()  # load revisions
                try:
                    first_revision: Revision = page.oldest_revision
                    logging.info(
                        f"{first_revision.user=} == {user_to_nuke.username=} ? {first_revision.user == user_to_nuke.username}")
                    if first_revision.user == user_to_nuke.username:
                        page.delete(
                            reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + ": [[Inkipedia:Policy/Vandalism|Vandalism]]",
                            prompt=False)
                    else:
                        logging.info(f"Reverting page={page.title()}")
                        self.inkipedia.rollbackpage(page,
                                                    user=user_to_nuke)  # This will fail on the API if the last user is not the user to nuke
                except Exception as error:
                    logging.error(error)
        await ctx.send(f"Finished nuking {user_to_nuke.username}.")

    @commands.command(
        name='auto_delete',
        description="Deletes orphaned talk pages and broken redirects in the specified category, defaulting to Pages pending deletion.",
        brief="Deletes orphaned talk pages and broken redirects in the specified category, defaulting to Pages pending deletion",
        aliases=['autodel', 'delorphantalk', 'delorphantalks, delete_orphan_talks'],
        help=f'{COMMAND_SYMBOL}autodel [cat=Pages pending deletion]',
        pass_ctx=True)
    async def auto_delete(self, ctx: Context, *, category_title: str = "Pages pending deletion"):
        await self.conditional_load_permissions()
        if self._is_admin(ctx.author):
            if not category_title.lower().startswith("category"):
                category_title = "Category:" + category_title

            category_title = category_title.replace('_', ' ')
            await ctx.send(f"Auto-deleting from {category_title}")
            cat_page = pywikibot.Category(self.inkipedia, category_title)
            if not Page(self.inkipedia, category_title).exists():
                await ctx.send(f"Error: the category does not exist.")
                return

            count = await self.run_auto_delete(cat_page, category_title, ctx.author.__str__())
            await ctx.send(f"Done, {count} page(s) deleted.")
        else:
            await ctx.send("You don't have admin permission.")

    async def run_auto_delete(self, cat_page, category_title, author):
        auth_by = EDIT_WITH_AUTHORIZED_BY + author + " "
        orphaned_summary = auth_by + "Deleting orphaned talk page in [[:" + category_title + "]]"
        broken_redirect_summary = auth_by + "Deleting broken redirect page in [[:" + category_title + "]]"
        unused_redirect_summary = auth_by + "Deleting unused or superseded redirect page in [[:" + category_title + "]]"
        pages = chain(cat_page.articles(), cat_page.subcategories(recurse=True))
        count = 0
        for page in pages:
            await asyncio.sleep(0.1)  # yield

            if page.isTalkPage():
                content_page = page.toggleTalkPage()
                if content_page is None or not content_page.exists() or content_page.isRedirectPage():
                    # Delete the orphan
                    deleted = page.delete(reason=orphaned_summary, prompt=False)
                    if deleted == 1:
                        count += 1
                    else:
                        logging.error(f"Failed to delete {page}.")
                    continue
                else:
                    logging.warning(f"Did not delete {page} because its contents page is in use.")

            # If the page is a redirect (or would have been but has {{delete}} now so is no longer)
            if page.isRedirectPage() or REDIRECT_TEXT in page.text[:1024]:
                if page.isRedirectPage():
                    target_page = page.getRedirectTarget()
                else:
                    start_index = page.text.index(REDIRECT_TEXT) + len(REDIRECT_TEXT)
                    target_page_title = page.text[start_index: page.text.index("]]", start_index)].lstrip(': ')
                    target_page = Page(self.inkipedia, target_page_title)

                if target_page is None or not target_page.exists():
                    # Delete the broken redirect
                    deleted = page.delete(
                        reason=broken_redirect_summary + " targeting " + (
                            target_page.title() if target_page else "non-existent page"),
                        prompt=False)
                    if deleted == 1:
                        count += 1
                    else:
                        logging.error(f"Failed to delete {page}.")
                elif target_page.isRedirectPage():
                    # Double redirect
                    target_target_page = target_page.getRedirectTarget()
                    if target_target_page == page:
                        # Circular reference
                        deleted = page.delete(
                            reason=broken_redirect_summary + " targeting " + (
                                target_page.title() if target_page else "non-existent page"),
                            prompt=False)
                        if deleted == 1:
                            count += 1
                        else:
                            logging.error(f"Failed to delete {page}.")
                    else:
                        # Fix the redirect instead
                        page.set_redirect_target(target_target_page,
                                                 summary=auth_by + "fixing double redirect to " + target_target_page.title(
                                                     as_link=True))
                else:
                    # The target exists and is not a redirect... this page is probably superseded or unused redirect but should be checked by an admin.
                    if any(page.backlinks(total=2)):
                        logging.warning(f"Did not delete {page} because it is in use.")
                    else:
                        deleted = page.delete(
                            reason=unused_redirect_summary + " targeting " + (
                                target_page.title() if target_page else "non-existent page"),
                            prompt=False)
                        if deleted == 1:
                            count += 1
                        else:
                            logging.error(f"Failed to delete {page}.")
            else:
                logging.info(f"Not taking action against {page}: it is not a talk or redirect.")
        return count

    @commands.command(
        name='remove_construction',
        description="Go through pages under construction and remove those above a certain size",
        brief="Go through pages under construction and remove those above a certain size",
        aliases=['remconstruction'],
        help=f'{COMMAND_SYMBOL}remove_construction',
        pass_ctx=True)
    async def remove_construction(self, ctx: Context, *, category_title: str = "Articles under construction"):
        construction_re = re.compile(re.escape('{{construction}}'), re.IGNORECASE)
        size_threshold = 4000

        await self.conditional_load_permissions()
        if self._is_editor(ctx.author):

            if not category_title.lower().startswith("category"):
                category_title = "Category:" + category_title

            category_title = category_title.replace('_', ' ')
            summary = f"Removing construction notice from articles larger than {size_threshold} bytes"
            await ctx.send(summary)
            cat_page = pywikibot.Category(self.inkipedia, category_title)
            if not Page(self.inkipedia, category_title).exists():
                await ctx.send(f"Error: the category does not exist.")
                return

            pages = chain(cat_page.articles(), cat_page.subcategories(recurse=True))
            count = 0

            for page in pages:
                if page.latest_revision.size >= size_threshold:
                    page.text = construction_re.sub('', page.text)
                    page.save(
                        summary=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary,
                        prompt=False)
                    count += 1
                    await asyncio.sleep(1)  # yield

            await ctx.send(f"Done, {count} page(s) changed.")
        else:
            await ctx.send("You don't have admin permission.")

    @commands.command(
        name='interwiki',
        description="Run interwiki sync command",
        brief="Run interwiki sync command",
        help=f'{COMMAND_SYMBOL}interwiki',
        pass_ctx=True)
    async def perform_interwiki(self, ctx: Context):
        await self.conditional_load_permissions()
        if self._is_editor(ctx.author):
            interwiki_conf = InterwikiBotConfig()
            interwiki_conf.readOptions("-autonomous")

            # Do not use additional summary with autonomous mode
            interwiki_conf.summary = EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " interwiki update"
            site = self.inkipedia

            # ensure that we don't try to change main page
            main_page_name = site.siteinfo['mainpage']
            interwiki_conf.skip.add(pywikibot.Page(site, main_page_name))
            dump = InterwikiDumps(site=site, do_continue=False, restore_all=interwiki_conf.restore_all)
            bot = InterwikiBot(interwiki_conf)
            bot.site = site
            bot.setPageGenerator(iter(pagegenerators.AllpagesPageGenerator(includeredirects=False, site=site)))

            try:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, bot.run)
            except KeyboardInterrupt:
                dump.write_dump(bot.dump_titles, True)
            except Exception:  # pragma: no cover
                pywikibot.exception()
                dump.write_dump(bot.dump_titles, True)
            else:
                pywikibot.output('Script terminated successfully.')
            finally:
                dump.delete_dumps()
        else:
            await ctx.send("You don't have editor permission.")

    async def add_categories_with_perm_check(self, interaction: Interaction, category_no_ns, operation, rule_namespace, rule_title):
        await self.conditional_load_permissions()
        user = interaction.user
        if self._is_editor(user):
            switch = {
                'user': BuiltinNamespace.USER,
                'user talk': BuiltinNamespace.USER_TALK,
                'category': BuiltinNamespace.CATEGORY,
                'category talk': BuiltinNamespace.CATEGORY_TALK,
                'template': BuiltinNamespace.TEMPLATE,
                'template talk': BuiltinNamespace.TEMPLATE_TALK,
                'file': BuiltinNamespace.FILE,
                'file talk': BuiltinNamespace.FILE_TALK,
                'help': BuiltinNamespace.HELP,
                'help talk': BuiltinNamespace.HELP_TALK,
                'main': BuiltinNamespace.MAIN,
                'talk': BuiltinNamespace.TALK,
                'media': BuiltinNamespace.MEDIA,
                'mediawiki': BuiltinNamespace.MEDIAWIKI,
                'mediawiki talk': BuiltinNamespace.MEDIAWIKI_TALK,
                'project': BuiltinNamespace.PROJECT,
                'inkipedia': BuiltinNamespace.PROJECT,
                'project talk': BuiltinNamespace.PROJECT_TALK,
                'inkipedia talk': BuiltinNamespace.PROJECT_TALK,
                'special': BuiltinNamespace.SPECIAL,
            }
            if rule_namespace:
                ns = switch.get(rule_namespace.lower().replace('_', ' '), 0)
            else:
                ns = 0
            namespace_filter_pages = pagegenerators.AllpagesPageGenerator(includeredirects=False, site=self.inkipedia, namespace=ns)
            operation_switch = {
                'are named': fr"^{re.escape(rule_title)}$",
                'start with': fr"^{re.escape(rule_title)}",
                'end with': fr"{re.escape(rule_title)}$",
                'contain': fr"{re.escape(rule_title)}",
            }
            regex_str = operation_switch.get(operation, None)
            rule_pages = pagegenerators.RegexFilterPageGenerator(namespace_filter_pages, re.compile(regex_str))

            bot = CategoryAddBot(rule_pages, category_no_ns, comment=EDIT_WITH_AUTHORIZED_BY + user.__str__() + " adding category " + category_no_ns, prompt=False)
            bot.site = self.inkipedia
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, bot.run)

        else:
            await interaction.followup.send("You don't have editor permission.", ephemeral=True)
