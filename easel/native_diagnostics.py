"""Allowlisted lifecycle telemetry; no prompt, raw body or credentials."""
from typing import Literal
from pydantic import Field, field_validator, ValidationError
from .work_bridge import Strict, Identity

class NativeCallDiagnostic(Strict):
    duration_ms: float | int | None = Field(default=None, ge=0)
    request_bytes: int | None = Field(default=None, ge=0)
    response_bytes: int | None = Field(default=None, ge=0)
    outcome: Literal['completed','error'] | None = None

class NativeUsage(Strict):
    input: int | None = Field(default=None, ge=0)
    output: int | None = Field(default=None, ge=0)
    cacheRead: int | None = Field(default=None, ge=0)
    cacheWrite: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)

class NativeDiagnostic(Strict):
    parameter_source: Literal['configured_not_wire'] | None = None
    provider: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.:/-]{1,128}$')
    model: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.:/-]{1,128}$')
    duration_ms: float | int | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)
    model_max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: Literal['off','none','low','medium','high','xhigh','max','adaptive'] | None = None
    thinking: Literal['adaptive','disabled'] | None = None
    stop_reason: Literal['stop','length','toolUse','error','aborted'] | None = None
    provider_finish_reason: Literal['stop','length','tool_calls','function_call','content_filter'] | None = None
    response_id_hash: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    text_chars: int | None = Field(default=None, ge=0)
    reasoning_chars: int | None = Field(default=None, ge=0)
    tool_calls: int | None = Field(default=None, ge=0)
    usage: NativeUsage | None = None
    usage_status: Literal['reported','missing_or_zero'] | None = None
    calls: list[NativeCallDiagnostic] = Field(default_factory=list, max_length=8)

class NativeEnd(Identity):
    diagnostic: NativeDiagnostic | None = None

    @field_validator('diagnostic', mode='before')
    @classmethod
    def optional_telemetry(cls, value):
        if value is None:return None
        try:return NativeDiagnostic.model_validate(value)
        except (ValidationError, TypeError):
            # Telemetry must never prevent an authenticated native end callback.
            # Discard invalid/unknown fields rather than recording raw data.
            return None
