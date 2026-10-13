import pytest

from youtopia import generator, safety, terminal

UNSAFE = [
    ("Clean the gutters from a ladder", "heights"),
    ("Climb onto the roof to watch the sunset", "heights"),
    ("Have a small bonfire in the garden", "fire and heat"),
    ("Light a candle and meditate", "fire and heat"),
    ("Try a 24-hour water fast", "fasting"),
    ("Skip breakfast to reset your body", "fasting"),
    ("Do push-ups until failure", "extreme exertion"),
    ("Run a marathon this weekend", "extreme exertion"),
    ("Hold your breath for as long as you can", "extreme exertion"),
    ("Invest $50 in a stock you like", "money"),
    ("Buy yourself a new notebook", "money"),
    ("Lend money to a friend", "money"),
    ("Place a small bet on tonight's game", "money"),
    ("Explore an abandoned building nearby", "trespass"),
    ("Climb the fence into the old quarry", "trespass"),
    ("Pour a glass of wine and journal", "alcohol and drugs"),
    ("Try microdosing for focus", "alcohol and drugs"),
    ("Double your vitamin supplements", "alcohol and drugs"),
    ("Knock on doors to meet your neighbours", "strangers' homes"),
    ("Visit a stranger's house to swap books", "strangers' homes"),
    ("Swim in the lake at dawn", "other hazards"),
    ("Drive somewhere you've never been", "other hazards"),
    ("Mix bleach with other cleaners for a deep clean", "other hazards"),
]


@pytest.mark.parametrize("text, theme", UNSAFE)
def test_unsafe_corpus_is_caught(text, theme):
    assert theme in safety.risky_themes([text])


@pytest.mark.parametrize(
    "text",
    [
        "Spend ten minutes sketching your favourite mug.",
        "Write a short thank-you note to a friend.",
        "Water your plants and remove any dead leaves.",
        "Solve five mental maths problems and check them.",
        "Stretch your shoulders gently, stopping if anything hurts.",
        "Make a cup of tea and drink it slowly, without your phone nearby.",
    ],
)
def test_ordinary_tasks_pass(text):
    assert safety.risky_themes([text]) == []


def test_built_in_library_passes_the_filter():
    for t in generator.load_templates():
        assert safety.risky_themes([t.title, t.instructions, t.done_criteria]) == [], t.title


def test_ability_conflicts_only_for_excluded_tags():
    text = ["Go for a short walk and listen to a podcast"]
    assert set(safety.ability_conflicts(text, {"walking", "hearing"})) == {"walking", "hearing"}
    assert safety.ability_conflicts(text, {"kneeling"}) == []
    assert safety.ability_conflicts(text, set()) == []


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("\x1b[31mred\x1b[0m", "red"),
        ("\x1b]52;c;ZXZpbA==\x07copied", "copied"),  # OSC 52 clipboard write
        ("\x1b]8;;https://evil.example\x1b\\link\x1b]8;;\x1b\\", "link"),  # OSC 8 hyperlink
        ("\x1bPdevice\x1b\\after", "after"),
        ("bell\x07 and\x08 backspace\r", "bell and backspace"),
        ("\x9b31mC1 csi", "C1 csi"),
        ("tabs\tand\nnewlines", "tabs\tand\nnewlines"),
    ],
)
def test_strip_control(raw, expected):
    assert terminal.strip_control(raw) == expected


def test_safe_escapes_rich_markup():
    assert terminal.safe("[bold red]boo[/bold red]") == "\\[bold red]boo\\[/bold red]"
    assert terminal.safe("\x1b[31m[link=x]hi") == "\\[link=x]hi"
