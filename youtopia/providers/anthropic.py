"""Claude models through the official Anthropic SDK."""

from typing import Any

from youtopia.providers.base import ProviderError, RetryableError, check_url, with_one_retry


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        base_url: str,
        timeout_s: float,
        http_client: Any = None,
    ) -> None:
        import anthropic  # imported lazily: only needed when AI is on

        self.model = model
        self._key = api_key
        self._sdk = anthropic
        self._client = anthropic.Anthropic(
            api_key=api_key,
            base_url=check_url(base_url),
            timeout=timeout_s,
            max_retries=0,  # retries follow our own rule: one, on timeout or 5xx only
            http_client=http_client,
        )

    def __repr__(self) -> str:
        return f"AnthropicProvider(model={self.model!r})"

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        return with_one_retry(lambda: self._once(system, user, max_tokens))

    def _once(self, system: str, user: str, max_tokens: int) -> str:
        sdk = self._sdk
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except sdk.APITimeoutError as err:
            raise RetryableError("The provider timed out.", secrets=[self._key]) from err
        except sdk.APIStatusError as err:
            message = f"The provider returned HTTP {err.status_code}: {err.message}"
            if err.status_code >= 500:
                raise RetryableError(message, secrets=[self._key]) from err
            raise ProviderError(message, secrets=[self._key]) from err
        except sdk.APIError as err:
            raise ProviderError(f"Couldn't reach the provider: {err}", secrets=[self._key]) from err

        if response.stop_reason == "refusal":
            raise ProviderError("The model declined this request.")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise ProviderError("The model returned no text.")
        return text
