from typing import SupportsInt


def wrap_in_backticks(string: str) -> str:
    """
    Wrap the string in backticks.
    If the string contains an `, it is wrapped in ```.
    Otherwise, only one ` is used either side.
    """
    if '`' in string:
        string = f"```{string}```"
    else:
        string = f"`{string}`"
    return string


def safe_backticks(string: str) -> str:
    """
    Wrap the string in backticks if and only if it requires it.
    If the string contains an `, it is wrapped in ```.
    If the string contains an _ or *, or starts or ends with a space, it is wrapped in `.
    """
    if '`' in string:
        string = f"```{string}```"
    elif '_' in string or '*' in string or string.startswith(' ') or string.endswith(' '):
        string = f"`{string}`"
    return string


def close_backticks_if_unclosed(string: str) -> str:
    if (string.count('```') % 2) == 1:  # If we have an unclosed ```
        string += '```'
    return string


def truncate(string: str, max_length: SupportsInt = 2000, indicator: str = "…") -> str:
    """
    Truncates the given string up to a maximum length (including the truncation string).
    Strings that are already the max_length or less will be returned as-is.
    A truncation indicator is automatically added to strings that have been truncated, but can be specified as empty
    :param string: The string to truncate
    :param max_length: The maximum length of the string
    :param indicator: Indicator appended if truncated
    :return: The resulting string.
    """
    if string is None:
        raise ValueError('string is None.')

    if not isinstance(string, str):
        raise ValueError('string specified to truncate is not a string.')

    if not isinstance(max_length, int):
        max_length = int(max_length)

    if len(indicator) > max_length:
        raise ValueError('Truncation indicator length cannot be greater than the maximum length of the string.')

    if len(string) <= max_length:
        return string

    return string[0:max_length - len(indicator)] + indicator
