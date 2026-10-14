"""Pydantic models for catalog entries."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

PROVENANCE_SOURCES = ("paper", "code", "docs")


class Provenance(BaseModel):
    """Who checked this entry against what, and when.

    Rendered as "Verified <date> by <name>" by report.provenance_line. An
    entry without one renders "Not yet verified" - the honest state for a
    fresh contribution.
    """

    verified_on: date
    verified_by: str = Field(min_length=1)
    sources_checked: list[str] = Field(min_length=1)
    fields_checked: list[str] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> "Provenance":
        bad = sorted(set(self.sources_checked) - set(PROVENANCE_SOURCES))
        if bad:
            raise ValueError(
                f"sources_checked contains {bad}; allowed: {list(PROVENANCE_SOURCES)}")
        if self.verified_on > date.today():
            raise ValueError("verified_on is in the future")
        return self


def _check_provenance(entry: "Method | Dataset") -> None:
    p = entry.provenance
    if p is None:
        return
    for source in p.sources_checked:
        if getattr(entry.links, source) is None:
            raise ValueError(
                f"provenance says {source} was checked but the entry has "
                f"no {source} link")
    allowed = set(type(entry).model_fields)
    unknown = sorted(set(p.fields_checked) - allowed)
    if unknown:
        raise ValueError(f"fields_checked names unknown fields {unknown}")


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


class OutputPreview(BaseModel):
    """An illustration of the SHAPE a method emits.

    Never real generated output. The disclaimer saying so is rendered by
    report.render_preview, not stored here, so no entry can omit it.
    """

    format: str
    note: str = Field(min_length=1)
    preview: str = Field(min_length=1)


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
    output_preview: OutputPreview | None = None
    provenance: Provenance | None = None

    # Practical tags, read off the repository rather than estimated.
    language: str | None = None
    last_updated: int | None = None

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

    @model_validator(mode="after")
    def _provenance_matches_entry(self) -> "Method":
        _check_provenance(self)
        return self

    def governance_checked(self) -> bool:
        """True only when someone recorded that they looked for governance
        evidence. Distinguishes "none found" from "nobody looked"."""
        return (self.provenance is not None
                and "governance" in self.provenance.fields_checked)


class Dataset(BaseModel):
    id: str
    name: str
    domains: list[str]
    data_types: list[str]
    purposes: list[str] = Field(default_factory=list)
    n_records: str
    formal_dp: bool = False
    dp_mechanism: str | None = None
    generated_by: str | None = None
    access_conditions: str
    license: str
    realism_caveats: list[str] = Field(min_length=1)
    links: Links = Field(default_factory=Links)
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def _provenance_matches_entry(self) -> "Dataset":
        _check_provenance(self)
        return self

    @model_validator(mode="after")
    def _dp_needs_mechanism(self) -> "Dataset":
        if self.formal_dp and not self.dp_mechanism:
            raise ValueError("formal_dp is true but dp_mechanism is missing")
        return self
