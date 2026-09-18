"""Pydantic models for catalog entries."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Scale(BaseModel):
    """The demonstrated size envelope, and where that claim comes from.

    `evidence` cites the paper table or repository example the numbers were
    read off. A Scale with bounds but no evidence is a guess, and the loader
    rejects it — see `_scale_needs_evidence`.
    """

    min_rows: int | None = None
    max_rows: int | None = None
    max_cols: int | None = None
    evidence: str | None = None

    @model_validator(mode="after")
    def _scale_needs_evidence(self) -> "Scale":
        stated = (self.min_rows, self.max_rows, self.max_cols)
        if any(v is not None for v in stated) and not self.evidence:
            raise ValueError(
                "scale bounds were given without `evidence`; cite the paper "
                "table or repository example the numbers come from"
            )
        return self


class Maturity(BaseModel):
    maintained: bool
    last_release: str | None = None
    implementation_quality: str


class Governance(BaseModel):
    acceptance_evidence: list[str] = Field(default_factory=list)
    known_deployments: list[str] = Field(default_factory=list)


class Links(BaseModel):
    paper: str | None = None
    code: str | None = None
    docs: str | None = None


class Method(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    family: str

    # hard-filter fields
    domains: list[str]
    data_types: list[str]
    variable_types: list[str]
    formal_dp: bool
    dp_mechanism: str | None = None
    compute: str
    license: str

    # scored fields
    purposes: list[str]
    preserves: list[str]
    scale: Scale
    expertise: str
    maturity: Maturity
    governance: Governance = Field(default_factory=Governance)

    # narrative fields
    caveats: list[str] = Field(min_length=1)
    evaluation: list[str] = Field(default_factory=list)
    links: Links = Field(default_factory=Links)
    related_datasets: list[str] = Field(default_factory=list)

    is_framework: bool = False

    # True for simulators that never ingest real records (Synthea, rule-based
    # models). They cannot leak what they never saw, so a formal DP
    # requirement does not apply to them.
    requires_no_source_data: bool = False

    @model_validator(mode="after")
    def _dp_needs_mechanism(self) -> "Method":
        if self.formal_dp and not self.dp_mechanism:
            raise ValueError("formal_dp is true but dp_mechanism is missing")
        return self


class Dataset(BaseModel):
    id: str
    name: str
    domain: str
    data_type: str
    size: str
    generated_by: str | None = None
    access_conditions: str
    license: str
    realism_caveats: list[str] = Field(min_length=1)
    links: Links = Field(default_factory=Links)
