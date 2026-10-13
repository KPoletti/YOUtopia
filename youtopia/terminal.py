"""Make untrusted text (AI output, user notes, error messages) safe to print.

Strips ANSI/OSC/other escape sequences and control characters, then escapes Rich markup,
so text can neither drive the terminal nor restyle the output around it.
"""

import re

from rich.markup import escape

# CSI (ESC [ ... final), OSC (ESC ] ... BEL or ESC \), DCS/SOS/PM/APC (ESC P|X|^|_ ... ST),
# single-character escapes, and 8-bit C1 equivalents.
_ESCAPES = re.compile(
    r"""
    \x1b\[[0-?]*[ -/]*[@-~]                    # CSI
    | \x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?        # OSC
    | \x1b[PX^_][^\x1b]*(?:\x1b\\)?             # DCS, SOS, PM, APC
    | \x1b[@-Z\\-_]                             # other two-character escapes
    | \x9b[0-?]*[ -/]*[@-~]                     # 8-bit CSI
    | [\x90\x98\x9d\x9e\x9f][^\x07\x9c]*[\x07\x9c]?  # 8-bit DCS/SOS/OSC/PM/APC
    """,
    re.VERBOSE,
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def strip_control(text: str, *, keep_newlines: bool = True) -> str:
    """Remove escape sequences and control characters (tabs and, optionally, newlines stay)."""
    text = _ESCAPES.sub("", text)
    text = _CONTROL.sub("", text)
    return text if keep_newlines else re.sub(r"[\r\n]+", " ", text)


def safe(text: object) -> str:
    """Text that's safe to pass to Rich: no escapes, no control characters, no markup."""
    return escape(strip_control(str(text)))
