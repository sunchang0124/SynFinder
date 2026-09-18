# SynFinder v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python package and Streamlit app that takes a researcher's intake and returns a ranked shortlist of synthetic data generation methods with rationales, caveats, and an exportable report.

**Architecture:** The catalog is data (one YAML per method), the engine is code. Ranking is a hard-filter pass that records why each method was eliminated, followed by a weighted mean over scored axes. Explanations are assembled from the score breakdown and catalog text; an LLM may rewrite them into prose but can never add a claim.

**Tech Stack:** Python 3.11+, pydantic v2, PyYAML, pytest, Streamlit, anthropic SDK (optional at runtime).

**Spec:** `docs/superpowers/specs/2026-09-18-synfinder-design.md`

## Global Constraints

- Python 3.11 or newer; pydantic v2 (not v1 syntax).
- **The app must work with no `ANTHROPIC_API_KEY` set.** Every feature — ranking, rationales, comparison table, report — is produced without any network call. The LLM is enrichment only.
- No controlled-vocabulary value may appear in a method YAML unless it is listed in `catalog/taxonomy.yaml`. The loader raises on drift.
- A skipped optional intake answer removes its axis from both numerator and denominator of the weighted mean. It never scores 0.
- Catalog entries are drafted in batches of ~8 and reviewed by Chang before merge. No entry is committed unreviewed.
- v1 catalog is `domains: [biomedical]` or `[general]` only. No SSH entries.

---

### Task 1: Project scaffolding, taxonomy, and schema

**Files:**
- Create: `pyproject.toml`
- Create: `catalog/taxonomy.yaml`
- Create: `src/synfinder/__init__.py`
- Create: `src/synfinder/schema.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Taxonomy`, `Method`, `Dataset`, `Scale`, `Maturity`, `Governance`, `Links` pydantic models. `Method` fields used by every later task: `id: str`, `name: str`, `family: str`, `domains: list[str]`, `data_types: list[str]`, `variable_types: list[str]`, `formal_dp: bool`, `dp_mechanism: str | None`, `compute: str`, `license: str`, `purposes: list[str]`, `preserves: list[str]`, `scale: Scale`, `expertise: str`, `maturity: Maturity`, `governance: Governance`, `caveats: list[str]`, `evaluation: list[str]`, `links: Links`, `related_datasets: list[str]`, `is_framework: bool`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "synfinder"
version = "0.1.0"
description = "Find the right synthetic data generation method for your research"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.6", "pyyaml>=6.0"]

[project.optional-dependencies]
app = ["streamlit>=1.33"]
llm = ["anthropic>=0.40"]
dev = ["pytest>=8.0"]

[project.scripts]
synfinder = "synfinder.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Write `catalog/taxonomy.yaml`**

```yaml
domains: [biomedical, ssh, general]
data_types:
  - tabular_cross_sectional
  - tabular_longitudinal
  - coded_event_sequences
  - time_series
  - survival
  - survey_instrument
  - text
  - images
  - graph
variable_types: [continuous, categorical, ordinal, count, datetime, free_text]
compute: [cpu_fine, gpu_recommended, gpu_required]
expertise: [low, medium, high]
implementation_quality: [reference_only, research_code, production_ready]
purposes:
  - open_release
  - pipeline_testing
  - ml_augmentation
  - statistical_replication
  - causal_inference
  - education
  - benchmarking
  - imbalance_correction
preserves:
  - marginals
  - joint_correlations
  - temporal_dynamics
  - causal_structure
  - rare_events
families:
  - gan
  - vae
  - diffusion
  - probabilistic_graphical
  - marginal_based
  - copula
  - sequential_tree
  - llm
  - agent_simulation
  - rule_based
  - resampling
  - toolkit
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_schema.py
import pytest
from pydantic import ValidationError
from synfinder.schema import Method, Scale, Maturity, Governance, Links

def minimal_method(**over):
    base = dict(
        id="ctgan", name="CTGAN", family="gan",
        domains=["general"], data_types=["tabular_cross_sectional"],
        variable_types=["continuous", "categorical"],
        formal_dp=False, dp_mechanism=None,
        compute="gpu_recommended", license="MIT",
        purposes=["ml_augmentation"], preserves=["joint_correlations"],
        scale=Scale(min_rows=1000, max_rows=1_000_000, max_cols=200),
        expertise="medium",
        maturity=Maturity(maintained=True, last_release="2024-06",
                          implementation_quality="production_ready"),
        governance=Governance(acceptance_evidence=[], known_deployments=[]),
        caveats=["Struggles with high-cardinality categorical columns."],
        evaluation=["SDMetrics column-shape and column-pair-trend scores"],
        links=Links(paper="10.48550/arXiv.1907.00503",
                    code="https://github.com/sdv-dev/CTGAN", docs=None),
        related_datasets=[], is_framework=False,
    )
    base.update(over)
    return Method(**base)

def test_method_accepts_a_complete_entry():
    m = minimal_method()
    assert m.id == "ctgan"
    assert m.is_framework is False

def test_method_requires_caveats():
    with pytest.raises(ValidationError):
        minimal_method(caveats=[])

def test_formal_dp_requires_a_mechanism():
    with pytest.raises(ValidationError):
        minimal_method(formal_dp=True, dp_mechanism=None)
```

The `caveats` rule is deliberate: an entry with no honest failure mode has
not really been reviewed.

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.schema'`

- [ ] **Step 5: Write `src/synfinder/schema.py`**

```python
"""Pydantic models for catalog entries."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Scale(BaseModel):
    min_rows: int | None = None
    max_rows: int | None = None
    max_cols: int | None = None


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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_schema.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml catalog/taxonomy.yaml src/synfinder tests/test_schema.py
git commit -m "feat: catalog schema and taxonomy"
```

---

### Task 2: Catalog loader with taxonomy validation

**Files:**
- Create: `src/synfinder/catalog.py`
- Create: `catalog/methods/.gitkeep`, `catalog/datasets/.gitkeep`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `Method`, `Dataset` from `synfinder.schema`.
- Produces: `class CatalogError(Exception)`; `load_taxonomy(path: Path) -> dict[str, list[str]]`; `load_catalog(root: Path) -> Catalog`; `class Catalog` with attributes `methods: list[Method]`, `datasets: list[Dataset]`, `taxonomy: dict[str, list[str]]` and method `generation_methods() -> list[Method]` (all methods where `is_framework is False`) and `frameworks() -> list[Method]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_catalog.py
from pathlib import Path
import pytest
import yaml
from synfinder.catalog import load_catalog, CatalogError

TAXONOMY = {
    "domains": ["biomedical", "general"],
    "data_types": ["tabular_cross_sectional"],
    "variable_types": ["continuous", "categorical"],
    "compute": ["cpu_fine", "gpu_recommended", "gpu_required"],
    "expertise": ["low", "medium", "high"],
    "implementation_quality": ["research_code", "production_ready"],
    "purposes": ["ml_augmentation", "open_release"],
    "preserves": ["marginals", "joint_correlations"],
    "families": ["gan", "toolkit"],
}

ENTRY = {
    "id": "ctgan", "name": "CTGAN", "family": "gan",
    "domains": ["general"], "data_types": ["tabular_cross_sectional"],
    "variable_types": ["continuous", "categorical"],
    "formal_dp": False, "compute": "gpu_recommended", "license": "MIT",
    "purposes": ["ml_augmentation"], "preserves": ["joint_correlations"],
    "scale": {"min_rows": 1000, "max_rows": 1000000, "max_cols": 200},
    "expertise": "medium",
    "maturity": {"maintained": True, "last_release": "2024-06",
                 "implementation_quality": "production_ready"},
    "caveats": ["Struggles with high-cardinality categoricals."],
}

def build(tmp_path: Path, entry: dict) -> Path:
    (tmp_path / "methods").mkdir()
    (tmp_path / "datasets").mkdir()
    (tmp_path / "taxonomy.yaml").write_text(yaml.safe_dump(TAXONOMY))
    (tmp_path / "methods" / f"{entry['id']}.yaml").write_text(yaml.safe_dump(entry))
    return tmp_path

def test_loads_a_valid_method(tmp_path):
    cat = load_catalog(build(tmp_path, ENTRY))
    assert [m.id for m in cat.methods] == ["ctgan"]

def test_rejects_a_term_missing_from_the_taxonomy(tmp_path):
    bad = dict(ENTRY, purposes=["time_travel"])
    with pytest.raises(CatalogError) as exc:
        load_catalog(build(tmp_path, bad))
    assert "time_travel" in str(exc.value)
    assert "purposes" in str(exc.value)

def test_frameworks_are_separated_from_generation_methods(tmp_path):
    root = build(tmp_path, ENTRY)
    sdv = dict(ENTRY, id="sdv", name="SDV", family="toolkit", is_framework=True)
    (root / "methods" / "sdv.yaml").write_text(yaml.safe_dump(sdv))
    cat = load_catalog(root)
    assert [m.id for m in cat.generation_methods()] == ["ctgan"]
    assert [m.id for m in cat.frameworks()] == ["sdv"]

def test_duplicate_ids_are_rejected(tmp_path):
    root = build(tmp_path, ENTRY)
    (root / "methods" / "ctgan_copy.yaml").write_text(yaml.safe_dump(ENTRY))
    with pytest.raises(CatalogError) as exc:
        load_catalog(root)
    assert "ctgan" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.catalog'`

