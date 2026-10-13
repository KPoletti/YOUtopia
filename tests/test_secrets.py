import keyring
import pytest
from keyring.backends import fail

from youtopia import secrets

KEY = "sk-ant-test-0123456789abcd"


def test_lookup_order(monkeypatch):
    assert secrets.find_key("anthropic") is None

    secrets.set_key("anthropic", "keyring-key-000000wxyz")
    assert secrets.find_key("anthropic").source == "keyring"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "provider-env-key-0000abcd")
    found = secrets.find_key("anthropic")
    assert (found.source, found.value) == ("env ANTHROPIC_API_KEY", "provider-env-key-0000abcd")

    monkeypatch.setenv("YOUTOPIA_API_KEY", "generic-env-key-00001234")
    assert secrets.find_key("anthropic").source == "env YOUTOPIA_API_KEY"


def test_keys_are_per_provider():
    secrets.set_key("openai", KEY)
    assert secrets.find_key("openai").value == KEY
    assert secrets.find_key("groq") is None


def test_mask_shows_last_four_at_most():
    assert secrets.mask(KEY) == "••••abcd"
    assert secrets.mask("short") == "••••"


def test_found_key_never_shows_itself():
    found = secrets.FoundKey(KEY, "keyring")
    assert KEY not in repr(found)
    assert KEY not in str(found)
    assert KEY not in f"{found}"


def test_remove():
    secrets.set_key("mistral", KEY)
    assert secrets.remove_key("mistral") is True
    assert secrets.remove_key("mistral") is False
    assert secrets.find_key("mistral") is None


def test_no_keyring_backend():
    keyring.set_keyring(fail.Keyring())
    assert secrets.find_key("anthropic") is None
    with pytest.raises(secrets.KeyringUnavailable):
        secrets.set_key("anthropic", KEY)
    with pytest.raises(secrets.KeyringUnavailable):
        secrets.remove_key("anthropic")
