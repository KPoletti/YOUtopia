"""Support and crisis resources for `youtopia help-now`.

Static and offline on purpose: no AI, no network, nothing generated. Review any change by hand.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Resource:
    name: str
    detail: str


EMERGENCY_INTRO = (
    "If you or someone else is in immediate danger, call your local emergency number now."
)

EMERGENCY_NUMBERS = (
    Resource("EU and many other countries", "112"),
    Resource("US and Canada", "911"),
    Resource("UK", "999 or 112"),
    Resource("Australia", "000"),
)

HELPLINES = (
    Resource("Find a helpline in your country", "https://findahelpline.com (free, confidential)"),
    Resource("US: Suicide & Crisis Lifeline", "call or text 988"),
    Resource("UK and Ireland: Samaritans", "call 116 123, free, any time"),
)

CLOSING = (
    "Talking to someone you trust, or to your doctor, can help too. "
    "You don't need a crisis to reach out."
)