- [ ] **Step 3: Write `src/synfinder/catalog.py`**

```python
"""Load and validate the YAML catalog."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from .schema import Dataset, Method

# catalog field -> taxonomy key it must draw from
CONTROLLED: dict[str, str] = {
    "domains": "domains",
    "data_types": "data_types",
    "variable_types": "variable_types",
    "compute": "compute",
    "expertise": "expertise",
    "purposes": "purposes",
    "preserves": "preserves",
    "family": "families",
}


class CatalogError(Exception):
    """A catalog file is malformed or uses a term outside the taxonomy."""


@dataclass
class Catalog:
    methods: list[Method] = field(default_factory=list)
    datasets: list[Dataset] = field(default_factory=list)
    taxonomy: dict[str, list[str]] = field(default_factory=dict)

    def generation_methods(self) -> list[Method]:
        return [m for m in self.methods if not m.is_framework]

    def frameworks(self) -> list[Method]:
        return [m for m in self.methods if m.is_framework]

    def by_id(self, method_id: str) -> Method | None:
        return next((m for m in self.methods if m.id == method_id), None)


def load_taxonomy(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        raise CatalogError(f"taxonomy file not found: {path}")
    return yaml.safe_load(path.read_text())


def _check_terms(entry: dict, taxonomy: dict[str, list[str]], source: Path) -> None:
    for field_name, tax_key in CONTROLLED.items():
        if field_name not in entry:
            continue
        allowed = set(taxonomy.get(tax_key, []))
        raw = entry[field_name]
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            if value not in allowed:
                raise CatalogError(
                    f"{source.name}: '{value}' is not a permitted value for "
                    f"'{field_name}'; taxonomy key '{tax_key}' allows "
                    f"{sorted(allowed)}"
                )
    quality = entry.get("maturity", {}).get("implementation_quality")
    if quality is not None and quality not in set(taxonomy.get("implementation_quality", [])):
        raise CatalogError(
            f"{source.name}: '{quality}' is not a permitted implementation_quality"
        )


def load_catalog(root: Path) -> Catalog:
    root = Path(root)
    taxonomy = load_taxonomy(root / "taxonomy.yaml")
    catalog = Catalog(taxonomy=taxonomy)

    seen: dict[str, Path] = {}
    for path in sorted((root / "methods").glob("*.yaml")):
        entry = yaml.safe_load(path.read_text())
        _check_terms(entry, taxonomy, path)
        try:
            method = Method(**entry)
        except ValidationError as exc:
            raise CatalogError(f"{path.name}: {exc}") from exc
        if method.id in seen:
            raise CatalogError(
                f"duplicate method id '{method.id}' in {path.name} "
                f"and {seen[method.id].name}"
            )
        seen[method.id] = path
        catalog.methods.append(method)

    datasets_dir = root / "datasets"
    if datasets_dir.exists():
        for path in sorted(datasets_dir.glob("*.yaml")):
            entry = yaml.safe_load(path.read_text())
            try:
                catalog.datasets.append(Dataset(**entry))
            except ValidationError as exc:
                raise CatalogError(f"{path.name}: {exc}") from exc

    return catalog
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_catalog.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/synfinder/catalog.py tests/test_catalog.py catalog/methods catalog/datasets
git commit -m "feat: catalog loader with taxonomy validation"
```

---

### Task 3: Intake model

