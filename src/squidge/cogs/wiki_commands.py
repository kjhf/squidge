"""Wiki commands cog."""
import asyncio
import datetime
import logging
import os
import re
from itertools import chain
from typing import Optional, List, Generator

import pywikibot.config
import requests
from discord import TextChannel, Message, Interaction
from discord.ext import commands
from discord.ext.commands import Context, Bot
# noinspection PyProtectedMember
from pywikibot import Site, Page, pagegenerators, APISite, Category  # APISite used for type hinting
from pywikibot.data import api
from pywikibot.page import Revision
from pywikibot.site._namespace import BuiltinNamespace

from src.squidge.discordsupport.channel_logger import MESSAGE_TEXT_LIMIT
from src.squidge.entry.consts import COMMAND_SYMBOL
from src.squidge.pwbsupport.category import CategoryAddBot
from src.squidge.pwbsupport.helpers import get_all_users_generator
from src.squidge.pwbsupport.interwiki import InterwikiBotConfig, InterwikiBot
from src.squidge.savedata.bad_words import BadWords
from src.squidge.savedata.wiki_permissions import WikiPermissions

DEFAULT_EDIT = f"[[User:{os.getenv('WIKI_USERNAME')}|Bot edit]] ([[User_talk:{os.getenv('WIKI_USERNAME')}|Something wrong?]])"
EDIT_WITH_AUTHORIZED_BY = f"[[User:{os.getenv('WIKI_USERNAME')}|Bot edit]] authorized by "
REDIRECT_TEXT = "#REDIRECT [["
FILE_LINK_REGEX = re.compile(r"\[\[:?[Ff]ile:([\s\S]*?)(?:\||\]\])")
DELETE_REASON_REGEX = re.compile(r"{{[dD]elete\s*?\|\s*([\s\S]*?)}}")  # TODO - find a way of parsing templates inside the delete reason
AUTHOR_REQ_REGEX = re.compile(r"(author req|(?:un|n[o']t?).*?(?:need|used?)|user image)")


