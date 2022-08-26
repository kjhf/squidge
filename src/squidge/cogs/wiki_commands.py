"""Wiki commands cog."""
import asyncio
import json
import logging
import re
from itertools import chain
from typing import Optional, Union, Dict, List

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


class WikiCommands(commands.Cog):
    """A grouping of wiki commands."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.permissions = {}
        pywikibot.config.usernames['splatoon']['*'] = os.getenv("WIKI_USERNAME")
        pywikibot.config.default_edit_summary = DEFAULT_EDIT
        # Find the password file
        file = ".pwd"
        for i in range(0, 10):
            if os.path.exists(file):
                pywikibot.config.password_file = file
                break
            else:
                file = "../" + file
        else:
            logging.warning("Wiki password file not found. Wiki commands that require login will not work.")

        pywikibot.config.put_throttle = 1  # i.e. 1 operation per second throttle

        # Disable the PyTypeChecker here as an APISite is returned from the Site interface.
        # noinspection PyTypeChecker
        self.inkipedia: APISite = Site(code='', fam='splatoon', url="https://splatoonwiki.org")
        self.__setattr__("_noDeletePrompt", True)  # See ...\pywikibot\page\_pages.py  # TODO: This...... doesn't work :(

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
                    self.permissions["false-positives"] = permissions_json.get("false-positives", [])
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
                        await ctx.send(f"{user} is already blocked, skipping...")
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
                                logging.info(f"{first_revision.user=} == {user_to_nuke.username=} ? {first_revision.user == user_to_nuke.username}")
                                if first_revision.user == user_to_nuke.username:
                                    page.delete(reason=EDIT_WITH_AUTHORIZED_BY + ctx.author.__str__() + ": [[Inkipedia:Policy/Vandalism|Vandalism]]")
                                else:
                                    logging.info(f"Reverting page={page.title()}")
                                    self.inkipedia.rollbackpage(page, user=user_to_nuke)  # This will fail on the API if the last user is not the user to nuke
                            except Exception as error:
                                logging.error(error)
                    await ctx.send(f"Finished nuking {user}.")
            else:
                await ctx.send(f"User {user} was not found.")
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
                    if "Troublemaker" in content:
                        # If it's the "Troublemaker" account skip all the checks and ping
                        return f"🦹 Troublemaker is back. {message.jump_url} " + await self._get_patrol_pings()

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
                            matched_phrases = set()
                            current_level = "low"
                            for match in profanity_matches:
                                phrase = match["match"]
                                if phrase not in self.permissions["false-positives"]:
                                    matched_phrases.add(phrase)
                                    if match["intensity"] == "high":
                                        current_level = "high"
                                    elif match["intensity"] == "medium" and current_level != "high":
                                        current_level = "medium"

                            if matched_phrases:
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
                                logging.info(f"handle_inkipedia_event: ✔ Checked but had only false positives")
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
        description="Add a false positive result to the swear filter to allow it next time.",
        brief="Add a false positive result to the swear filter to allow it next time.",
        aliases=['false_positive'],
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

        self.permissions["false-positives"].append(phrase)
        channel: TextChannel = self.bot.get_channel(int(os.getenv("WIKI_PERMISSIONS_CHANNEL")))
        await channel.send(json.dumps(self.permissions))
        await ctx.send(f"Added {phrase} to false positives!")

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

#     @commands.command(
#         name='s3',
#         description="Splat 3 updates.",
#         brief="Splat 3 updates.",
#         help=f'{COMMAND_SYMBOL}s3',
#         pass_ctx=True)
#     async def s3(self, ctx: Context):
#         await self.conditional_load_permissions()
#         if not self._is_editor(ctx.author):
#             await ctx.send(f"You don't have permission to do that.")
#             return

#         # https://github.com/Leanny/leanny.github.io/tree/master/splat3
#         with open("../../../USen.json", 'r', encoding='utf-8') as f:
#             language: Dict[str, str] = json.load(f)

#         with open("../../../WeaponInfoMain.json", 'r', encoding='utf-8') as infile:
#             main_weapons: List[dict] = json.load(infile)

#         for wep in main_weapons:
#             local_name = wep["__RowId"]
#             english_name = language.get(local_name)
#             if not english_name:
#                 logging.warning("No English name for " + local_name)
#                 continue

#             english_page = Page(self.inkipedia, english_name)
#             if not english_page.exists():
#                 logging.warning("The page for " + english_name + " does not exist.")
#                 continue

#             ui_params = wep.get("UIParam", [])
#             ui_params = {obj["Type"]: obj["Value"] for obj in ui_params}
#             ui_range = ui_params.get("Range")
#             ui_damage = ui_params.get("Power")
#             ui_impact = ui_params.get("Explosion")
#             ui_fire_rate = ui_params.get("Blaze")
#             ui_charge_speed = ui_params.get("Charge")
#             ui_ink_speed = ui_params.get("PaintSpeed")
#             ui_mobility = ui_params.get("Mobility")
#             ui_durability = ui_params.get("Defence")
#             ui_handling = ui_params.get("Weight")

#             level = wep.get("ShopUnlockRank")
#             points = wep.get("SpecialPoint")
#             sub = wep.get("SubWeapon")
#             if sub:
#                 sub = re.match(r"Work/Gyml/(.+)\.spl__WeaponInfoSub.gyml", sub).group(1)
#                 sub = language.get(sub)
#             special = wep.get("SpecialWeapon")
#             if special:
#                 special = re.match(r"Work/Gyml/(.+)\.spl__WeaponInfoSpecial.gyml", special).group(1)
#                 special = language.get(special)

#             await ctx.send(f"""<{english_page.full_url()}>\n```
#             {{{{Infobox/Weapon
# |game=Splatoon 3
# |image=S3 Weapon Main {english_name}.png
# |size=354px
# |category=Main
# |class=
# |sub={sub or "?"}
# |special={special or "?"}
# |level={level or "?"}
# |points={points or "?"}
# {"|range=" + str(ui_range) if ui_range else ""}
# {"|damage=" + str(ui_damage) if ui_damage else ""}
# {"|impact=" + str(ui_impact) if ui_impact else ""}
# {"|fire_rate=" + str(ui_fire_rate) if ui_fire_rate else ""}
# {"|charge_speed=" + str(ui_charge_speed) if ui_charge_speed else ""}
# {"|ink_speed=" + str(ui_ink_speed) if ui_ink_speed else ""}
# {"|mobility=" + str(ui_mobility) if ui_mobility else ""}
# {"|durability=" + str(ui_durability) if ui_durability else ""}
# {"|handling=" + str(ui_handling) if ui_handling else ""}
# }}}}```""")