**Files:**
- Create: `src/synfinder/intake.py`
- Test: `tests/test_intake.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `class Intake` with required fields `domain: str`, `data_type: str`, `purpose: str`, `privacy: str` (one of `none`, `deidentified_ok`, `formal_dp_required`) and optional fields `compute: str | None`, `expertise: str | None`, `expected_rows: int | None`, `variable_types: list[str]` (default `[]`), `preserves: list[str]` (default `[]`), `needs_governance_evidence: bool | None`, `require_open_license: bool | None`. Also `Intake.answered(axis: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intake.py
import pytest
from pydantic import ValidationError
from synfinder.intake import Intake

def test_core_four_are_required():
    with pytest.raises(ValidationError):
        Intake(domain="biomedical", data_type="tabular_cross_sectional")

def test_optional_axes_default_to_unanswered():
    i = Intake(domain="biomedical", data_type="tabular_cross_sectional",
               purpose="open_release", privacy="formal_dp_required")
    assert i.expertise is None
    assert i.preserves == []
    assert i.answered("expertise") is False
    assert i.answered("preserves") is False
    assert i.answered("purpose") is True

def test_answered_is_true_once_an_optional_axis_is_filled():
    i = Intake(domain="biomedical", data_type="tabular_cross_sectional",
               purpose="open_release", privacy="none",
               preserves=["temporal_dynamics"], expertise="low")
    assert i.answered("preserves") is True
    assert i.answered("expertise") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_intake.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.intake'`

- [ ] **Step 3: Write `src/synfinder/intake.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_intake.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/synfinder/intake.py tests/test_intake.py
git commit -m "feat: intake model"
```

---

### Task 4: Hard filters

**Files:**
- Create: `src/synfinder/ranking.py`
- Test: `tests/test_hard_filters.py`
- Test helper: `tests/factories.py`

**Interfaces:**
- Consumes: `Method` (Task 1), `Intake` (Task 3).
- Produces: `@dataclass Exclusion` with fields `method_id: str`, `method_name: str`, `reason: str`; `hard_filter(methods: list[Method], intake: Intake) -> tuple[list[Method], list[Exclusion]]`.

- [ ] **Step 1: Write `tests/factories.py`**

```python
"""Shared test factory so every ranking test builds methods the same way."""
from synfinder.schema import Method, Scale, Maturity, Governance, Links

def make_method(**over) -> Method:
    base = dict(
        id="m", name="M", family="gan",
        domains=["general"], data_types=["tabular_cross_sectional"],
        variable_types=["continuous", "categorical"],
        formal_dp=False, dp_mechanism=None,
        compute="cpu_fine", license="MIT",
        purposes=["ml_augmentation"], preserves=["marginals"],
        scale=Scale(min_rows=None, max_rows=None, max_cols=None),
        expertise="medium",
        maturity=Maturity(maintained=True, last_release="2025-01",
                          implementation_quality="production_ready"),
        governance=Governance(),
        caveats=["A caveat."], evaluation=[], links=Links(),
        related_datasets=[], is_framework=False,
    )
    base.update(over)
    return Method(**base)
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_hard_filters.py
from synfinder.intake import Intake
from synfinder.ranking import hard_filter
from tests.factories import make_method

def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")
    base.update(over)
    return Intake(**base)

def test_general_domain_methods_survive_a_biomedical_intake():
    kept, dropped = hard_filter([make_method(domains=["general"])], intake())
    assert [m.id for m in kept] == ["m"]
    assert dropped == []

def test_wrong_domain_is_excluded_with_a_reason():
    kept, dropped = hard_filter([make_method(domains=["ssh"])], intake())
    assert kept == []
    assert "biomedical" in dropped[0].reason

def test_unsupported_data_type_is_excluded():
    kept, dropped = hard_filter(
        [make_method(data_types=["images"])], intake())
    assert kept == []
    assert "tabular_cross_sectional" in dropped[0].reason

def test_no_formal_dp_when_dp_is_required():
    kept, dropped = hard_filter(
        [make_method(formal_dp=False)], intake(privacy="formal_dp_required"))
    assert kept == []
    assert "differential privacy" in dropped[0].reason

def test_gpu_required_when_user_has_cpu_only():
    kept, dropped = hard_filter(
        [make_method(compute="gpu_required")], intake(compute="cpu_fine"))
    assert kept == []
    assert "GPU" in dropped[0].reason

def test_free_text_requirement_the_method_cannot_meet():
    kept, dropped = hard_filter(
        [make_method(variable_types=["continuous"])],
        intake(variable_types=["continuous", "free_text"]))
    assert kept == []
    assert "free text" in dropped[0].reason

def test_closed_license_when_open_is_required():
    kept, dropped = hard_filter(
        [make_method(license="proprietary")],
        intake(require_open_license=True))
    assert kept == []
    assert "proprietary" in dropped[0].reason

def test_unanswered_compute_does_not_exclude_a_gpu_method():
    kept, _ = hard_filter([make_method(compute="gpu_required")], intake())
    assert [m.id for m in kept] == ["m"]

def test_frameworks_are_never_ranked():
    kept, dropped = hard_filter([make_method(is_framework=True)], intake())
    assert kept == []
    assert "framework" in dropped[0].reason
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_hard_filters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.ranking'`

- [ ] **Step 4: Write the hard-filter half of `src/synfinder/ranking.py`**

```python
"""Hard filters and weighted scoring."""
from __future__ import annotations

from dataclasses import dataclass

from .intake import Intake
from .schema import Method

OPEN_LICENSES = {
    "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0",
    "GPL-3.0", "GPL-2.0", "LGPL-3.0", "MPL-2.0", "CC-BY-4.0", "CC0-1.0",
}


@dataclass
class Exclusion:
    method_id: str
    method_name: str
    reason: str


def _exclusion_reason(method: Method, intake: Intake) -> str | None:
    """The first reason this method cannot serve this intake, or None."""
    if method.is_framework:
        return "is a framework or toolkit, not a generation method in itself"

    if intake.domain not in method.domains and "general" not in method.domains:
        return f"is not established for the {intake.domain} domain"

    if intake.data_type not in method.data_types:
        return f"cannot handle {intake.data_type} data"

    if intake.privacy == "formal_dp_required" and not method.formal_dp:
        return "provides no formal differential privacy guarantee"

    if intake.compute == "cpu_fine" and method.compute == "gpu_required":
        return "requires a GPU, which you said is not available"

    missing = set(intake.variable_types) - set(method.variable_types)
    if "free_text" in missing:
        return "cannot generate free text fields"
    if missing:
        return f"cannot generate {', '.join(sorted(missing))} variables"

    if intake.require_open_license and method.license not in OPEN_LICENSES:
        return f"license {method.license} is not an open licence"

    return None


def hard_filter(
    methods: list[Method], intake: Intake
) -> tuple[list[Method], list[Exclusion]]:
    kept: list[Method] = []
    dropped: list[Exclusion] = []
    for method in methods:
        reason = _exclusion_reason(method, intake)
        if reason is None:
            kept.append(method)
        else:
            dropped.append(Exclusion(method.id, method.name, reason))
    return kept, dropped
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_hard_filters.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add src/synfinder/ranking.py tests/test_hard_filters.py tests/factories.py
git commit -m "feat: hard filters with recorded exclusion reasons"
```

---

### Task 5: Weighted scoring and ranking

**Files:**
- Modify: `src/synfinder/ranking.py`
- Create: `catalog/weights.yaml`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `hard_filter`, `Exclusion` (Task 4).
- Produces: `@dataclass AxisScore(axis: str, score: float, weight: float, note: str)`; `@dataclass Candidate(method: Method, fit: float, axes: list[AxisScore])`; `@dataclass Ranking(shortlist: list[Candidate], excluded: list[Exclusion])`; `DEFAULT_WEIGHTS: dict[str, float]`; `load_weights(path) -> dict[str, float]`; `score_method(method, intake, weights) -> Candidate`; `rank(methods, intake, weights=None, top_n=5) -> Ranking`.

- [ ] **Step 1: Write `catalog/weights.yaml`**

```yaml
# Relative importance of each scored axis. Tuned against the golden
# scenarios in tests/test_golden_scenarios.py — change these and run
# that file.
purpose: 3.0
preserves: 2.5
expertise: 1.5
maturity: 1.5
scale: 1.0
governance: 1.0
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_scoring.py
import pytest
from synfinder.intake import Intake
from synfinder.ranking import score_method, rank, DEFAULT_WEIGHTS
from synfinder.schema import Scale, Governance
from tests.factories import make_method

def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")
    base.update(over)
    return Intake(**base)

def axis(candidate, name):
    return next(a for a in candidate.axes if a.axis == name)

def test_purpose_match_scores_one():
    c = score_method(make_method(purposes=["ml_augmentation"]),
                     intake(), DEFAULT_WEIGHTS)
    assert axis(c, "purpose").score == 1.0

def test_purpose_mismatch_scores_zero_but_does_not_eliminate():
    c = score_method(make_method(purposes=["education"]),
                     intake(), DEFAULT_WEIGHTS)
    assert axis(c, "purpose").score == 0.0
    assert 0.0 <= c.fit <= 1.0

def test_preserves_is_the_fraction_of_needs_met():
    m = make_method(preserves=["marginals", "joint_correlations"])
    c = score_method(m, intake(preserves=["marginals", "temporal_dynamics"]),
                     DEFAULT_WEIGHTS)
    assert axis(c, "preserves").score == 0.5

def test_unanswered_axis_is_absent_not_zero():
    c = score_method(make_method(), intake(), DEFAULT_WEIGHTS)
    assert all(a.axis != "preserves" for a in c.axes)
    assert all(a.axis != "expertise" for a in c.axes)

def test_unanswered_axis_does_not_drag_the_fit_down():
    """A perfect method scores 1.0 even when most questions were skipped."""
    m = make_method(purposes=["ml_augmentation"])
    c = score_method(m, intake(), DEFAULT_WEIGHTS)
    assert c.fit == pytest.approx(1.0)

def test_method_needing_more_expertise_than_the_user_has_is_penalised():
    low = score_method(make_method(expertise="high"),
                       intake(expertise="low"), DEFAULT_WEIGHTS)
    ok = score_method(make_method(expertise="low"),
                      intake(expertise="low"), DEFAULT_WEIGHTS)
    assert axis(low, "expertise").score < axis(ok, "expertise").score

def test_scale_beyond_the_method_maximum_is_penalised():
    m = make_method(scale=Scale(min_rows=None, max_rows=10_000, max_cols=None))
    c = score_method(m, intake(expected_rows=1_000_000), DEFAULT_WEIGHTS)
    assert axis(c, "scale").score < 0.5

def test_governance_evidence_is_rewarded_when_asked_for():
    with_ev = make_method(
        governance=Governance(acceptance_evidence=["Approved by an MREC in 2024"]))
    without = make_method(governance=Governance())
    i = intake(needs_governance_evidence=True)
    assert (axis(score_method(with_ev, i, DEFAULT_WEIGHTS), "governance").score
            > axis(score_method(without, i, DEFAULT_WEIGHTS), "governance").score)

def test_rank_returns_best_first_and_respects_top_n():
    good = make_method(id="good", purposes=["ml_augmentation"])
    poor = make_method(id="poor", purposes=["education"])
    result = rank([poor, good], intake(), top_n=1)
    assert [c.method.id for c in result.shortlist] == ["good"]

def test_rank_reports_exclusions():
    result = rank([make_method(id="img", data_types=["images"])], intake())
    assert result.shortlist == []
    assert result.excluded[0].method_id == "img"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: FAIL — `ImportError: cannot import name 'score_method'`

- [ ] **Step 4: Append the scoring half to `src/synfinder/ranking.py`**

Hoist the two new imports (`from pathlib import Path`, `import yaml`) up to
the import block at the top of the file rather than leaving them mid-module.

```python
# --- scoring -------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "purpose": 3.0,
    "preserves": 2.5,
    "expertise": 1.5,
    "maturity": 1.5,
    "scale": 1.0,
    "governance": 1.0,
}

