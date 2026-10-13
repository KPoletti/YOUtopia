"""The providers YOUtopia knows how to talk to, and their ready-made settings."""

from dataclasses import dataclass
from typing import Literal

Adapter = Literal["anthropic", "openai_compat"]


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    adapter: Adapter
    base_url: str | None  # None: the user must set ai.base_url
    key_env: str | None  # the provider's own environment variable, if it has one
    needs_key: bool
    default_model: str | None = None


PROVIDERS: dict[str, ProviderSpec] = {
    spec.name: spec
    for spec in (
        ProviderSpec(
            "anthropic",
            "anthropic",
            "https://api.anthropic.com",
            "ANTHROPIC_API_KEY",
            needs_key=True,
            default_model="claude-opus-5-5",
        ),
        ProviderSpec(
            "openai", "openai_compat", "https://api.openai.com/v1", "OPENAI_API_KEY", True
        ),
        ProviderSpec(
            "openrouter",
            "openai_compat",
            "https://openrouter.ai/api/v1",
            "OPENROUTER_API_KEY",
            True,
        ),
        ProviderSpec(
            "groq", "openai_compat", "https://api.groq.com/openai/v1", "GROQ_API_KEY", True
        ),
        ProviderSpec(
            "mistral", "openai_compat", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", True
        ),
        ProviderSpec("ollama", "openai_compat", "http://localhost:11434/v1", None, False),
        ProviderSpec("lmstudio", "openai_compat", "http://localhost:1234/v1", None, False),
        ProviderSpec("custom", "openai_compat", None, None, False),
    )
}


def provider_names() -> list[str]:
    return list(PROVIDERS)
