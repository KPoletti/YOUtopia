"""Build a Provider from the config, with its key from secrets.py."""

from collections.abc import Callable
from typing import Any

from youtopia import secrets
from youtopia.config import AISettings
from youtopia.providers.base import Provider, ProviderError
from youtopia.providers.catalog import PROVIDERS


def build_provider(
    settings: AISettings,
    *,
    find_key: Callable[[str], secrets.FoundKey | None] = secrets.find_key,
    transport: Any = None,
) -> Provider:
    """Raises ProviderError with a user-facing reason if the provider can't be built.

    `transport` is for tests: an httpx transport (OpenAI-compatible) or an httpx2 client
    (Anthropic).
    """
    spec = PROVIDERS.get(settings.provider)
    if spec is None:
        raise ProviderError(f"Unknown provider {settings.provider!r}.")
    model = settings.model or spec.default_model
    if not model:
        raise ProviderError(
            f"No model set for {spec.name}. Run: youtopia config set ai.model <model-id>"
        )
    base_url = settings.base_url or spec.base_url
    if not base_url:
        raise ProviderError(
            f"No URL set for {spec.name}. Run: youtopia config set ai.base_url <url>"
        )
    found = find_key(spec.name)
    if spec.needs_key and found is None:
        raise ProviderError(f"No API key for {spec.name}. Run: youtopia auth set {spec.name}")
    key = found.value if found else None

    if spec.adapter == "anthropic":
        from youtopia.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            model, key or "", base_url=base_url, timeout_s=settings.timeout_s,
            http_client=transport,
        )  # fmt: skip
    from youtopia.providers.openai_compat import OpenAICompatProvider

    return OpenAICompatProvider(
        spec.name, model, key, base_url=base_url, timeout_s=settings.timeout_s,
        transport=transport,
    )  # fmt: skip