EXPERTISE_RANK = {"low": 0, "medium": 1, "high": 2}
QUALITY_SCORE = {
    "reference_only": 0.3,
    "research_code": 0.6,
    "production_ready": 1.0,
}


@dataclass
class AxisScore:
    axis: str
    score: float
    weight: float
    note: str


@dataclass
class Candidate:
    method: Method
    fit: float
    axes: list[AxisScore]

    def axis(self, name: str) -> AxisScore | None:
        return next((a for a in self.axes if a.axis == name), None)


@dataclass
class Ranking:
    shortlist: list[Candidate]
    excluded: list[Exclusion]


def load_weights(path: Path) -> dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(yaml.safe_load(Path(path).read_text()) or {})
    return weights


def _purpose_axis(method: Method, intake: Intake) -> AxisScore:
    hit = intake.purpose in method.purposes
    note = (
        f"supports your purpose ({intake.purpose.replace('_', ' ')})"
        if hit
        else f"is not typically used for {intake.purpose.replace('_', ' ')}"
    )
    return AxisScore("purpose", 1.0 if hit else 0.0, 0.0, note)


def _preserves_axis(method: Method, intake: Intake) -> AxisScore:
    wanted = set(intake.preserves)
    met = wanted & set(method.preserves)
    score = len(met) / len(wanted)
    if score == 1.0:
        note = "preserves everything you asked for"
    elif met:
        note = (
            f"preserves {', '.join(sorted(m.replace('_', ' ') for m in met))} "
            f"but not {', '.join(sorted(w.replace('_', ' ') for w in wanted - met))}"
        )
    else:
        note = (
            "preserves none of "
            f"{', '.join(sorted(w.replace('_', ' ') for w in wanted))}"
        )
    return AxisScore("preserves", score, 0.0, note)


def _expertise_axis(method: Method, intake: Intake) -> AxisScore:
    gap = EXPERTISE_RANK[method.expertise] - EXPERTISE_RANK[intake.expertise]
    score = 1.0 if gap <= 0 else max(0.0, 1.0 - 0.5 * gap)
    note = (
        "sits within your stated experience level"
        if gap <= 0
        else f"expects {method.expertise} familiarity with synthetic data methods"
    )
    return AxisScore("expertise", score, 0.0, note)


def _scale_axis(method: Method, intake: Intake) -> AxisScore:
    rows = intake.expected_rows
    max_rows, min_rows = method.scale.max_rows, method.scale.min_rows
    if max_rows is not None and rows > max_rows:
        over = rows / max_rows
        score = 0.4 if over <= 2 else 0.1
        note = f"is usually run on at most ~{max_rows:,} rows"
    elif min_rows is not None and rows < min_rows:
        score = 0.4
        note = f"needs roughly {min_rows:,} rows to train well"
    else:
        score = 1.0
        note = f"handles {rows:,} rows comfortably"
    return AxisScore("scale", score, 0.0, note)


def _maturity_axis(method: Method) -> AxisScore:
    score = QUALITY_SCORE.get(method.maturity.implementation_quality, 0.5)
    if not method.maturity.maintained:
        score *= 0.5
    note = (
        f"implementation is {method.maturity.implementation_quality.replace('_', ' ')}"
        + ("" if method.maturity.maintained else " and no longer maintained")
    )
    return AxisScore("maturity", score, 0.0, note)


def _governance_axis(method: Method) -> AxisScore:
    evidence = method.governance.acceptance_evidence
    deployments = method.governance.known_deployments
    if evidence or deployments:
        score = 1.0
        note = "has a track record you can point a review board to"
    else:
        score = 0.2
        note = "has no documented governance or regulatory acceptance yet"
    return AxisScore("governance", score, 0.0, note)


def score_method(
    method: Method, intake: Intake, weights: dict[str, float] | None = None
) -> Candidate:
    weights = weights or DEFAULT_WEIGHTS
    axes: list[AxisScore] = [_purpose_axis(method, intake), _maturity_axis(method)]

    if intake.answered("preserves"):
        axes.append(_preserves_axis(method, intake))
    if intake.answered("expertise"):
        axes.append(_expertise_axis(method, intake))
    if intake.answered("expected_rows"):
        axes.append(_scale_axis(method, intake))
    if intake.needs_governance_evidence:
        axes.append(_governance_axis(method))

    for a in axes:
        a.weight = weights.get(a.axis, 1.0)

    total = sum(a.weight for a in axes)
    fit = sum(a.score * a.weight for a in axes) / total if total else 0.0
    return Candidate(method=method, fit=fit, axes=axes)


def rank(
    methods: list[Method],
    intake: Intake,
    weights: dict[str, float] | None = None,
    top_n: int = 5,
) -> Ranking:
    kept, excluded = hard_filter(methods, intake)
    candidates = [score_method(m, intake, weights) for m in kept]
    candidates.sort(
        key=lambda c: (
            c.fit,
            QUALITY_SCORE.get(c.method.maturity.implementation_quality, 0.0),
        ),
        reverse=True,
    )
    return Ranking(shortlist=candidates[:top_n], excluded=excluded)
```

Note the `_maturity_axis` is always scored — it has no intake question,
so it is never "unanswered".

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: 10 passed

- [ ] **Step 6: Run the whole suite**

Run: `python -m pytest -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add src/synfinder/ranking.py catalog/weights.yaml tests/test_scoring.py
git commit -m "feat: weighted scoring with skipped-axis handling"
```

---

### Task 6: Explanations assembled from the breakdown

**Files:**
- Create: `src/synfinder/explain.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Consumes: `Candidate`, `AxisScore` (Task 5).
- Produces: `@dataclass Explanation(headline: str, why_fits: list[str], weakness: str | None, caveats: list[str], evaluation: list[str])`; `explain(candidate: Candidate, top_k: int = 2) -> Explanation`; `as_text(explanation: Explanation) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_explain.py
from synfinder.explain import explain, as_text
from synfinder.intake import Intake
from synfinder.ranking import score_method, DEFAULT_WEIGHTS
from tests.factories import make_method

def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")
    base.update(over)
    return Intake(**base)

def test_why_fits_names_the_strongest_axes():
    c = score_method(make_method(purposes=["ml_augmentation"]),
                     intake(), DEFAULT_WEIGHTS)
    e = explain(c)
    assert any("ml augmentation" in reason for reason in e.why_fits)

def test_weakness_names_the_lowest_scoring_axis():
    # purpose must MATCH here, so that `preserves` is unambiguously the
    # weakest axis; if both scored 0.0 the tie-break would pick purpose.
    m = make_method(purposes=["ml_augmentation"], preserves=["marginals"])
    c = score_method(m, intake(preserves=["temporal_dynamics"]), DEFAULT_WEIGHTS)
    e = explain(c)
    assert e.weakness is not None
    assert "temporal dynamics" in e.weakness

def test_caveats_are_carried_verbatim():
    m = make_method(caveats=["Breaks on irregular visit spacing."])
    e = explain(score_method(m, intake(), DEFAULT_WEIGHTS))
    assert e.caveats == ["Breaks on irregular visit spacing."]

def test_no_weakness_when_everything_scores_full():
    m = make_method(purposes=["ml_augmentation"])
    e = explain(score_method(m, intake(), DEFAULT_WEIGHTS))
    assert e.weakness is None

def test_as_text_contains_every_section_present():
    m = make_method(purposes=["education"],
                    caveats=["A caveat."],
                    evaluation=["Run SDMetrics."])
    text = as_text(explain(score_method(m, intake(), DEFAULT_WEIGHTS)))
    assert "Watch out" in text
    assert "How to check" in text
    assert "Run SDMetrics." in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_explain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.explain'`