class WikiCommands(commands.Cog):
    """A grouping of wiki commands."""

    def __init__(self, bot: Bot):
        from src.squidge.entry.SquidgeBot import SquidgeBot
        assert isinstance(bot, SquidgeBot)
        self.bot: SquidgeBot = bot
        # the docs say you can use a star but interwiki determined that is... a lie
        pywikibot.config.usernames['splatoonwiki']['en'] = os.getenv("WIKI_USERNAME")
        pywikibot.config.usernames['splatoonwiki']['fr'] = os.getenv("WIKI_USERNAME")
        pywikibot.config.usernames['splatoonwiki']['es'] = os.getenv("WIKI_USERNAME")
        pywikibot.config.default_edit_summary = DEFAULT_EDIT
        pywikibot.config.family = 'splatoonwiki'
        pywikibot.config.mylang = 'en'
        pywikibot.config.interwiki_backlink = True
        pywikibot.config.colorized_output = True
        pywikibot.config.interwiki_shownew = True

        self.sites: dict[str, APISite] = {}

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
                self.sites['en'] = Site(code='en', fam='splatoonwiki')
                # noinspection PyTypeChecker
                self.sites['fr'] = Site(code='fr', fam='splatoonwiki')
                # noinspection PyTypeChecker
                self.sites['es'] = Site(code='es', fam='splatoonwiki')
                break
            else:
                file = "../" + file
        else:
            logging.critical("***Family file not found. Interwiki commands will not work.***")
            # Disable the PyTypeChecker here as an APISite is returned from the Site interface.
            # noinspection PyTypeChecker
            self.sites['en'] = Site(fam='splatoonwiki', url="https://splatoonwiki.org")

        pywikibot.config.put_throttle = 1  # i.e. 1 operation per second throttle
        self.recent_vandals = set()
        super().__init__()

    @property
    def inkipedia(self):
        """Shortcut to get the English Inkipedia site"""
        return self.sites['en']

    @property
    def permissions(self) -> WikiPermissions:
        return self.bot.save_data.wiki_permissions

    @property
    def bad_words(self) -> BadWords:
        return self.bot.save_data.bad_words

    def login_to_sites(self):
        for site in self.sites.values():
            site.login()

    async def _get_patrol_pings(self):
        return "".join([f"<@!{i}> " for i in self.permissions.patrol])

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
        if self.permissions.is_editor(ctx.author):
            self.login_to_sites()
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
                old_cat_page_list.move(new_category,
                                       reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary)
            pages = chain(old_cat_page_list.articles(), old_cat_page_list.subcategories(recurse=True))
            count = 0

            new_cat_page_list = pywikibot.Category(self.inkipedia, new_category)
            for page in pages:
                changed = page.change_category(old_cat_page_list, new_cat_page_list,
                                               summary=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary)
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
        if self.permissions.is_admin(ctx.author):
            self.login_to_sites()
            if not category_title.lower().startswith("category"):
                category_title = "Category:" + category_title

            category_title = category_title.replace('_', ' ')
            summary = "Removing `" + category_title + "`"
            await ctx.send(summary)
            cat_page = pywikibot.Category(self.inkipedia, category_title)
            if not Page(self.inkipedia, category_title).exists():
                await ctx.send(f"Warning: the category does not exist.")
            else:
                cat_page.delete(reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary, prompt=False,
                                deletetalk=True)

            pages = chain(cat_page.articles(), cat_page.subcategories(recurse=True))
            count = 0

            for page in pages:
                changed = page.change_category(cat_page, None,
                                               summary=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " " + summary)
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
        # Get the user to nuke
        self.login_to_sites()
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

        if self.permissions.is_admin(ctx.author):
            await self._nuke(ctx, user_to_nuke)
        elif self.permissions.is_editor(ctx.author):
            # We have already checked the user's autoconfirmed status.
            first_edit_ts: pywikibot.Timestamp = user_to_nuke.first_edit[2]
            one_day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
            if first_edit_ts < one_day_ago:  # If the first edit was older than a day ago
                await ctx.send(
                    f"You don't have admin permission for this: {user_to_nuke.username}'s first contribution is more than a day old.")
                return

            if user_to_nuke.username not in self.recent_vandals:
                await ctx.send(
                    f"You don't have admin permission for this: {user_to_nuke.username}'s has not tripped the anti-vandalism detection.")
                return

            await self._nuke(ctx, user_to_nuke)
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
                    source_user = re.search(r"\[([^\]]+)]", content)
                    if source_user:
                        source_user = source_user.group(1)
                    else:
                        logging.warning(
                            f"handle_inkipedia_event: There were no [] in the message and so a source user was not found.")
                        return

                    # As insurance, also check that the source user indeed appears as a link, to make sure
                    # we haven't tripped over any funny symbols in the user's name
                    source_user_as_page = Page(self.inkipedia, source_user, BuiltinNamespace.USER)
                    if source_user_as_page.title(underscore=True) not in content:
                        logging.error(
                            f"handle_inkipedia_event: Determined the source user to be {source_user} but {source_user_as_page} is not in the content.")
                        return

                    logging.debug(f"handle_inkipedia_event: Checking {content}")

                    # Remove square brackets as they are primarily links, and also fool some detection (e.g. [ is a c)
                    content = content.replace("[", "").replace("]", "")

                    # In each false trigger, if it's a whole word, remove it
                    # [\s\W\b] is there to match space/punctuation/end of the string
                    for word in self.bad_words.false_triggers:
                        content = re.sub(r"[\s\W\b](" + word + r")[\s\W\b]", "", content, flags=re.I)

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
                                if phrase not in self.bad_words.whitelist:
                                    matched_phrases.add(phrase)
                                    if match["intensity"] == "high":
                                        current_level = "high"
                                    elif match["intensity"] == "medium" and current_level != "high":
                                        current_level = "medium"

                            if matched_phrases:
                                self.recent_vandals.add(source_user)
                                return f"🚨 {current_level} intensity match: ||[{', '.join(matched_phrases)}]|| {message.jump_url} " + await self._get_patrol_pings()
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
        if not self.permissions.is_patrol(ctx.author) and not self.permissions.is_admin(ctx.author):
            await ctx.send(f'You do not have permission to do this (you must be a bot patrol or bot admin).')
            return

        phrase = phrase.lower()

        if not phrase:
            await ctx.send(f'{COMMAND_SYMBOL}false <phrase>')
            return

        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
        set_list = set([w.lower() for w in self.bad_words.false_triggers])

        if phrase in set_list:
            set_list.remove(phrase)
            await ctx.send(f"Removed {phrase} from false triggers!")
        else:
            set_list.add(phrase)
            await ctx.send(f"Added {phrase} to false triggers!")

        self.bad_words.false_triggers = list(set_list)
        await self.bot.save_data.save(channel)

    @commands.command(
        name='whitelist',
        description="Add a detected swear to the whitelist. These are words that trigger detection but are okay, e.g. 'stringer'",
        brief="Add a detected swear to the swear filter to allow it.",
        aliases=['false-whitelist', 'allow'],
        help=f'{COMMAND_SYMBOL}whitelist <word>',
        pass_ctx=True)
    async def whitelist(self, ctx: Context, *, word: str):
        if not self.permissions.is_patrol(ctx.author) and not self.permissions.is_admin(ctx.author):
            await ctx.send(f'You do not have permission to do this (you must be a bot patrol or bot admin).')
            return

        word = word.lower()

        if not word:
            await ctx.send(f'{COMMAND_SYMBOL}whitelist <word>')
            return

        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
        set_list = set([w.lower() for w in self.bad_words.whitelist])

        if word in set_list:
            set_list.remove(word)
            await ctx.send(f"Removed {word} from allowed words!")
        else:
            set_list.add(word)
            await ctx.send(f"Added {word} to allowed words!")

        self.bad_words.whitelist = list(set_list)
        await self.bot.save_data.save(channel)

    @commands.command(
        name='grant',
        description="Add yourself or another user to a bot group.",
        brief="Add yourself or another user to a bot group.",
        aliases=['add_to_group'],
        help=f'{COMMAND_SYMBOL}grant <role> [other_user]',
        pass_ctx=True)
    async def grant(self, ctx: Context, *, message: str):
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
            role_list = self.permissions.get_role_list(role)
            if user_id not in role_list:
                if role == 'patrol':
                    role_list.append(user_id)
                    channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                    await self.bot.save_data.save(channel)
                    await ctx.send(f"Added {user_id} to patrol!")
                else:
                    if self.permissions.is_owner(ctx.author):
                        role_list.append(user_id)
                        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                        await self.bot.save_data.save(channel)
                        await ctx.send(f"Added {user_id} to {role}!")
                    else:
                        await ctx.send(f"You don't have permission to do that.")
            else:
                await ctx.send(f"The {user_id=} already has the role {role}.")
        else:
            await ctx.send(
                f"I wasn't able to get a target user id. You may omit other_user to target yourself, or use a mention.")

    @commands.command(
        name='deny',
        description="Remove yourself or another user from a bot group.",
        brief="Remove yourself or another user from a bot group.",
        aliases=['remove_from_group'],
        help=f'{COMMAND_SYMBOL}deny <role> [other_user]',
        pass_ctx=True)
    async def deny(self, ctx: Context, *, message: str):
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
            role_list = self.permissions.get_role_list(role)
            if user_id in role_list:
                if role == 'patrol':
                    role_list.remove(user_id)
                    channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                    await self.bot.save_data.save(channel)
                    await ctx.send(f"Removed {user_id} from patrol!")
                else:
                    if self.permissions.is_owner(ctx.author):
                        if role == "owner" and len(role_list) == 1 and role_list[0] == user_id:
                            await ctx.send(f"You may not remove yourself as the only owner. Add someone else first.")
                            return

                        role_list.remove(user_id)
                        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
                        await self.bot.save_data.save(channel)
                        await ctx.send(f"Removed {user_id} from {role}!")
                    else:
                        await ctx.send(f"You don't have permission to do that.")
            else:
                await ctx.send(f"The {user_id=} already does not have the role {role}.")
        else:
            await ctx.send(
                f"I wasn't able to get a target user id. You may omit other_user to target yourself, or use a mention.")

    async def _nuke(self, ctx, user_to_nuke: pywikibot.User):
        # Block the user
        if user_to_nuke.is_blocked():
            await ctx.send(f"{user_to_nuke.username} is already blocked, skipping block step.")
        else:
            user_to_nuke.block(expiry='never',
                               reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + ": [[Inkipedia:Policy/Vandalism|Vandalism]]")

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
        if self.permissions.is_admin(ctx.author):
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
        self.login_to_sites()
        auth_by = EDIT_WITH_AUTHORIZED_BY + author + " "
        orphaned_summary = auth_by + "Deleting orphaned talk page in [[:" + category_title + "]]"
        broken_redirect_summary = auth_by + "Deleting broken redirect page in [[:" + category_title + "]]"
        double_redirect_summary = auth_by + "Fixing double redirect in [[:" + category_title + "]]"
        unused_redirect_summary = auth_by + "Deleting unused or superseded redirect page in [[:" + category_title + "]]"
        unused_category_summary = auth_by + "Empty category marked for deletion in [[:" + category_title + "]]"
        author_request_summary = auth_by + "Deleting page by author request in [[:" + category_title + "]]"
        duplicate_request_summary = auth_by + "Deleting reported duplicate in [[:" + category_title + "]]"
        count = 0
        for page in chain(cat_page.articles(), cat_page.subcategories(recurse=True)):
            await asyncio.sleep(0.1)  # yield

            if page.isTalkPage():
                if await self._handle_talkpage_auto_delete(page, orphaned_summary):
                    count = count + 1
                continue

            if page.is_categorypage():
                if await self._handle_category_auto_delete(page, unused_category_summary):
                    count = count + 1
                continue

            if page.namespace() == BuiltinNamespace.USER.value:
                if await self._handle_userpage_auto_delete(page, author_request_summary):
                    count = count + 1
                continue

            if page.is_filepage():
                if await self._handle_filepage_auto_delete(page, author_request_summary, duplicate_request_summary):
                    count = count + 1
                    continue  # only loop if deleted. Otherwise, let's try the redirect.

            # If the page is a redirect (or would have been but has {{delete}} now so is no longer)
            target_page = self._get_redirect_target(page)
            if target_page:
                if await self._handle_redirect_auto_delete(page, target_page, broken_redirect_summary,
                                                           double_redirect_summary, unused_redirect_summary):
                    count = count + 1
                continue

            logging.info(f"Not taking action against {page}.")
        return count

    async def _handle_redirect_auto_delete(self, page: Page, target_page: Page,
                                           broken_redirect_summary,
                                           double_redirect_summary,
                                           unused_redirect_summary):
        if not target_page.exists():
            # Delete the broken redirect
            return self._try_delete_page(page, broken_redirect_summary + " targeting " + (target_page.title()))

        if target_page.isRedirectPage():
            # Double redirect
            target_target_page = target_page.getRedirectTarget()
            if target_target_page == page:
                # Circular reference
                return self._try_delete_page(page, broken_redirect_summary + " targeting " + (target_page.title()))
            # else fix the redirect instead
            page.set_redirect_target(
                target_target_page,
                summary=double_redirect_summary + " targeting " + target_target_page.title(as_link=True),
                force=True)  # If the page isn't a redirect, which it isn't because it's marked with {{delete}}, it will not be corrected without this
            self._handle_not_deleting(page, "fixed redirect instead.", False, False)
        else:
            # The target exists and is not a redirect... this page is probably superseded or unused redirect but should be checked by an admin.
            if self._is_in_use(page):
                self._handle_not_deleting(page, "it is in use.")
            else:
                return self._try_delete_page(page, unused_redirect_summary + " targeting " + (
                    target_page.title(as_link=True)))
        return False

    async def _handle_filepage_auto_delete(self, page: Page, author_request_summary, duplicate_request_summary):
        if self._is_in_use(page):
            self._handle_not_deleting(page, "it is in use.")
            return False

        page.revisions()  # load revisions
        try:
            first_revision: Revision = page.oldest_revision
            latest_revision = page.latest_revision
            is_uploader = first_revision.user == latest_revision.user
            given_reason = self._get_given_delete_reason(page)

            if not given_reason and is_uploader:
                return self._try_delete_page(page, author_request_summary)

            # If it's a duplicate
            given_reason_cf = given_reason.casefold()
            if any(r in given_reason_cf for r in ("dupe file", "dupe", "duplicate")):
                dupe_target = self._get_dupe_file_target(page, given_reason)
                if dupe_target:
                    if dupe_target.exists():
                        return self._try_delete_page(
                            page, f"{duplicate_request_summary} targeting {dupe_target.title(as_link=True)}")
                    else:
                        self._handle_not_deleting(
                            page, "the dupe reason contains a non-existent file target.")
                else:
                    self._handle_not_deleting(
                        page, "the dupe reason does not contain a file target.")
            elif is_uploader:
                if AUTHOR_REQ_REGEX.search(given_reason_cf):
                    return self._try_delete_page(page, author_request_summary)
                else:
                    self._handle_not_deleting(
                        page, "author requested deletion but I didn't understand the reason.", False, True)
            else:
                # Extend this to include user and wiki image handling and send off notices.
                self._handle_not_deleting(page, "an editor other than the author requested deletion.", False, True)
        except Exception as error:
            logging.error(error)
        return False

    async def _handle_userpage_auto_delete(self, page, author_request_summary):
        if self._is_in_use(page):
            self._handle_not_deleting(page, "it is in use.")
            return False

        try:
            if page.latest_revision.user == page.oldest_revision.user:
                return self._try_delete_page(page, author_request_summary)
            # else
            self._handle_not_deleting(page, "someone other than the author requested deletion of a userpage.")
        except Exception as error:
            logging.error(error)
        return False

    async def _handle_category_auto_delete(self, page: Category, unused_category_summary):
        subpages = chain(page.articles(), page.subcategories(recurse=True))
        if any(subpages):
            self._handle_not_deleting(page, "it has subpages.")
            return False

        # Delete the empty category
        return self._try_delete_page(page, unused_category_summary)

    async def _handle_talkpage_auto_delete(self, page: Page, summary):
        content_page = page.toggleTalkPage()
        if content_page is None or not content_page.exists() or content_page.isRedirectPage():
            # Delete the orphan
            return self._try_delete_page(page, summary)
        # else
        self._handle_not_deleting(page, "its contents page is in use.")
        return False

    def _handle_not_deleting(self, page: Page, reason: str,
                             add_as_clarify: bool = True,
                             add_as_cannot_auto: bool = True):
        # Add to the logging
        reason_pre = f"Did not delete {page} because: "
        logging.info(reason_pre + reason)

        # If not modifying the page
        if not add_as_cannot_auto and not add_as_clarify:
            return

        # Don't double-up
        # if self._is_last_modified_by_squidge(page):  # TODO - this isn't working for some reason
        #     return

        current_reason = self._get_given_delete_reason(page)

        if 'CannotAutoDelete' in current_reason or '{{clarify' in current_reason:
            return

        modified_reason = current_reason or ""
        if add_as_clarify:
            modified_reason += " {{clarify|" + reason + "}}"
        if add_as_cannot_auto:
            # Add {{Delete/CannotAutoDelete}}
            modified_reason += " {{Delete/CannotAutoDelete}}"
            pass
        page.text = re.sub(DELETE_REASON_REGEX, r'{{delete|' + modified_reason + '}}', page.text)
        page.save(
            summary=DEFAULT_EDIT + ": Cannot process auto-delete",
            prompt=False)

    @staticmethod
    def _get_given_delete_reason(page) -> Optional[str]:
        match = DELETE_REASON_REGEX.search(page.text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _is_last_modified_by_squidge(page: Page):
        page.revisions(total=1)
        return page.site.username() == page.userName

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

        if self.permissions.is_editor(ctx.author):
            self.login_to_sites()
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
        if self.permissions.is_editor(ctx.author):
            await ctx.send("Configuring interwiki...")
            interwiki_conf = InterwikiBotConfig()
            # tempting to run in async mode, but we control the event loop, so don't do that
            # interwiki_conf.readOptions("-restore all")

            # Do not use additional summary with autonomous mode
            # (we don't care for the i18n submodule)
            interwiki_conf.summary = EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + " interwiki update"
            interwiki_conf.auto = True
            interwiki_conf.autonomous = True
            interwiki_conf.always = True
            interwiki_conf.minsubjects = 10  # 100 by default. Don't consume the whole wiki in one go!!
            interwiki_conf.maxquerysize = 25  # was 50
            interwiki_conf.nobackonly = False

            # Refresh our logins now
            self.login_to_sites()

            # ensure that we don't try to change main page
            for (code, site) in self.sites.items():
                interwiki_conf.skip.clear()
                main_page_name = site.siteinfo['mainpage']
                interwiki_conf.skip.add(pywikibot.Page(site, main_page_name))
                bot = InterwikiBot(interwiki_conf)
                bot.site = site
                bot.setPageGenerator(iter(pagegenerators.AllpagesPageGenerator(includeredirects=False)))

                try:
                    await ctx.send(f"Running interwiki for {code}...")
                    await bot.run()
                except Exception as err:
                    pywikibot.exception()
                    await ctx.send(f"Interwiki terminated early: {err[:2000]}")
                finally:
                    await ctx.send(f"...Interwiki finished for {code}.")
        else:
            await ctx.send("You don't have editor permission.")

    @commands.command(
        name='delete_list',
        description="Deletes from a supplied list.",
        brief="Deletes from a supplied list.",
        aliases=['dellist', 'deletioning'],
        help=f'{COMMAND_SYMBOL}delete_list (args)',
        pass_ctx=True)
    async def delete_list(self, ctx: Context):
        if self.permissions.is_admin(ctx.author):
            self.login_to_sites()
            try:
                # If there is an attachment, read it
                if str(ctx.message.attachments) == "[]":  # Checks if there is an attachment on the message
                    await ctx.send(
                        "You need to send a text file with the message. Please upload and send a new message.")
                    return

                attachments = ctx.message.attachments
                split_v1 = str(attachments).split("filename='")[1]
                filename = str(split_v1).split("' ")[0]
                if filename.endswith(".txt") or filename.endswith(".csv"):  # if csv or txt
                    file_bytes = await attachments[0].read()  # Read the contents of the file as bytes
                    file_contents = file_bytes.decode("utf-8").splitlines()  # Decode the bytes as a string[]
                    author = ctx.author.__str__()
                    auth_by = EDIT_WITH_AUTHORIZED_BY + author + " "
                    edit_summary = auth_by + "Mass deletion of files"
                    result = "Deleted: \n"
                    for line in file_contents:
                        if line:
                            # Each line is a wiki title
                            page = Page(self.inkipedia, line, ns=BuiltinNamespace.FILE)
                            if self._try_delete_page(page, edit_summary):
                                result += line + "\n"
                            else:
                                result += "*FAILED* " + line + "\n"
                    await ctx.send(result[:MESSAGE_TEXT_LIMIT])

            except Exception as ex:
                await ctx.send(f"There was a problem: {ex.args}")

    @commands.command(
        name='iotm',
        description="Run Inkipedian of the Month command",
        brief="Run Inkipedian of the Month command",
        help=f'{COMMAND_SYMBOL}iotm',
        pass_ctx=True)
    async def perform_iotm(self, ctx: Context):
        if self.permissions.is_admin(ctx.author):
            await ctx.send("Beginning Inkipedian of the Month command.")
            edited_page = await self._do_iotm()
            url = edited_page.site.base_url(edited_page.site.articlepath.format(edited_page.title(underscore=True)))
            await ctx.send(f"Done. Please see {url}")

    async def _do_iotm(self):
        self.login_to_sites()

        # Define namespace weighting
        ns_to_score = {
            BuiltinNamespace.CATEGORY: 1,
            BuiltinNamespace.CATEGORY_TALK: 0.1,
            BuiltinNamespace.TEMPLATE: 5,
            BuiltinNamespace.TEMPLATE_TALK: 0.5,
            BuiltinNamespace.FILE: 1,
            BuiltinNamespace.FILE_TALK: 0.1,
            BuiltinNamespace.HELP: 1,
            BuiltinNamespace.HELP_TALK: 0.1,
            BuiltinNamespace.MAIN: 3,
            BuiltinNamespace.TALK: 0.2,
            BuiltinNamespace.MEDIA: 1,
            BuiltinNamespace.MEDIAWIKI: 1,
            BuiltinNamespace.MEDIAWIKI_TALK: 0.1,
            BuiltinNamespace.PROJECT: 1,
            BuiltinNamespace.PROJECT_TALK: 0.1,
            460: 1,  # Campaign
            461: 0.1,  # Campaign talk
            828: 5,  # Module
            829: 0.5,  # Module talk
            2300: 5,  # Gadget
            2301: 0.5,  # Gadget talk
            3000: 2,  # Competitive
            3001: 0.2,  # Competitive talk
            # For all other namespaces, score nothing
        }

        # Fist, gather a list of users who have edited in the last month.
        start = datetime.datetime.utcnow()
        end = start - datetime.timedelta(days=31)
        if start and end:
            self.inkipedia.assert_valid_iter_params('usercontribs', start, end, False)

        # Keyed by username, with the user's editcount, groups, and registration date
        users_info = {}
        au_gen: Generator[dict] = get_all_users_generator(
            self.inkipedia,
            auexcludegroup="bot",
            auprop="groups|registration",
            auwitheditsonly=True,
            auactiveusers=True)

        for user in au_gen:
            username: str = user["name"]
            users_info[username] = user
            await asyncio.sleep(0.001)  # yield

        # Score each one
        logging.info(f"All users received, {len(users_info)} in the set.")
        for username in users_info:
            await asyncio.sleep(0.001)  # yield
            # Used self.inkipedia.usercontribs(user=user, start=start, end=end) but this does not return the contrib sizediff that we need ._.
            ucgen = self.inkipedia._generator(api.ListGenerator,
                                              type_arg='usercontribs',
                                              ucprop='title|sizediff',
                                              namespaces=None,
                                              total=None,
                                              uctoponly=False)
            ucgen.request['ucuser'] = username
            ucgen.request['ucstart'] = str(start)
            ucgen.request['ucend'] = str(end)
            option_set = api.OptionSet(self.inkipedia, 'usercontribs', 'show')
            option_set['minor'] = None
            ucgen.request['ucshow'] = option_set

            user_score = 0
            for contrib in ucgen:
                bytes_changed = abs(int(contrib['sizediff']))
                # 5,000 bytes maximum per edit to prevent huge score increase for manual merge/copy-paste
                user_score += (min(bytes_changed, 5000) * ns_to_score.get(int(contrib['ns']), 0))
            users_info[username]["score"] = user_score

        # Post results to the page
        # For rights level: User / autopatrolled / Patroller / Admin / Bcrat
        best = [pair for pair in sorted(users_info.items(), key=lambda kv: kv[1]["score"], reverse=True) if
                pair[1]["score"] > 0]
        iotm_page = Page(self.inkipedia, self.inkipedia.username() + "/iotm", ns=BuiltinNamespace.USER)
        iotm_page.text = """
{| class="sortable wikitable"
! User
! Weighted score
! Highest group
! Registration
|-"""

        for (username, user_info_dict) in best:
            user_groups = user_info_dict["groups"]
            rights_level = ("B'crat" if "bureaucrat" in user_groups else
                            "Admin" if "sysop" in user_groups else
                            "InterfaceAdmin" if "interface-admin" in user_groups else
                            "Patroller" if "patrol" in user_groups else
                            "Auto-patrolled" if "autopatrol" in user_groups else
                            "Auto-confirmed" if "autoconfirmed" in user_groups else
                            "User" if "user" in user_groups else "?")
            if "affiliate" in user_groups:
                rights_level += " + Affiliate"

            iotm_page.text += f"\n| [[Special:Contributions/{username}|{username}]]\n|{user_info_dict['score']}\n|{rights_level}\n|{user_info_dict['registration']}\n|-"

        iotm_page.text += "\n|}"
        iotm_page.save(summary=DEFAULT_EDIT + f" Updating IotM scores since {str(end)}", minor=True, botflag=True,
                       force=True)
        return iotm_page

    async def add_categories_with_perm_check(self, interaction: Interaction, category_no_ns, operation, rule_namespace,
                                             rule_title):
        user = interaction.user
        if self.permissions.is_editor(user):
            self.login_to_sites()
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
            namespace_filter_pages = pagegenerators.AllpagesPageGenerator(includeredirects=False, site=self.inkipedia,
                                                                          namespace=ns)
            operation_switch = {
                'are named': fr"^{re.escape(rule_title)}$",
                'start with': fr"^{re.escape(rule_title)}",
                'end with': fr"{re.escape(rule_title)}$",
                'contain': fr"{re.escape(rule_title)}",
            }
            regex_str = operation_switch.get(operation, None)
            rule_pages = pagegenerators.RegexFilterPageGenerator(namespace_filter_pages, re.compile(regex_str))

            bot = CategoryAddBot(rule_pages, category_no_ns,
                                 comment=EDIT_WITH_AUTHORIZED_BY + user.__str__() + " adding category " + category_no_ns,
                                 prompt=False)
            bot.site = self.inkipedia
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, bot.run)

        else:
            await interaction.followup.send("You don't have editor permission.", ephemeral=True)

    @staticmethod
    def _is_in_use(page):
        # The target exists and is not a redirect... this page is probably superseded or unused redirect but should be checked by an admin.
        backlinks: List[pywikibot.Page] = list(page.backlinks(total=3))
        logging.info("Up to 3 backlinks checked: " + '\n'.join([page.full_url() for page in backlinks]))

        # thanks Trig.
        trig_userspace = "https://splatoonwiki.org/wiki/User%3ATrig_Jegman%2F"
        trig_usertalkspace = "https://splatoonwiki.org/wiki/User_talk%3ATrig_Jegman%2F"
        return backlinks and any(backlink
                                 and not backlink.full_url().startswith(trig_userspace)
                                 and not backlink.full_url().startswith(trig_usertalkspace)
                                 for backlink in backlinks)

    @staticmethod
    def _try_delete_page(page, delete_summary) -> bool:
        try:
            deleted = page.delete(reason=delete_summary, prompt=False)
        except pywikibot.exceptions.Error as err:
            logging.error(f"Failed to delete {page} because a wiki exception occurred: {err}.", exc_info=err)
            return False

        if deleted == 1:
            return True
        else:
            #  0 = no action was done
            # -1 = marked for deletion instead
            logging.error(f"Failed to delete {page} (delete returned {deleted}).")
            return False

    @staticmethod
    def _previous_revision_text(page) -> Optional[str]:
        """Return the previous revision's text for this page (i.e. the one before latest); None if there isn't one"""
        latest: 'Revision' = page.latest_revision
        parent_id = latest.get("parentid")
        return page.getOldVersion(parent_id) if parent_id else None

    @staticmethod
    def _get_redirect_target(page: Page) -> Optional[Page]:
        """
        Return the page's redirect target, including where it would have redirected to if it's not a redirect.
        None if it's definitely not a redirect.
        """
        if page.isRedirectPage():
            return page.getRedirectTarget()

        previous_revision: Optional[str] = None
        if (REDIRECT_TEXT in page.text[:1024]) or (
                (previous_revision := WikiCommands._previous_revision_text(page))
                and REDIRECT_TEXT in previous_revision):
            text = previous_revision if previous_revision else page.text
            start_index = text.index(REDIRECT_TEXT) + len(REDIRECT_TEXT)
            target_page_title = text[start_index:text.index("]]", start_index)].lstrip(': ')
            return Page(page.site, target_page_title)
        return None

    @staticmethod
    def _get_dupe_file_target(page: Page, reason: str) -> Optional[Page]:
        """
        Return the duplicate target if it's in the reason.
        None if it's not there.
        """
        match = FILE_LINK_REGEX.search(reason)
        if match:
            return Page(page.site, "File:" + match.group(1))
