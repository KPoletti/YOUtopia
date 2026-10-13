import json

import anthropic
import httpx
import httpx2
import pytest

from youtopia.config import AISettings
from youtopia.providers import base
from youtopia.providers.anthropic import AnthropicProvider
from youtopia.providers.base import ProviderError, RetryableError
from youtopia.providers.openai_compat import OpenAICompatProvider
from youtopia.providers.registry import build_provider
from youtopia.secrets import FoundKey

KEY = "sk-test-0123456789abcdef"


# --- transport rules ------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    ["https://api.example.com/v1", "http://localhost:11434/v1", "http://127.0.0.1:1234",
     "http://[::1]:8080/v1"],
)  # fmt: skip
def test_allowed_urls(url):
    assert base.check_url(url + "/") == url


@pytest.mark.parametrize(
    "url", ["http://api.example.com/v1", "ftp://example.com", "http://10.0.0.5/v1", "nonsense"]
)
def test_rejected_urls(url):
    with pytest.raises(ProviderError):
        base.check_url(url)


def test_redaction():
    text = (
        f"boom: Authorization: Bearer {KEY}, x-api-key: {KEY} "
        "api_key=abc123 other sk-proj-ZZZZZZZZZZZZ and secret-value"
    )
    cleaned = base.redact(text, secrets=["secret-value"])
    assert KEY not in cleaned
    assert "abc123" not in cleaned
    assert "sk-proj-" not in cleaned
    assert "secret-value" not in cleaned
    assert "boom" in cleaned


def test_provider_error_is_redacted():
    assert KEY not in str(ProviderError(f"failed with {KEY}", secrets=[KEY]))


def test_one_retry_only():
    calls = []

    def flaky():
        calls.append(1)
        raise RetryableError("timeout")

    with pytest.raises(RetryableError):
        base.with_one_retry(flaky)
    assert len(calls) == 2


# --- OpenAI-compatible ---------------------------------------------------------------


def openai_reply(text="hello"):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def openai_provider(handler, key=KEY, url="https://api.example.com/v1"):
    return OpenAICompatProvider(
        "openai", "gpt-x", key, base_url=url, timeout_s=5, transport=httpx.MockTransport(handler)
    )


def test_openai_request_shape():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return openai_reply("ready")

    assert openai_provider(handler).complete("sys", "hi", max_tokens=50) == "ready"
    assert seen["url"] == "https://api.example.com/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    assert seen["body"]["model"] == "gpt-x"
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]


def test_openai_without_key_sends_no_auth_header():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return openai_reply()

    openai_provider(handler, key=None, url="http://localhost:11434/v1").complete(
        "s", "u", max_tokens=5
    )
    assert seen["auth"] is None


def test_openai_retries_once_on_5xx_then_succeeds():
    responses = [httpx.Response(503, text="busy"), openai_reply("second")]
    assert openai_provider(lambda r: responses.pop(0)).complete("s", "u", max_tokens=5) == "second"


def test_openai_gives_up_after_one_retry():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError, match="timed out"):
        openai_provider(handler).complete("s", "u", max_tokens=5)
    assert len(calls) == 2


def test_openai_4xx_is_not_retried_and_is_redacted():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text=f"bad key {KEY}")

    with pytest.raises(ProviderError) as err:
        openai_provider(handler).complete("s", "u", max_tokens=5)
    assert len(calls) == 1
    assert "401" in str(err.value)
    assert KEY not in str(err.value)


@pytest.mark.parametrize("payload", [{"choices": []}, {"nope": 1}, {"choices": [{"message": {}}]}])
def test_openai_bad_reply_shape(payload):
    with pytest.raises(ProviderError, match="expected format|no text"):
        openai_provider(lambda r: httpx.Response(200, json=payload)).complete(
            "s", "u", max_tokens=5
        )


def test_openai_rejects_plain_http_remote():
    with pytest.raises(ProviderError, match="HTTPS"):
        openai_provider(openai_reply, url="http://api.example.com/v1")


# --- Anthropic -----------------------------------------------------------------------


def claude_reply(text="hello", stop_reason="end_turn"):
    return httpx2.Response(
        200,
        json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-x",
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason,
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )  # fmt: skip


def claude_provider(handler):
    client = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    return AnthropicProvider(
        "claude-x", KEY, base_url="https://api.anthropic.com", timeout_s=5, http_client=client
    )


def test_anthropic_request_shape():
    seen = {}

    def handler(request):
        seen["key"] = request.headers.get("x-api-key")
        seen["body"] = json.loads(request.content)
        return claude_reply("ready")

    assert claude_provider(handler).complete("sys", "hi", max_tokens=50) == "ready"
    assert seen["key"] == KEY
    assert seen["body"]["system"] == "sys"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert seen["body"]["max_tokens"] == 50


def test_anthropic_retries_once_on_5xx():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(500, json={"type": "error", "error": {"message": "oops"}})

    with pytest.raises(ProviderError, match="500"):
        claude_provider(handler).complete("s", "u", max_tokens=5)
    assert len(calls) == 2


def test_anthropic_timeout_is_retried_once():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx2.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError, match="timed out"):
        claude_provider(handler).complete("s", "u", max_tokens=5)
    assert len(calls) == 2


def test_anthropic_4xx_not_retried_and_redacted():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(
            401, json={"type": "error", "error": {"message": f"invalid x-api-key: {KEY}"}}
        )

    with pytest.raises(ProviderError) as err:
        claude_provider(handler).complete("s", "u", max_tokens=5)
    assert len(calls) == 1
    assert KEY not in str(err.value)


def test_anthropic_refusal_is_an_error():
    with pytest.raises(ProviderError, match="declined"):
        claude_provider(lambda r: claude_reply("", "refusal")).complete("s", "u", max_tokens=5)


# --- registry and repr ---------------------------------------------------------------


def key_for(value):
    return lambda provider: FoundKey(value, "test") if value else None


def test_registry_builds_each_adapter():
    claude = build_provider(AISettings(provider="anthropic"), find_key=key_for(KEY))
    assert isinstance(claude, AnthropicProvider)
    assert claude.model == "claude-opus-5-5"
    local = build_provider(AISettings(provider="ollama", model="llama3.2"), find_key=key_for(None))
    assert isinstance(local, OpenAICompatProvider)


@pytest.mark.parametrize(
    "settings, message",
    [
        (AISettings(provider="anthropic"), "No API key"),
        (AISettings(provider="openai"), "No model"),
        (AISettings(provider="custom", model="m"), "No URL"),
        (AISettings(provider="custom", model="m", base_url="http://example.com"), "HTTPS"),
    ],
)
def test_registry_explains_what_is_missing(settings, message):
    with pytest.raises(ProviderError, match=message):
        build_provider(settings, find_key=key_for(None))


def test_no_key_in_provider_repr():
    for settings in (AISettings(provider="anthropic"), AISettings(provider="openai", model="m")):
        provider = build_provider(settings, find_key=key_for(KEY))
        assert KEY not in repr(provider)
        assert KEY not in str(vars(provider).get("model"))
