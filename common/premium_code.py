"""
Copyright 2020-2023 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import codecs
import re
import secrets
import typing

import interactions as ipy

__all__ = ("full_code_generate", "full_code_validate", "bytestring_length_decode")

# code modified from https://github.com/brett-patterson/coupon_codes - 2015 Brett Patterson, MIT License

BAD_WORDS: typing.Final[frozenset[str]] = frozenset(
    codecs.decode(w, "rot13")
    for w in (
        "SHPX",
        "PHAG",
        "JNAX",
        "JNAT",
        "CVFF",
        "PBPX",
        "FUVG",
        "GJNG",
        "GVGF",
        "SNEG",
        "URYY",
        "ZHSS",
        "QVPX",
        "XABO",
        "NEFR",
        "FUNT",
        "GBFF",
        "FYHG",
        "GHEQ",
        "FYNT",
        "PENC",
        "CBBC",
        "OHGG",
        "SRPX",
        "OBBO",
        "WVFZ",
        "WVMM",
        "CUNG",
    )
)


SYMBOLS: typing.Final[list[str]] = list("0123456789ABCDEFGHJKLMNPQRTUVWXY")
SYMBOLS_LENGTH: typing.Final[int] = len(SYMBOLS)

SYMBOLS_MAP: typing.Final[dict[str, int]] = {s: i for i, s in enumerate(SYMBOLS)}

PART_SEP: typing.Final[str] = "-"

REPLACEMENTS: typing.Final[list[tuple[re.Pattern, str]]] = [
    (re.compile(r"[^0-9A-Z-]+"), ""),
    (re.compile(r"O"), "0"),
    (re.compile(r"I"), "1"),
    (re.compile(r"Z"), "2"),
    (re.compile(r"S"), "5"),
]


def has_bad_word(code: str) -> bool:
    """Check if a given code contains a bad word."""
    return any(word in code for word in BAD_WORDS)


def check_digit(data: str, n: int) -> str:
    """Generate the check digit for a code part."""
    for c in data:
        n = n * 19 + SYMBOLS_MAP[c]
    return SYMBOLS[n % (SYMBOLS_LENGTH - 1)]


def rpl_checksum(clamped_max_uses: int, user_id: ipy.Snowflake_Type) -> str:
    """Generate the check digit for a full code."""
    user_id = str(user_id)
    sum_user_id = sum(ord(c) + int(c) + clamped_max_uses for c in user_id)
    return SYMBOLS[SYMBOLS_LENGTH - 1 - (sum_user_id % 11)]


def base_code_generate(*, n_parts: int = 3, part_len: int = 4) -> str:
    """
    Generate the base part of the code.

    Parameters:
    -----------

    n_parts : int
        The number of parts for the code.

    part_len : int
        The number of symbols in each part.

    Returns:
    --------
    A base code string.
    """
    parts = []

    while not parts or has_bad_word("".join(parts)):
        for i in range(n_parts):
            part = "".join(secrets.choice(SYMBOLS) for _ in range(part_len - 1))
            part += check_digit(part, i + 1)
            parts.append(part)

    return PART_SEP.join(parts)


def full_code_generate(
    max_uses: int, user_id: typing.Optional[ipy.Snowflake_Type] = None
) -> str:
    clamped_max_uses = max_uses % 11
    max_uses_char = SYMBOLS[clamped_max_uses + 11]
    check_chara = rpl_checksum(clamped_max_uses, user_id) if user_id else "A"
    return f"PL{max_uses_char}{check_chara}-{base_code_generate()}"


def base_code_validate(code: str, *, n_parts: int = 3, part_len: int = 4) -> str:
    """
    Validate a given code.

    Parameters:
    -----------
    code : str
        The code to validate.

    n_parts : int
        The number of parts for the code.

    part_len : int
        The number of symbols in each part.

    Returns:
    --------
    A cleaned code if the code is valid, otherwise an empty string.
    """
    parts = code.split(PART_SEP)
    if len(parts) != n_parts:
        return ""

    for i, part in enumerate(parts):
        if len(part) != part_len:
            return ""

        data = part[:-1]
        check = part[-1]

        if check != check_digit(data, i + 1):
            return ""

    return code


def full_code_validate(code: str, user_id: ipy.Snowflake_Type) -> str:
    # handles all the checks for a proper code, which includes the first part before -s
    code = code.upper()
    for replacement in REPLACEMENTS:
        code = replacement[0].sub(replacement[1], code)

    if not code.startswith("PL"):
        return ""

    first_part = code.split(PART_SEP, maxsplit=1)[0]
    if len(first_part) != 4:
        return ""

    max_uses_symbol = first_part[2]
    try:
        clamped_max_uses = SYMBOLS.index(max_uses_symbol) - 11
    except ValueError:
        return ""

    if clamped_max_uses < 0 or clamped_max_uses > 10:
        return ""

    if first_part[3] == "A":
        check_chara = "A"
    else:
        check_chara = rpl_checksum(clamped_max_uses, user_id)

    if not code.startswith(f"PL{max_uses_symbol}{check_chara}-"):
        return ""

    if base_code_validate(code.removeprefix(f"PL{max_uses_symbol}{check_chara}-")):
        return code
    return ""


def bytestring_length_decode(the_input: str) -> int:
    the_input = the_input.removeprefix("b'").removesuffix("'")
    try:
        return len(the_input.encode().decode("unicode_escape"))
    except UnicodeDecodeError:
        return -1
