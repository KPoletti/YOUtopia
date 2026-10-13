"""Safety filter for generated text: anything that matches is rejected and replaced by a
built-in task. Deliberately cautious, since a false positive only costs one template swap."""

import re
from collections.abc import Collection, Iterable

# Risky themes. Each pattern is matched case-insensitively against the whole task text.
DENY_PATTERNS: dict[str, tuple[str, ...]] = {
    "heights": (
        r"\bladders?\b", r"\broof(top)?s?\b", r"\bclimb(ing)?\b(?! stairs)", r"\bcliffs?\b",
        r"\bscaffold", r"\bat height\b", r"\bledges?\b", r"\bbalcony railing",
    ),
    "fire and heat": (
        r"\bfires?\b", r"\bflames?\b", r"\bcandles?\b", r"\bbonfire", r"\blighters?\b",
        r"\bmatches to\b", r"\bblowtorch", r"\bfireworks?\b", r"\bdeep[- ]fr(y|ied|ying)",
        r"\bhot oil\b", r"\bburn(ing)? (something|it|paper|leaves)", r"\bfuel\b", r"\bpetrol\b",
        r"\bgasoline\b",
    ),
    "fasting": (
        r"\bfast(ing)?\b(?!er| as)", r"\bskip(ping)? (a |your )?(meals?|breakfast|lunch|dinner)",
        r"\bdon'?t eat\b", r"\bcalorie restrict", r"\bstarv", r"\bdetox\b", r"\bcleanse\b",
    ),
    "extreme exertion": (
        r"\bmarathon", r"\bultra(marathon)?\b", r"\bto exhaustion\b", r"\buntil (failure|you drop)",
        r"\bas (hard|fast) as (you )?(can|possible)\b", r"\bmax(imum)? (effort|reps|weight)",
        r"\bhold your breath\b", r"\bice baths?\b", r"\bcold plunge", r"\bno water\b",
        r"\bhundreds? of (push|sit|squat|burpee)", r"\bsprints?\b",
    ),
    "money": (
        r"\binvest", r"\bstocks?\b", r"\bshares\b(?! with)", r"\bcrypto", r"\bbitcoin",
        r"\btrading\b", r"\bgambl", r"\bbet(s|ting)?\b", r"\blottery", r"\bcasino",
        r"\bloans?\b", r"\bborrow(ing)? money", r"\blend(ing)? money", r"\bcredit cards?\b",
        r"\bdebt\b", r"\bwire (money|transfer)", r"\bsend money\b", r"\bbank details\b",
        r"\bpassword", r"\bpin number", r"\bbuy\b", r"\bpurchase", r"\bdonate\b",
        r"\bspend(ing)? (money|cash|on)\b",
        r"[$£€]\s?\d",
    ),
    "trespass": (
        r"\btrespass", r"\bbreak(ing)? into\b", r"\bsneak(ing)? into\b",
        r"\babandoned (building|house|factory|site)", r"\bprivate property\b",
        r"\bclimb(ing)? (over )?(a |the )?(fence|wall|gate)", r"\brailway tracks?\b",
        r"\bconstruction site",
    ),
    "alcohol and drugs": (
        r"\balcohol", r"\bbeers?\b", r"\bwines?\b", r"\bvodka", r"\bwhisk(e)?y", r"\bliquor",
        r"\bcocktails?\b", r"\bdrunk", r"\bbooze", r"\bdrugs?\b", r"\bcannabis", r"\bmarijuana",
        r"\bpsychedelic", r"\bmicrodos", r"\bcbd\b", r"\bsmok(e|ing)\b", r"\bvap(e|ing)\b",
        r"\bmedication", r"\bdosage\b", r"\bsupplements?\b", r"\bpills?\b",
    ),
    "strangers' homes": (
        r"\bstranger'?s?'? (home|house|flat|apartment|car)",
        r"\b(enter|go into|visit) (a )?stranger",
        r"\bdoor[- ]to[- ]door\b", r"\bknock(ing)? on (doors|a stranger)", r"\bhitchhik",
        r"\bmeet (up with )?(a |an online )?stranger", r"\bget in(to)? (a |someone'?s )?car",
    ),
    "other hazards": (
        r"\bweapons?\b", r"\bguns?\b", r"\bfirearms?\b", r"\bknife (fight|throw)", r"\bbleach\b",
        r"\bmix(ing)? (cleaning )?chemicals", r"\bswim(ming)? in (a |the )?(lake|sea|river|ocean)",
        r"\bopen water\b", r"\bdriv(e|ing)\b(?! you)", r"\bself[- ]harm", r"\bsuicid",
        r"\bkill\b", r"\bhack(ing)?\b", r"\bprank", r"\bdare\b",
    ),
}  # fmt: skip

# Activities that rely on an ability, re-checked against the user's accessibility limits
# even when the model left the `requires` tag off.
ABILITY_PATTERNS: dict[str, tuple[str, ...]] = {
    "standing": (r"\bstand(ing)?\b", r"\bon your feet\b"),
    "walking": (r"\bwalk", r"\bstroll", r"\bhik(e|ing)\b", r"\bjog", r"\brun(ning)?\b"),
    "kneeling": (r"\bkneel", r"\bon your knees\b"),
    "lifting": (r"\blift", r"\bcarry(ing)?\b", r"\bheavy\b"),
    "exertion": (r"\bjog", r"\brun(ning)?\b", r"\bpush[- ]?ups?\b", r"\bsquats?\b", r"\bjump"),
    "hands": (r"\bknit", r"\bsew", r"\bdraw\b", r"\bsketch", r"\bby hand\b", r"\bchop", r"\bfold"),
    "vision": (r"\bwatch\b", r"\bdraw\b", r"\bsketch", r"\bpaint", r"\bphotograph"),
    "hearing": (r"\blisten", r"\bpodcast", r"\bmusic\b", r"\bphone call", r"\bcall (a|an|your)\b"),
    "speaking": (
        r"\bcall (a|an|your)\b", r"\bphone\b", r"\bsing", r"\baloud\b", r"\bout loud\b",
        r"\btalk to\b", r"\bsay\b",
    ),
    "going_out": (
        r"\boutside\b", r"\boutdoors?\b", r"\bpark\b", r"\bshop\b", r"\bstore\b",
        r"\bneighbou?rhood\b", r"\bgo out\b", r"\bhead out\b", r"\bvisit\b", r"\blibrary\b",
    ),
}  # fmt: skip

_DENY = {
    theme: [re.compile(p, re.IGNORECASE) for p in patterns]
    for theme, patterns in DENY_PATTERNS.items()
}
_ABILITY = {
    tag: [re.compile(p, re.IGNORECASE) for p in patterns]
    for tag, patterns in ABILITY_PATTERNS.items()
}


def risky_themes(texts: Iterable[str]) -> list[str]:
    """The risky themes found in the text, if any."""
    text = " ".join(texts)
    return [theme for theme, patterns in _DENY.items() if any(p.search(text) for p in patterns)]


def ability_conflicts(texts: Iterable[str], excluded_tags: Collection[str]) -> list[str]:
    """Abilities the text relies on that the user's accessibility limits rule out."""
    text = " ".join(texts)
    return [
        tag
        for tag in excluded_tags
        if tag in _ABILITY and any(p.search(text) for p in _ABILITY[tag])
    ]
