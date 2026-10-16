"""External generation protocol: observation never implies a new submission."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True)
class ProviderCapabilities:
    query_by_task_id: bool = False
    query_by_request_key: bool = False


@dataclass(frozen=True)
class ProviderResult:
    state: Literal["submitted", "succeeded", "failed", "not_found", "unknown"]
    task_id: str | None = None
    result: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.state not in {"submitted", "succeeded", "failed", "not_found", "unknown"}:
            raise ValueError("unsupported provider result state")
        if not isinstance(self.result, dict):
            raise TypeError("provider result must be a JSON object")


class SubmissionNotSent(Exception):
    """Adapter has affirmative evidence no generation request was submitted.

    A timeout or an eventually-consistent lookup returning not_found is NOT
    sufficient evidence. Raw provider error bodies must not be used as messages.
    """


class SubmissionUncertain(Exception):
    """Transport ended without an authoritative submission acknowledgement."""


class GenerationProvider(Protocol):
    provider_id: str
    model: str
    mode: str
    capabilities: ProviderCapabilities

    def submit(self, request: dict, *, request_key: str) -> ProviderResult: ...

    def observe(self, *, task_id: str | None, request_key: str) -> ProviderResult: ...
