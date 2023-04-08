from typing import Optional, Union

from pywikibot import Site
from pywikibot.data import api
from pywikibot.exceptions import PageRelatedError


def get_all_users_generator(
        site: Site,
        aufrom: Optional[str] = None,
        auto: Optional[str] = None,
        auprefix: Optional[str] = None,
        audir: bool = False,
        augroup: Optional[Union[str, list[str]]] = None,
        auexcludegroup: Optional[Union[str, list[str]]] = None,
        aurights: Optional[Union[str, list[str]]] = None,
        auprop: Optional[Union[str, list[str]]] = 'editcount|groups|registration',
        aulimit: Optional[int] = None,
        auwitheditsonly: bool = False,
        auactiveusers: bool = False,
        auattachedwiki: Optional[str] = None
):
    """Iterate registered users, ordered by username.

    Iterated values are dicts containing 'name', 'editcount',
    'registration', and (sometimes) 'groups' keys. 'groups' will be
    present only if the user is a member of at least 1 group, and
    will be a list of str; all the other values are str and should
    always be present.

    .. seealso:: :api:`Allusers`

    :param site: Wiki site object
    :param aufrom: The username to start enumerating from (name need not exist)
    :param auto: The username to stop enumerating at (name need not exist)
    :param auprefix: Search for all users that begin with this value.
    :param audir: Direction to sort in. For simplicity this is implemented as a bool representing reverse order.
                  In the API it is None for ascending or audir=descending.
    :param augroup: Only include users in the given groups. Cannot be used with au_excludegroup.
                    Specify a str list or one string with | to delimit.
    :param auexcludegroup: Exclude users in the given groups. Cannot be used with au_group.
                           Specify a str list or one string with | to delimit.
    :param aurights: Only include users with the given rights.
                     Does not include rights granted by implicit or auto-promoted groups
                     like *, user, or autoconfirmed.
                     Maximum number of values is 50 (500 for clients that are allowed higher limits).
    :param auprop: Which pieces of information to include. Specify a str list or one string with | to delimit.
    :param aulimit: How many total usernames to return. The value must be between 1 and 500.
    :param auwitheditsonly: Only list users who have made edits.
    :param auactiveusers: Only list users active in the last 30 days.
    :param auattachedwiki: With auprop=centralids, also indicate whether the user is attached with the wiki identified by this ID.

    :example: https://www.mediawiki.org/w/api.php?action=query&format=json&list=allusers&formatversion=2

    :example: https://www.mediawiki.org/w/api.php?action=query&format=json&list=allusers&formatversion=2
    &aufrom=a&auto=c&auprefix=b&augroup=autopatrolled%7Cconfirmed%7Cbot%7Cbureaucrat%7Csysop&aurights=autoconfirmed%7Cautopatrol
    &auprop=blockinfo%7Ceditcount%7Cgroups%7Cimplicitgroups%7Cregistration&aulimit=10&auwitheditsonly=1&auactiveusers=1
    """
    au_gen = site._generator(
        api.ListGenerator,
        type_arg='allusers',
        total=aulimit)
    if aufrom:
        au_gen.request['aufrom'] = aufrom
    if auto:
        au_gen.request['auto'] = auto
    if auprefix:
        au_gen.request['auprefix'] = auprefix
    if audir:
        au_gen.request['audir'] = "descending"
    if augroup:
        au_gen.request['augroup'] = augroup if isinstance(augroup, str) else augroup.join('|')
    elif auexcludegroup:
        au_gen.request['auexcludegroup'] = auexcludegroup if isinstance(auexcludegroup, str) else auexcludegroup.join('|')
    if aurights:
        au_gen.request['aurights'] = aurights if isinstance(aurights, str) else aurights.join('|')
    if auprop:
        au_gen.request['auprop'] = auprop if isinstance(auprop, str) else auprop.join('|')
    if aulimit:
        au_gen.request['aulimit'] = str(aulimit)
    if auwitheditsonly:
        au_gen.request['auwitheditsonly'] = "1"
    if auactiveusers:
        au_gen.request['auactiveusers'] = "1"
    if auattachedwiki:
        au_gen.request['auattachedwiki'] = auattachedwiki
    return au_gen


def try_get_user_from_revision(revision):
    try:
        return revision.userName()
    except PageRelatedError:
        return None
