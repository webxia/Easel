"""Internal output decisions. Validators and the existing workflow own authority."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib


class OutputOutcome(str, Enum):
    ACCEPT = 'ACCEPT'
    NORMALIZE = 'NORMALIZE'
    BOUNDED_REPAIR = 'BOUNDED_REPAIR'
    REJECT = 'REJECT'


@dataclass(frozen=True)
class OutputDecision:
    outcome: OutputOutcome
    stage: str
    code: str
    field_path: str | None = None
    input_sha256: str | None = None
    policy_revision: str = 'model-output-contract@1'

    def as_dict(self) -> dict:
        result = asdict(self)
        result['outcome'] = self.outcome.value
        return result


def output_decision(stage, outcome, code, *, text=None, field_path=None, policy_revision='model-output-contract@1'):
    return OutputDecision(OutputOutcome(outcome), stage, code, field_path,
                          hashlib.sha256(text.encode()).hexdigest() if isinstance(text, str) else None,
                          policy_revision).as_dict()