- [ ] **Step 3: Write `src/synfinder/explain.py`**

```python
"""Turn a score breakdown into prose, using only catalog text."""
from __future__ import annotations

from dataclasses import dataclass, field

from .ranking import Candidate

STRONG = 0.75
WEAK = 0.6


@dataclass
class Explanation:
    headline: str
    why_fits: list[str] = field(default_factory=list)
    weakness: str | None = None
    caveats: list[str] = field(default_factory=list)
    evaluation: list[str] = field(default_factory=list)


def explain(candidate: Candidate, top_k: int = 2) -> Explanation:
    method = candidate.method
    ranked = sorted(candidate.axes, key=lambda a: a.score * a.weight, reverse=True)

    why = [a.note for a in ranked if a.score >= STRONG][:top_k]

    losers = [a for a in candidate.axes if a.score < WEAK]
    losers.sort(key=lambda a: a.score * a.weight)
    weakness = losers[0].note if losers else None

    headline = f"{method.name} — {candidate.fit:.0%} fit"
    return Explanation(
        headline=headline,
        why_fits=why,
        weakness=weakness,
        caveats=list(method.caveats),
        evaluation=list(method.evaluation),
    )


def as_text(explanation: Explanation) -> str:
    parts = [explanation.headline]
    if explanation.why_fits:
        parts.append("Why it fits: " + "; ".join(explanation.why_fits) + ".")
    if explanation.weakness:
        parts.append(f"Where it is weaker: it {explanation.weakness}.")
    if explanation.caveats:
        parts.append("Watch out: " + " ".join(explanation.caveats))
    if explanation.evaluation:
        parts.append("How to check it worked: " + "; ".join(explanation.evaluation) + ".")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_explain.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/synfinder/explain.py tests/test_explain.py
git commit -m "feat: explanations assembled from the score breakdown"
```

---

### Task 7: Report export

**Files:**
- Create: `src/synfinder/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `Ranking` (Task 5), `explain`, `as_text` (Task 6), `Intake` (Task 3).
- Produces: `render_markdown(intake: Intake, ranking: Ranking, datasets: list[Dataset] | None = None) -> str`; `render_html(intake: Intake, ranking: Ranking, datasets: list[Dataset] | None = None) -> str`; `comparison_rows(ranking: Ranking) -> tuple[list[str], list[list[str]]]` returning `(header, rows)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from synfinder.intake import Intake
from synfinder.ranking import rank
from synfinder.report import render_markdown, render_html, comparison_rows
from tests.factories import make_method

def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")
    base.update(over)
    return Intake(**base)

def test_markdown_lists_the_shortlist_and_the_exclusions():
    methods = [make_method(id="good", name="Good", purposes=["ml_augmentation"]),
               make_method(id="img", name="Imgs", data_types=["images"])]
    md = render_markdown(intake(), rank(methods, intake()))
    assert "Good" in md
    assert "Imgs" in md
    assert "cannot handle tabular_cross_sectional data" in md

def test_markdown_records_the_intake_so_the_report_is_self_contained():
    md = render_markdown(intake(), rank([make_method()], intake()))
    assert "ml_augmentation" in md
    assert "biomedical" in md

def test_comparison_rows_has_one_row_per_shortlisted_method():
    methods = [make_method(id="a", name="A"), make_method(id="b", name="B")]
    header, rows = comparison_rows(rank(methods, intake()))
    assert header[0] == "Method"
    assert len(rows) == 2

def test_html_is_wrapped_in_a_document():
    html = render_html(intake(), rank([make_method()], intake()))
    assert html.lstrip().startswith("<!doctype html>")
    assert "</html>" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.report'`

- [ ] **Step 3: Write `src/synfinder/report.py`**

```python
"""Export a shortlist as markdown or standalone HTML."""
from __future__ import annotations

import html as html_mod
from datetime import date

from .explain import explain
from .intake import Intake
from .ranking import Ranking
from .schema import Dataset

COMPARISON_AXES = ["purpose", "preserves", "expertise", "scale", "maturity", "governance"]


def comparison_rows(ranking: Ranking) -> tuple[list[str], list[list[str]]]:
    header = ["Method", "Fit"] + [a.replace("_", " ").title() for a in COMPARISON_AXES]
    rows: list[list[str]] = []
    for c in ranking.shortlist:
        row = [c.method.name, f"{c.fit:.0%}"]
        for name in COMPARISON_AXES:
            a = c.axis(name)
            row.append("—" if a is None else f"{a.score:.2f}")
        rows.append(row)
    return header, rows


def _intake_lines(intake: Intake) -> list[str]:
    lines = [
        f"- Domain: {intake.domain}",
        f"- Data type: {intake.data_type}",
        f"- Purpose: {intake.purpose}",
        f"- Privacy requirement: {intake.privacy}",
    ]
    optional = {
        "Compute": intake.compute,
        "Expertise": intake.expertise,
        "Expected rows": intake.expected_rows,
        "Variable types": ", ".join(intake.variable_types) or None,
        "Must preserve": ", ".join(intake.preserves) or None,
        "Open licence required": intake.require_open_license,
        "Governance evidence needed": intake.needs_governance_evidence,
    }
    lines += [f"- {k}: {v}" for k, v in optional.items() if v is not None]
    return lines


def render_markdown(
    intake: Intake, ranking: Ranking, datasets: list[Dataset] | None = None
) -> str:
    out: list[str] = [
        "# Synthetic data method recommendation",
        "",
        f"Generated by SynFinder on {date.today().isoformat()}.",
        "",
        "## What you asked for",
        "",
        *_intake_lines(intake),
        "",
        "## Recommended methods",
        "",
    ]

    if not ranking.shortlist:
        out += ["No method in the catalog matches these requirements.", ""]

    for i, c in enumerate(ranking.shortlist, start=1):
        e = explain(c)
        out.append(f"### {i}. {c.method.name} — {c.fit:.0%} fit")
        out.append("")
        if e.why_fits:
            out.append("**Why it fits:** " + "; ".join(e.why_fits) + ".")
        if e.weakness:
            out.append(f"**Where it is weaker:** it {e.weakness}.")
        if e.caveats:
            out.append("**Watch out:** " + " ".join(e.caveats))
        if e.evaluation:
            out.append("**How to check it worked:** " + "; ".join(e.evaluation) + ".")
        links = c.method.links
        link_bits = [
            f"[paper]({links.paper})" if links.paper else "",
            f"[code]({links.code})" if links.code else "",
            f"[docs]({links.docs})" if links.docs else "",
        ]
        link_line = " · ".join(b for b in link_bits if b)
        if link_line:
            out.append(link_line)
        out.append("")

    if ranking.shortlist:
        header, rows = comparison_rows(ranking)
        out += ["## Side by side", "",
                "| " + " | ".join(header) + " |",
                "|" + "---|" * len(header)]
        out += ["| " + " | ".join(r) + " |" for r in rows]
        out.append("")

    if datasets:
        out += ["## Ready-made synthetic datasets", ""]
        for d in datasets:
            out.append(f"- **{d.name}** ({d.size}, {d.license}) — {d.access_conditions}")
        out.append("")

    if ranking.excluded:
        out += [
            "## Ruled out",
            "",
            f"{len(ranking.excluded)} method(s) were excluded before scoring:",
            "",
        ]
        out += [f"- **{e.method_name}** {e.reason}." for e in ranking.excluded]
        out.append("")

    return "\n".join(out)


def render_html(
    intake: Intake, ranking: Ranking, datasets: list[Dataset] | None = None
) -> str:
    body = html_mod.escape(render_markdown(intake, ranking, datasets))
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        "<title>Synthetic data method recommendation</title>"
        "<style>body{font:16px/1.6 system-ui,sans-serif;max-width:52rem;"
        "margin:2rem auto;padding:0 16px}pre{white-space:pre-wrap}</style>"
        f"</head><body><pre>{body}</pre></body></html>\n"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/synfinder/report.py tests/test_report.py
git commit -m "feat: markdown and HTML report export"
```

