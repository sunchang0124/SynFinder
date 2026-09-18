"""The researcher's answers."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PRIVACY = Literal["none", "deidentified_ok", "formal_dp_required"]


class Intake(BaseModel):
    # core four — required
    domain: str
    data_type: str
    purpose: str
    privacy: PRIVACY

    # constraints and resources
    compute: str | None = None
    expertise: str | None = None
    expected_rows: int | None = None
    variable_types: list[str] = Field(default_factory=list)
    require_open_license: bool | None = None

    # fidelity and evaluation
    preserves: list[str] = Field(default_factory=list)

    # governance and acceptance
    needs_governance_evidence: bool | None = None

    def answered(self, axis: str) -> bool:
        """True when the user supplied an answer driving this axis.

        An unanswered axis is dropped from the weighted mean entirely — it
        is never scored as zero.
        """
        value = getattr(self, axis, None)
        if isinstance(value, list):
            return len(value) > 0
        return value is not None
