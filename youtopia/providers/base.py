"""The Provider protocol, its error type, and the transport rules every adapter follows."""

import re
from collections.abc import Callable, Iterable
from typing import Protocol
from urllib.parse import urlsplit

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Header values and well-known key shapes that must never appear in an error message.
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?[^\s,;'\"]+"),
    re.compile(r"(?i)(x-api-key\s*[:=]\s*)[^\s,;'\"]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;'\"]+"),
    re.compile(r"()\b(sk|rk|pk|gsk|or)-[A-Za-z0-9_\-]{8,}"),
)
REDACTED = "[redacted]"


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        """Return the model's text reply. Raises ProviderError on any failure."""
        ...


class ProviderError(Exception):
    """Any provider failure. The message is redacted, so it is safe to show."""

    def __init__(self, message: str, *, secrets: Iterable[str | None] = ()) -> None:
        super().__init__(redact(message, secrets))


class RetryableError(ProviderError):
    """A timeout or 5xx response: worth exactly one more try."""


def redact(text: str, secrets: Iterable[str | None] = ()) -> str:
    """Remove the given secrets, Authorization/API-key headers and key-shaped tokens."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + REDACTED, text)
    return text


def check_url(url: str) -> str:
    """Allow HTTPS anywhere, plain HTTP only on this machine. Returns the URL without a
    trailing slash."""
    parts = urlsplit(url)
    if parts.username or parts.password:
        raise ProviderError("Provider URLs must not contain credentials.")
    if not parts.hostname:
        raise ProviderError(f"Not a valid provider URL: {url!r}.")
    if parts.scheme == "https":
        return url.rstrip("/")
    if parts.scheme == "http" and parts.hostname in LOCAL_HOSTS:
        return url.rstrip("/")
    raise ProviderError(
        f"Provider URLs must use HTTPS (plain HTTP is only allowed for localhost): {url!r}."
    )


def with_one_retry[T](call: Callable[[], T]) -> T:
    """Run `call`, retrying once if it raises RetryableError."""
    try:
        return call()
    except RetryableError:
        return call()