---

### Task 8: CLI

**Files:**
- Create: `src/synfinder/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main(argv: list[str] | None = None) -> int`; `default_catalog_root() -> Path` resolving to the repo's `catalog/` directory.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from synfinder.cli import main

def test_cli_prints_a_shortlist(capsys, monkeypatch):
    code = main([
        "--domain", "biomedical",
        "--data-type", "tabular_cross_sectional",
        "--purpose", "ml_augmentation",
        "--privacy", "none",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "Recommended methods" in out

def test_cli_writes_a_report_file(tmp_path):
    target = tmp_path / "report.md"
    code = main([
        "--domain", "biomedical",
        "--data-type", "tabular_cross_sectional",
        "--purpose", "ml_augmentation",
        "--privacy", "none",
        "--out", str(target),
    ])
    assert code == 0
    assert "Recommended methods" in target.read_text()

def test_cli_rejects_a_data_type_outside_the_taxonomy(capsys):
    code = main([
        "--domain", "biomedical",
        "--data-type", "holograms",
        "--purpose", "ml_augmentation",
        "--privacy", "none",
    ])
    assert code == 2
    assert "holograms" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.cli'`

- [ ] **Step 3: Write `src/synfinder/cli.py`**

```python
"""Command line entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import CatalogError, load_catalog
from .intake import Intake
from .ranking import load_weights, rank
from .report import render_html, render_markdown


def default_catalog_root() -> Path:
    return Path(__file__).resolve().parents[2] / "catalog"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="synfinder",
        description="Find a synthetic data generation method that fits your study.",
    )
    p.add_argument("--domain", required=True)
    p.add_argument("--data-type", required=True)
    p.add_argument("--purpose", required=True)
    p.add_argument("--privacy", required=True,
                   choices=["none", "deidentified_ok", "formal_dp_required"])
    p.add_argument("--compute", choices=["cpu_fine", "gpu_recommended", "gpu_required"])
    p.add_argument("--expertise", choices=["low", "medium", "high"])
    p.add_argument("--rows", type=int, dest="expected_rows")
    p.add_argument("--variable-types", nargs="*", default=[])
    p.add_argument("--preserves", nargs="*", default=[])
    p.add_argument("--open-license", action="store_true", dest="require_open_license")
    p.add_argument("--governance-evidence", action="store_true",
                   dest="needs_governance_evidence")
    p.add_argument("--catalog", type=Path, default=None)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--out", type=Path, default=None,
                   help="write the report here (.md or .html)")
    return p


def _validate_against_taxonomy(args, taxonomy: dict) -> list[str]:
    checks = [
        ("domain", args.domain, "domains"),
        ("data-type", args.data_type, "data_types"),
        ("purpose", args.purpose, "purposes"),
    ]
    errors = [
        f"'{value}' is not a known {flag}; choose from "
        f"{', '.join(taxonomy.get(key, []))}"
        for flag, value, key in checks
        if value not in taxonomy.get(key, [])
    ]
    for value in args.preserves:
        if value not in taxonomy.get("preserves", []):
            errors.append(f"'{value}' is not a known preserves value")
    for value in args.variable_types:
        if value not in taxonomy.get("variable_types", []):
            errors.append(f"'{value}' is not a known variable type")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = args.catalog or default_catalog_root()

    try:
        catalog = load_catalog(root)
    except CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 1

    errors = _validate_against_taxonomy(args, catalog.taxonomy)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 2

    intake = Intake(
        domain=args.domain, data_type=args.data_type, purpose=args.purpose,
        privacy=args.privacy, compute=args.compute, expertise=args.expertise,
        expected_rows=args.expected_rows, variable_types=args.variable_types,
        preserves=args.preserves,
        require_open_license=args.require_open_license or None,
        needs_governance_evidence=args.needs_governance_evidence or None,
    )

    weights_path = Path(root) / "weights.yaml"
    weights = load_weights(weights_path) if weights_path.exists() else None
    ranking = rank(catalog.generation_methods(), intake, weights, top_n=args.top)

    matching = [
        d for d in catalog.datasets
        if d.domain in (intake.domain, "general") and d.data_type == intake.data_type
    ]

    if args.out and args.out.suffix == ".html":
        args.out.write_text(render_html(intake, ranking, matching))
        print(f"wrote {args.out}")
        return 0

    markdown = render_markdown(intake, ranking, matching)
    if args.out:
        args.out.write_text(markdown)
        print(f"wrote {args.out}")
    else:
        print(markdown)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 3 passed

Note: these tests read the real `catalog/` directory. Until Task 10 adds
entries, the shortlist will be empty — the assertions only check the report
structure and the taxonomy guard, which hold either way.

- [ ] **Step 5: Commit**

```bash
git add src/synfinder/cli.py tests/test_cli.py
git commit -m "feat: command line interface"
```

---

### Task 9: Optional LLM narration

**REQUIRED READING:** load the `claude-api` skill before writing `llm.py` — it
carries the current model ids and SDK usage. Do not write the Anthropic call
from memory.

**Files:**
- Create: `src/synfinder/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `Explanation` (Task 6), `Method` (Task 1), `Intake` (Task 3).
- Produces: `available() -> bool`; `narrate(explanation: Explanation, method: Method, intake: Intake) -> str | None` returning `None` whenever the SDK or key is absent, or the call fails.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm.py
from synfinder import llm
from synfinder.explain import Explanation
from synfinder.intake import Intake
from tests.factories import make_method

EXPL = Explanation(headline="M — 90% fit", why_fits=["supports your purpose"],
                   weakness=None, caveats=["A caveat."], evaluation=[])
INTAKE = Intake(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")

def test_unavailable_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.available() is False

def test_narrate_returns_none_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.narrate(EXPL, make_method(), INTAKE) is None

def test_narrate_returns_none_when_the_call_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(llm, "_call", boom)
    assert llm.narrate(EXPL, make_method(), INTAKE) is None

def test_prompt_carries_only_catalog_facts():
    prompt = llm.build_prompt(EXPL, make_method(), INTAKE)
    assert "A caveat." in prompt
    assert "do not introduce" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synfinder.llm'`

- [ ] **Step 3: Write `src/synfinder/llm.py`**

Load the `claude-api` skill first and use the model id it gives for the
default. The structure:

```python
"""Optional LLM narration. Every function degrades to None."""
from __future__ import annotations

import os

from .explain import Explanation, as_text
from .intake import Intake
from .schema import Method

MODEL = "claude-opus-5"  # confirm against the claude-api skill before shipping

SYSTEM = (
    "You rewrite a structured recommendation into two or three fluent "
    "sentences for a health researcher. Use only the facts given to you. "
    "Do not introduce any method, claim, number or citation that is not in "
    "the input. Keep every caveat."
)


def available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def build_prompt(explanation: Explanation, method: Method, intake: Intake) -> str:
    return (
        f"Researcher's situation: {intake.domain} study, {intake.data_type} "
        f"data, purpose is {intake.purpose}, privacy requirement is "
        f"{intake.privacy}.\n\n"
        f"Recommended method: {method.name}.\n\n"
        f"Structured recommendation to rewrite:\n{as_text(explanation)}\n\n"
        "Rewrite this for the researcher. Do not introduce anything new."
    )


def _call(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def narrate(
    explanation: Explanation, method: Method, intake: Intake
) -> str | None:
    if not available():
        return None
    try:
        return _call(build_prompt(explanation, method, intake))
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_llm.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the whole suite with no API key**

Run: `env -u ANTHROPIC_API_KEY python -m pytest -v`
Expected: all tests pass — this is the constraint that the app works
without a key.

- [ ] **Step 6: Commit**

```bash
git add src/synfinder/llm.py tests/test_llm.py
git commit -m "feat: optional LLM narration that degrades to templates"
```

---

### Task 10: First catalog batch and golden scenarios

**Files:**
- Create: `catalog/methods/{ctgan,tvae,gaussian_copula,synthpop,metasyn,bayesian_network,dp_cgans,privbayes}.yaml`
- Create: `tests/test_golden_scenarios.py`
- Create: `tests/test_catalog_integrity.py`

**Interfaces:**
- Consumes: `load_catalog` (Task 2), `rank` (Task 5).
- Produces: eight reviewed catalog entries and the regression suite that guards the weights.

- [ ] **Step 1: Write the catalog integrity test**

```python
# tests/test_catalog_integrity.py
from synfinder.catalog import load_catalog
from synfinder.cli import default_catalog_root

def test_the_real_catalog_loads():
    catalog = load_catalog(default_catalog_root())
    assert catalog.methods, "catalog is empty"

def test_every_method_has_caveats_and_links():
    for m in load_catalog(default_catalog_root()).methods:
        assert m.caveats, f"{m.id} has no caveats"
        assert m.links.code or m.links.paper, f"{m.id} has no paper or code link"

def test_related_dataset_ids_resolve():
    catalog = load_catalog(default_catalog_root())
    known = {d.id for d in catalog.datasets}
    for m in catalog.methods:
        for ref in m.related_datasets:
            assert ref in known, f"{m.id} references unknown dataset {ref}"
```

- [ ] **Step 2: Draft the eight YAML entries**

One file per method, following this shape exactly (CTGAN shown; the other
seven follow the same fields with their own values):

```yaml
# catalog/methods/ctgan.yaml
id: ctgan
name: CTGAN
aliases: [Conditional Tabular GAN]
family: gan
domains: [general]
data_types: [tabular_cross_sectional]
variable_types: [continuous, categorical, ordinal, count]
formal_dp: false
compute: gpu_recommended
license: MIT
purposes: [ml_augmentation, pipeline_testing, benchmarking]
preserves: [marginals, joint_correlations]
scale:
  min_rows: 1000
  max_rows: 1000000
  max_cols: 200
expertise: medium
maturity:
  maintained: true
  last_release: "2024-06"
  implementation_quality: production_ready
governance:
  acceptance_evidence: []
  known_deployments: []
caveats:
  - High-cardinality categorical columns blow up the conditional vector and
    training becomes unstable.
  - Offers no formal privacy guarantee; memorisation of rare records has been
    demonstrated, so it should not be used for open release of sensitive data.
evaluation:
  - SDMetrics column shape and column pair trend scores
  - A nearest-neighbour distance ratio check for memorised records
links:
  paper: https://doi.org/10.48550/arXiv.1907.00503
  code: https://github.com/sdv-dev/CTGAN
related_datasets: []
```

Batch one: `ctgan`, `tvae`, `gaussian_copula`, `synthpop`, `metasyn`,
`bayesian_network`, `dp_cgans`, `privbayes`.

**STOP after drafting: Chang reviews all eight before the commit.** The
caveats and governance fields are the ones to read closely — those are the
claims the tool will repeat to strangers.

- [ ] **Step 3: Run the integrity test**

Run: `python -m pytest tests/test_catalog_integrity.py -v`
Expected: 3 passed

- [ ] **Step 4: Write the golden scenarios**

```python
# tests/test_golden_scenarios.py
"""Fixed intakes with known-correct outcomes.

These guard the weights: change catalog/weights.yaml and run this file.
"""
import pytest
from synfinder.catalog import load_catalog
from synfinder.cli import default_catalog_root
from synfinder.intake import Intake
from synfinder.ranking import load_weights, rank

@pytest.fixture(scope="module")
def catalog():
    return load_catalog(default_catalog_root())

@pytest.fixture(scope="module")
def weights():
    return load_weights(default_catalog_root() / "weights.yaml")

def shortlist_ids(catalog, weights, **intake_kwargs):
    intake = Intake(**intake_kwargs)
    result = rank(catalog.generation_methods(), intake, weights, top_n=3)
    return [c.method.id for c in result.shortlist], result

def test_dp_requirement_keeps_only_dp_methods(catalog, weights):
    ids, result = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="tabular_cross_sectional",
        purpose="open_release", privacy="formal_dp_required")
    assert "ctgan" not in ids
    assert any(i in ids for i in ("dp_cgans", "privbayes"))
    assert any("differential privacy" in e.reason for e in result.excluded)

def test_low_expertise_cpu_only_prefers_simple_methods(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="tabular_cross_sectional",
        purpose="pipeline_testing", privacy="none",
        compute="cpu_fine", expertise="low")
    assert ids, "expected at least one recommendation"
    assert any(i in ids for i in ("metasyn", "gaussian_copula", "synthpop"))

def test_causal_structure_need_surfaces_a_graphical_method(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="tabular_cross_sectional",
        purpose="causal_inference", privacy="none",
        preserves=["causal_structure"])
    assert "bayesian_network" in ids
```

- [ ] **Step 5: Run the golden scenarios**

Run: `python -m pytest tests/test_golden_scenarios.py -v`
Expected: 3 passed. **If one fails, the fix is usually a catalog field or a
weight, not the test** — the test states what a knowledgeable person would
recommend. Adjust `catalog/weights.yaml` and re-run.

- [ ] **Step 6: Run the whole suite**

Run: `python -m pytest -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add catalog/methods tests/test_golden_scenarios.py tests/test_catalog_integrity.py
git commit -m "feat: first catalog batch and golden scenario regression tests"
```

---

### Task 11: Streamlit app

**Files:**
- Create: `app/streamlit_app.py`
- Create: `README.md`
- Test: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `build_intake(answers: dict) -> Intake` (importable, so it can be tested without a browser) and the Streamlit page.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_smoke.py
import importlib.util
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"

def load_app():
    spec = importlib.util.spec_from_file_location("streamlit_app", APP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_build_intake_maps_answers_to_the_model():
    app = load_app()
    intake = app.build_intake({
        "domain": "biomedical",
        "data_type": "tabular_cross_sectional",
        "purpose": "open_release",
        "privacy": "formal_dp_required",
        "expertise": None,
        "preserves": [],
    })
    assert intake.privacy == "formal_dp_required"
    assert intake.expertise is None
    assert intake.answered("expertise") is False
```

The module must import without launching a server, so all Streamlit calls
live inside `main()` guarded by `if __name__ == "__main__"` — or behind
`st.runtime.exists()`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_smoke.py -v`
Expected: FAIL — file not found

- [ ] **Step 3: Write `app/streamlit_app.py`**

`build_intake` is module level and takes a plain dict, so the smoke test can
call it with no Streamlit runtime. Every Streamlit call lives inside `main()`.

```python
"""SynFinder — Streamlit front end."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synfinder import llm                                    # noqa: E402
from synfinder.catalog import load_catalog                   # noqa: E402
from synfinder.explain import as_text, explain               # noqa: E402
from synfinder.intake import Intake                          # noqa: E402
from synfinder.ranking import load_weights, rank             # noqa: E402
from synfinder.report import comparison_rows, render_html, render_markdown  # noqa: E402

UNSET = "not specified"


def build_intake(answers: dict) -> Intake:
    """Map raw form answers to an Intake, turning sentinels into None."""
    def clean(key):
        value = answers.get(key)
        return None if value in (UNSET, "", None) else value

    return Intake(
        domain=answers["domain"],
        data_type=answers["data_type"],
        purpose=answers["purpose"],
        privacy=answers["privacy"],
        compute=clean("compute"),
        expertise=clean("expertise"),
        expected_rows=clean("expected_rows"),
        variable_types=answers.get("variable_types") or [],
        preserves=answers.get("preserves") or [],
        require_open_license=clean("require_open_license"),
        needs_governance_evidence=clean("needs_governance_evidence"),
    )


def _pretty(value: str) -> str:
    return value.replace("_", " ")


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="SynFinder", page_icon="🧬", layout="wide")
    st.title("SynFinder")
    st.caption(
        "Answer four questions and get synthetic data generation methods that "
        "actually fit your study — with the caveats that will bite you."
    )

    catalog = load_catalog(ROOT / "catalog")
    tax = catalog.taxonomy
    weights = load_weights(ROOT / "catalog" / "weights.yaml")

    with st.form("intake"):
        st.subheader("The essentials")
        c1, c2 = st.columns(2)
        with c1:
            domain = st.selectbox("Research domain", tax["domains"],
                                  format_func=_pretty)
            purpose = st.selectbox("What is the synthetic data for?",
                                   tax["purposes"], format_func=_pretty)
        with c2:
            data_type = st.selectbox("What does your real data look like?",
                                     tax["data_types"], format_func=_pretty)
            privacy = st.selectbox(
                "Privacy requirement",
                ["none", "deidentified_ok", "formal_dp_required"],
                format_func=_pretty)

        with st.expander("Constraints and resources (optional)"):
            compute = st.selectbox("Compute available",
                                   [UNSET] + tax["compute"], format_func=_pretty)
            expertise = st.selectbox("Your experience with these methods",
                                     [UNSET] + tax["expertise"], format_func=_pretty)
            expected_rows = st.number_input(
                "Roughly how many records? (0 = not specified)",
                min_value=0, value=0, step=1000)
            variable_types = st.multiselect("Variable types you must generate",
                                            tax["variable_types"], format_func=_pretty)
            require_open_license = st.checkbox("Must have an open licence")

        with st.expander("Fidelity and evaluation (optional)"):
            preserves = st.multiselect(
                "What must the synthetic data preserve?",
                tax["preserves"], format_func=_pretty)

        with st.expander("Governance and acceptance (optional)"):
            needs_governance = st.checkbox(
                "I need evidence of ethics or regulatory acceptance")

        submitted = st.form_submit_button("Find methods", type="primary")

    if not submitted:
        return

    intake = build_intake({
        "domain": domain, "data_type": data_type, "purpose": purpose,
        "privacy": privacy, "compute": compute, "expertise": expertise,
        "expected_rows": expected_rows or None,
        "variable_types": variable_types, "preserves": preserves,
        "require_open_license": require_open_license or None,
        "needs_governance_evidence": needs_governance or None,
    })

    ranking = rank(catalog.generation_methods(), intake, weights, top_n=5)

    if not ranking.shortlist:
        st.error("No method in the catalog meets these requirements.")
    else:
        st.subheader("Recommended methods")

    for c in ranking.shortlist:
        e = explain(c)
        with st.container(border=True):
            left, right = st.columns([3, 1])
            left.markdown(f"### {c.method.name}")
            right.metric("Fit", f"{c.fit:.0%}")
            st.progress(c.fit)

            narrated = llm.narrate(e, c.method, intake) if llm.available() else None
            st.write(narrated or as_text(e).split("\n", 1)[-1])

            for caveat in e.caveats:
                st.warning(caveat, icon="⚠️")
            if e.evaluation:
                st.info("**How to check it worked:** " + "; ".join(e.evaluation))

            links = c.method.links
            bits = [f"[paper]({links.paper})" if links.paper else "",
                    f"[code]({links.code})" if links.code else "",
                    f"[docs]({links.docs})" if links.docs else ""]
            line = " · ".join(b for b in bits if b)
            if line:
                st.markdown(line)

    if ranking.shortlist:
        st.subheader("Side by side")
        header, rows = comparison_rows(ranking)
        st.dataframe([dict(zip(header, r)) for r in rows],
                     use_container_width=True, hide_index=True)

    matching = [d for d in catalog.datasets
                if d.domain in (intake.domain, "general")
                and d.data_type == intake.data_type]
    if matching:
        st.subheader("Ready-made synthetic datasets")
        for d in matching:
            st.markdown(f"- **{d.name}** ({d.size}, {d.license}) — {d.access_conditions}")

    if ranking.excluded:
        with st.expander(f"Why {len(ranking.excluded)} other method(s) were ruled out"):
            for x in ranking.excluded:
                st.markdown(f"- **{x.method_name}** {x.reason}.")

    st.subheader("Take it with you")
    d1, d2 = st.columns(2)
    d1.download_button("Download report (Markdown)",
                       render_markdown(intake, ranking, matching),
                       file_name="synfinder-report.md", mime="text/markdown")
    d2.download_button("Download report (HTML)",
                       render_html(intake, ranking, matching),
                       file_name="synfinder-report.html", mime="text/html")

    if not llm.available():
        st.caption(
            "Running without an ANTHROPIC_API_KEY — rationales are the "
            "catalog's own wording. Everything above works the same either way."
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the smoke test**

Run: `python -m pytest tests/test_app_smoke.py -v`
Expected: 1 passed

- [ ] **Step 5: Launch the app and look at it**

Run: `streamlit run app/streamlit_app.py`
Expected: the form renders; submitting the core four returns a shortlist
with rationales, a comparison table, and a working download button.

- [ ] **Step 6: Write `README.md`**

Cover: what the tool does, install (`pip install -e ".[app,dev]"`), the CLI
example, running the app, how to add a catalog entry (copy a YAML, fill it,
run `pytest tests/test_catalog_integrity.py`), and a plain statement that no
API key is required.

- [ ] **Step 7: Commit**

```bash
git add app/streamlit_app.py tests/test_app_smoke.py README.md
git commit -m "feat: streamlit app and README"
```

---

### Task 12: Remaining catalog batches

Repeat Task 10's pattern — draft, Chang reviews, add a golden scenario,
commit — for these batches:

- **Batch 2 (longitudinal and EHR):** `synthea`, `halo`, `medgan`, `eva`,
  `synteg`, `promptehr`, `ehr_safe`, `corgan`.
- **Batch 3 (time series, survival, DP tabular):** `timeautodiff`,
  `doppelganger`, `timegan`, `rtsgan`, `survivalgan`, `pate_gan`,
  `dp_ctgan`, `mst_aim`.
- **Batch 4 (diffusion, LLM, baselines, frameworks):** `tabddpm`, `tabsyn`,
  `great`, `rule_based_simulation`, `smote_family`, plus `sdv` and
  `synthcity` with `is_framework: true`.
- **Datasets:** at least `synthea_covid19`, `syntheticmass`, and any
  ready-made sets from your own projects worth handing to others.

Each batch adds at least one golden scenario exercising what that batch is
for — e.g. for batch 2, "coded event sequences + open release" should surface
`halo` or `synthea` and must exclude every cross-sectional-only method.

- [ ] Batch 2 drafted, reviewed, committed
- [ ] Batch 3 drafted, reviewed, committed
- [ ] Batch 4 drafted, reviewed, committed
- [ ] Dataset entries drafted, reviewed, committed

---

## Done when

- `python -m pytest` passes with no `ANTHROPIC_API_KEY` set.
- `streamlit run app/streamlit_app.py` produces a shortlist and a
  downloadable report for all three golden scenarios.
- The catalog holds 25–35 reviewed biomedical entries, every one with at
  least one caveat and a paper or code link.
- `catalog/taxonomy.yaml` already contains `ssh` in `domains`, so the next
  phase is catalog work only.
