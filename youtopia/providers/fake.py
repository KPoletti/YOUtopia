"""A scripted provider for tests: no network, records every prompt it receives."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class Call:
    system: str
    user: str
    max_tokens: int


class FakeProvider:
    def __init__(
        self, responses: Iterable[str | Exception] = (), *, name="fake", model="fake-1"
    ) -> None:
        self.name = name
        self.model = model
        self._responses = list(responses)
        self.calls: list[Call] = []

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        self.calls.append(Call(system, user, max_tokens))
        if not self._responses:
            raise AssertionError("FakeProvider ran out of scripted responses")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
