"""Any server that speaks the OpenAI chat-completions API: OpenAI, OpenRouter, Groq,
Mistral, Ollama, LM Studio, vLLM and your own."""

import httpx

from youtopia.providers.base import ProviderError, RetryableError, check_url, with_one_retry

MAX_ERROR_BODY = 200


class OpenAICompatProvider:
    def __init__(
        self,
        name: str,
        model: str,
        api_key: str | None,
        *,
        base_url: str,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self._key = api_key
        self._url = check_url(base_url) + "/chat/completions"
        self._timeout = timeout_s
        self._transport = transport

    def __repr__(self) -> str:
        return f"OpenAICompatProvider(name={self.name!r}, model={self.model!r})"

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        return with_one_retry(lambda: self._once(system, user, max_tokens))

    def _once(self, system: str, user: str, max_tokens: int) -> str:
        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(
                timeout=self._timeout, transport=self._transport, follow_redirects=False
            ) as client:
                response = client.post(self._url, json=body, headers=headers)
        except httpx.TimeoutException as err:
            raise RetryableError("The provider timed out.", secrets=[self._key]) from err
        except httpx.HTTPError as err:
            raise ProviderError(f"Couldn't reach the provider: {err}", secrets=[self._key]) from err

        if response.status_code >= 400:
            message = (
                f"The provider returned HTTP {response.status_code}: "
                f"{response.text[:MAX_ERROR_BODY]}"
            )
            error = RetryableError if response.status_code >= 500 else ProviderError
            raise error(message, secrets=[self._key])

        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as err:
            raise ProviderError("The provider's reply wasn't in the expected format.") from err
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("The model returned no text.")
        return text.strip()
