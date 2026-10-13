# SynFinder v3 (evidence-grade catalog) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SynFinder's "reviewed catalog" claim checkable: biomedical-only scope, repository drift detection, per-entry provenance, honest "unknown" scoring, in-app method registration, and LLM narration on the served web path.

**Architecture:** The engine stays one Python package shared by CLI, FastAPI and the Pyodide static page. New pure logic goes in `src/synfinder/` (so it runs in the browser and is unit-testable); the one network script lives in `tools/` and writes a committed JSON file that tests read. The frontend only renders what the payload carries; it never scores.

**Tech Stack:** Python 3.11, pydantic 2, PyYAML, FastAPI (optional), Pyodide 0.28 (static page), vanilla JS, pytest, node for the JS helper tests, GitHub REST API (stdlib `urllib`, no new dependency).

**Spec:** `docs/superpowers/specs/2026-10-13-synfinder-v3-design.md`

**Scope of this plan:** spec sections 3 to 8 and 10 (code). Spec section 9 (verify every entry, add 10 to 15 entries) and section 11 (MIE paper) are content work that depends on this tooling and get their own plans afterwards.

## Global Constraints

- Python `>=3.11`; dependencies stay `pydantic>=2.6`, `pyyaml>=6.0` only. No new runtime dependency (the sync script uses stdlib `urllib`).
- Every decision is made in Python. `app.js` may not contain `DEFAULT_WEIGHTS`, `hard_filter` or `weights =` (existing test).
- All API calls in `app.js` resolve relative to the page (`const API`), never `fetch("/api`.
- `catalog/taxonomy.yaml` is the single source of truth; `domains` becomes `[biomedical, general]`.
- Rendered disclaimers and verification labels are produced by code, never stored in YAML.
- Unknown evidence scores `0.5` and renders as `?`; checked-and-empty governance scores `0.2`.
- Maintained means: not archived and pushed within 24 months of `fetched_at`.
- All existing golden scenarios in `tests/test_golden_scenarios.py` pass unchanged.
- Run tests with the repo venv: `.venv/bin/python -m pytest -q`. Node tests: `node tests/test_frontend_rendering.js`.
- Commit after every task with a conventional-commit message ending in the attribution lines:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01U9fdmnUjWC57VqEJB96T8Q`.

## Review Focus

1. A `provenance.verified_on` written as a quoted string (`"2026-10-14"`) must load the same as an unquoted YAML date. Pinned in Task 2.
2. A code link like `https://github.com/org/repo/tree/main/src` or `.../repo.git` must resolve to `org/repo`; a GitLab link must be reported as unverifiable, not crash. Pinned in Task 4.
3. A GitHub repo that now 404s (renamed, deleted) must produce an error record in `repo_metadata.json`, and the drift test must skip that entry with a message rather than fail or crash. Pinned in Task 4.
4. A submission with `formal_dp` yes and an empty mechanism, or an empty caveat list, must return inline errors from `/api/validate`, never a 500. Pinned in Task 6.
5. A generated issue URL must stay under 8,000 characters even with a long preview body, so GitHub does not reject it; the full YAML remains available through "Copy YAML". Pinned in Task 7.

---

### Task 1: Biomedical-only taxonomy

**Files:**
- Modify: `catalog/taxonomy.yaml:1`
- Modify: `catalog/methods/simpop.yaml` (the `domains:` line)
- Modify: `.github/ISSUE_TEMPLATE/new_method.yml`, `.github/ISSUE_TEMPLATE/new_dataset.yml` (domain dropdown; method form also gains `single_cell_omics`)
- Modify: `web/app.js:38` (ACRONYM map)
- Modify: `tests/test_hard_filters.py:19-22`
- Modify: `README.md`, `CONTRIBUTING.md` (scope sentences)
- Test: `tests/test_catalog_integrity.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: taxonomy `domains == ["biomedical", "general"]`, relied on by every later task's forms.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_catalog_integrity.py`:

```python
def test_the_social_science_domain_is_gone():
    """v3 is biomedical only. The word must not survive anywhere a user or a
    contributor can meet it."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    files = [root / "catalog" / "taxonomy.yaml", root / "web" / "app.js",
             *sorted((root / "catalog").rglob("*.yaml")),
             *sorted((root / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))]
    for path in files:
        assert not re.search(r"\bssh\b", path.read_text()), f"{path} mentions ssh"
    catalog = load_catalog(default_catalog_root())
    assert catalog.taxonomy["domains"] == ["biomedical", "general"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_catalog_integrity.py::test_the_social_science_domain_is_gone -q`
Expected: FAIL, "taxonomy.yaml mentions ssh".

- [ ] **Step 3: Remove the domain**

`catalog/taxonomy.yaml` line 1 becomes:

```yaml
domains: [biomedical, general]
```

`catalog/methods/simpop.yaml`: change `domains: [ssh, general]` to `domains: [general]`.

In both issue forms change the domains dropdown to `options: [biomedical, general]`. In `new_method.yml` add `- single_cell_omics` as the last `data_types` option.

In `web/app.js` delete `ssh: "SSH", ` from the `ACRONYM` object.

- [ ] **Step 4: Fix the hard-filter test that used the old value**

Replace `test_wrong_domain_is_excluded_with_a_reason` in `tests/test_hard_filters.py`:

```python
def test_wrong_domain_is_excluded_with_a_reason():
    """A method established only for biomedical work must not be offered to a
    general-domain intake."""
    kept, dropped = hard_filter([make_method(domains=["biomedical"])],
                                intake(domain="general"))
    assert kept == []
    assert "general" in dropped[0].reason
```

- [ ] **Step 5: Update the two documents**

In `README.md` replace

```
Built for health, clinical and biomedical researchers first. Social sciences
and humanities are next, and will arrive as catalog entries rather than as new
code.
```

with

```
Built for health, clinical and biomedical researchers. Methods that work on
any tabular, sequence, image, text, graph or omics data are included when they
have documented biomedical use.
```

In `CONTRIBUTING.md`, after "## What this catalog is for", add one sentence to the first paragraph: "The scope is health, clinical and biomedical research; a method with no documented biomedical use is out of scope."

- [ ] **Step 6: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (119 passed, rest skipped).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat!: biomedical-only scope, the ssh domain is removed"
```

---

### Task 2: Provenance block

**Files:**
- Modify: `src/synfinder/schema.py`
- Modify: `src/synfinder/report.py` (new `provenance_line`, used per method and dataset)
- Modify: `src/synfinder/payload.py` (`verified` field on method and dataset JSON)
- Modify: `web/app.js` (`badges`, `datasetBlock`)
- Test: `tests/test_schema.py`, `tests/test_report.py`, `tests/test_catalog_integrity.py`, `tests/test_web_api.py`

**Interfaces:**
- Produces: `schema.Provenance` model; `Method.provenance: Provenance | None`; `Dataset.provenance: Provenance | None`; `Method.governance_checked() -> bool`; `report.provenance_line(entry) -> str` returning `"Verified 14 Oct 2026 by Chang Sun"` or `"Not yet verified"`; payload key `"verified": str` on every method and dataset JSON. Task 3 uses `governance_checked()`.

- [ ] **Step 1: Write the failing schema tests**

Append to `tests/test_schema.py`:

```python
import datetime as dt
import pytest
from pydantic import ValidationError
from synfinder.schema import Provenance, Links
from tests.factories import make_method


def test_provenance_accepts_a_quoted_or_unquoted_date():
    a = Provenance(verified_on="2026-10-14", verified_by="Chang Sun",
                   sources_checked=["paper"])
    b = Provenance(verified_on=dt.date(2026, 10, 14), verified_by="Chang Sun",
                   sources_checked=["paper"])
    assert a.verified_on == b.verified_on == dt.date(2026, 10, 14)


def test_provenance_rejects_a_future_date():
    with pytest.raises(ValidationError, match="future"):
        Provenance(verified_on=dt.date.today() + dt.timedelta(days=1),
                   verified_by="x", sources_checked=["paper"])


def test_provenance_rejects_an_unknown_source():
    with pytest.raises(ValidationError, match="sources_checked"):
        Provenance(verified_on="2026-10-14", verified_by="x",
                   sources_checked=["blog"])


def test_a_checked_source_must_have_a_link_on_the_entry():
    with pytest.raises(ValidationError, match="no paper link"):
        make_method(links=Links(code="https://github.com/x/y"),
                    provenance=Provenance(verified_on="2026-10-14",
                                          verified_by="x",
                                          sources_checked=["paper"]))


def test_fields_checked_must_be_real_fields():
    with pytest.raises(ValidationError, match="fields_checked"):
        make_method(links=Links(code="https://github.com/x/y"),
                    provenance=Provenance(verified_on="2026-10-14",
                                          verified_by="x",
                                          sources_checked=["code"],
                                          fields_checked=["telepathy"]))


def test_governance_checked_reads_the_provenance():
    unchecked = make_method()
    checked = make_method(links=Links(code="https://github.com/x/y"),
                          provenance=Provenance(verified_on="2026-10-14",
                                                verified_by="x",
                                                sources_checked=["code"],
                                                fields_checked=["governance"]))
    assert unchecked.governance_checked() is False
    assert checked.governance_checked() is True
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_schema.py -q`
Expected: FAIL with ImportError on `Provenance`.

- [ ] **Step 3: Add the model and validators**

In `src/synfinder/schema.py` add after the imports:

```python
from datetime import date

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
```

Add to `Method` (after `output_preview`):

```python
    provenance: Provenance | None = None
```

and the methods:

```python
    @model_validator(mode="after")
    def _provenance_matches_entry(self) -> "Method":
        _check_provenance(self)
        return self

    def governance_checked(self) -> bool:
        """True only when someone recorded that they looked for governance
        evidence. Distinguishes "none found" from "nobody looked"."""
        return (self.provenance is not None
                and "governance" in self.provenance.fields_checked)
```

Add to `Dataset` (after `links`):

```python
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def _provenance_matches_entry(self) -> "Dataset":
        _check_provenance(self)
        return self
```

Note: `_check_provenance` is defined before `Method` but references the classes only in a string annotation, so order is fine.

- [ ] **Step 4: Run the schema tests**

Run: `.venv/bin/python -m pytest tests/test_schema.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing render and payload tests**

Append to `tests/test_report.py`:

```python
def test_provenance_line_for_both_states():
    import datetime as dt
    from synfinder.report import provenance_line
    from synfinder.schema import Provenance, Links
    assert provenance_line(make_method()) == "Not yet verified"
    verified = make_method(
        links=Links(code="https://github.com/x/y"),
        provenance=Provenance(verified_on=dt.date(2026, 10, 14),
                              verified_by="Chang Sun", sources_checked=["code"]))
    assert provenance_line(verified) == "Verified 14 Oct 2026 by Chang Sun"


def test_markdown_states_verification_for_every_method():
    md = render_markdown(intake(), rank([make_method(name="Plain")], intake()))
    assert "Not yet verified" in md
```

Append to `tests/test_web_api.py`:

```python
def test_candidates_and_datasets_carry_a_verification_label():
    body = client.post("/api/recommend", json=INTAKE).json()
    assert all("verified" in c for c in body["shortlist"])
    sets = client.get("/api/datasets").json()["datasets"]
    assert all("verified" in d for d in sets)
```

Append to `tests/test_catalog_integrity.py`:

```python
def test_unverified_entries_are_listed_but_do_not_fail(capsys):
    """The count is printed so every CI log shows how much of the catalog has
    been checked. Nothing forces 100 %: a fresh contribution is unverified
    until a maintainer verifies it, and that is the honest state."""
    catalog = load_catalog(default_catalog_root())
    entries = catalog.methods + catalog.datasets
    unverified = [e.id for e in entries if e.provenance is None]
    print(f"\n{len(unverified)} of {len(entries)} entries not yet verified: "
          + ", ".join(unverified))
    assert len(unverified) <= len(entries)
```

- [ ] **Step 6: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_report.py tests/test_web_api.py tests/test_catalog_integrity.py -q`
Expected: FAIL on `provenance_line` import and on the missing `verified` key.

- [ ] **Step 7: Render it**

In `src/synfinder/report.py` add after `PREVIEW_DISCLAIMER`:

```python
def provenance_line(entry) -> str:
    """Rendered by code so no entry can claim a check it does not carry."""
    p = getattr(entry, "provenance", None)
    if p is None:
        return "Not yet verified"
    d = p.verified_on
    return f"Verified {d.day} {d.strftime('%b %Y')} by {p.verified_by}"
```

In `render_markdown`, in the dataset loop after the `n_records` line add:

```python
            out.append(f"- {provenance_line(d)}")
```

and in the method loop, directly after the `### {i}. ...` heading and its blank line, add:

```python
        out.append(f"_{provenance_line(c.method)}_")
        out.append("")
```

In `src/synfinder/payload.py` import `from .report import provenance_line` and add `"verified": provenance_line(d)` to `_dataset_json` and `"verified": provenance_line(m)` to `_candidate_json`.

Check for an import cycle: `report.py` imports `explain`, `intake`, `ranking`, `schema`; `payload.py` already imports `explain` and `ranking`. `report` does not import `payload`, so no cycle.

In `web/app.js`, in `badges(m)` before the licence badge add:

```js
  b.push(`<span class="badge ${m.verified.startsWith("Not") ? "stale" : "ok"}">${esc(m.verified)}</span>`);
```

and in `datasetBlock(d)` add `<span class="badge ${d.verified.startsWith("Not") ? "stale" : "ok"}">${esc(d.verified)}</span>` inside `.meta-row`.

In `web/style.css`, next to the `.badge.stale` rule, add:

```css
.badge.ok{color:var(--accent); border-color:var(--accent)}
```

(If there is no `--accent` variable, use the same colour token the `.badge.dp` rule uses.)

- [ ] **Step 8: Run the suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass; the integrity test prints "75 of 75 entries not yet verified".

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: provenance block on every entry, rendered as a verification label"
```

---

### Task 3: Unknown evidence is scored and shown as unknown

**Files:**
- Modify: `src/synfinder/ranking.py` (`AxisScore.known`, `_scale_axis`, `_governance_axis`)
- Modify: `src/synfinder/explain.py` (ignore unknown axes)
- Modify: `src/synfinder/report.py` (`comparison_rows` renders `?`)
- Modify: `src/synfinder/payload.py` (`known` in axes JSON)
- Modify: `web/app.js` (`axes()` renders `?`)
- Test: `tests/test_scoring.py`, `tests/test_explain.py`, `tests/test_report.py`, `tests/test_golden_scenarios.py`

**Interfaces:**
- Consumes: `Method.governance_checked()` from Task 2.
- Produces: `AxisScore.known: bool`; constant `ranking.UNKNOWN_SCORE = 0.5`; payload axes carry `"known": bool`.

- [ ] **Step 1: Write the failing scoring tests**

Append to `tests/test_scoring.py`:

```python
def test_unknown_scale_scores_neutral_and_is_flagged():
    c = score_method(make_method(), intake(expected_rows=50_000), DEFAULT_WEIGHTS)
    a = axis(c, "scale")
    assert a.score == 0.5
    assert a.known is False


def test_verified_scale_inside_bounds_scores_full_and_is_known():
    m = make_method(scale=Scale(min_rows=1_000, max_rows=100_000, max_cols=None,
                                evidence="paper table 3"))
    a = axis(score_method(m, intake(expected_rows=50_000), DEFAULT_WEIGHTS), "scale")
    assert a.score == 1.0
    assert a.known is True


def test_unchecked_governance_is_unknown_not_absent():
    a = axis(score_method(make_method(), intake(needs_governance_evidence=True),
                          DEFAULT_WEIGHTS), "governance")
    assert a.score == 0.5
    assert a.known is False


def test_checked_and_empty_governance_scores_low_and_is_known():
    import datetime as dt
    from synfinder.schema import Provenance, Links
    m = make_method(links=Links(code="https://github.com/x/y"),
                    provenance=Provenance(verified_on=dt.date(2026, 10, 14),
                                          verified_by="x", sources_checked=["code"],
                                          fields_checked=["governance"]))
    a = axis(score_method(m, intake(needs_governance_evidence=True),
                          DEFAULT_WEIGHTS), "governance")
    assert a.score == 0.2
    assert a.known is True
```

Append to `tests/test_explain.py`:

```python
def test_an_unknown_axis_is_neither_a_strength_nor_a_weakness():
    """Nobody checked, so the method is neither praised nor blamed for it."""
    c = score_method(make_method(purposes=["ml_augmentation"]),
                     intake(expected_rows=50_000, needs_governance_evidence=True),
                     DEFAULT_WEIGHTS)
    e = explain(c)
    assert not any("size envelope" in w for w in e.why_fits)
    assert e.weakness is None or "not yet" not in e.weakness
    assert e.weakness is None or "size envelope" not in e.weakness
```

Append to `tests/test_report.py`:

```python
def test_comparison_table_shows_a_question_mark_for_unknown_axes():
    header, rows = comparison_rows(
        rank([make_method()], intake(expected_rows=50_000,
                                     needs_governance_evidence=True)))
    scale_col = header.index("Scale")
    gov_col = header.index("Governance")
    assert rows[0][scale_col] == "?"
    assert rows[0][gov_col] == "?"
```

Append to `tests/test_golden_scenarios.py`:

```python
def test_verified_scale_outranks_unknown_scale_on_an_otherwise_equal_method(weights):
    from synfinder.schema import Scale
    from tests.factories import make_method
    known = make_method(id="known", scale=Scale(
        min_rows=100, max_rows=1_000_000, max_cols=None, evidence="paper table 2"))
    unknown = make_method(id="unknown")
    intake = Intake(domain="biomedical", data_type="tabular_cross_sectional",
                    purpose="ml_augmentation", privacy="not_required",
                    expected_rows=10_000)
    ids = [c.method.id for c in rank([unknown, known], intake, weights).shortlist]
    assert ids == ["known", "unknown"]


def test_checked_and_empty_governance_ranks_below_unchecked(weights):
    """Being checked and found empty is worse news than not having been
    checked; the score must say so rather than treat both as 0.2."""
    import datetime as dt
    from synfinder.schema import Provenance, Links
    from tests.factories import make_method
    checked_empty = make_method(
        id="checked", links=Links(code="https://github.com/x/y"),
        provenance=Provenance(verified_on=dt.date(2026, 10, 14), verified_by="x",
                              sources_checked=["code"], fields_checked=["governance"]))
    unchecked = make_method(id="unchecked")
    intake = Intake(domain="biomedical", data_type="tabular_cross_sectional",
                    purpose="ml_augmentation", privacy="not_required",
                    needs_governance_evidence=True)
    ids = [c.method.id for c in rank([checked_empty, unchecked], intake, weights).shortlist]
    assert ids == ["unchecked", "checked"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_scoring.py tests/test_explain.py tests/test_report.py tests/test_golden_scenarios.py -q`
Expected: FAIL (`AxisScore` has no `known`; scale scores 1.0).

- [ ] **Step 3: Implement in `ranking.py`**

Change `AxisScore`:

```python
@dataclass
class AxisScore:
    axis: str
    score: float
    weight: float
    note: str
    # False when the catalog records nothing on this axis for this method.
    # Scored UNKNOWN_SCORE, rendered "?", and never used in an explanation.
    known: bool = True


# What an axis scores when nobody has checked it. Neutral: neither the 1.0
# that silently rewarded missing evidence before v3, nor a penalty for a gap
# that is the catalog's fault rather than the method's.
UNKNOWN_SCORE = 0.5
```

Replace the `elif max_rows is None and min_rows is None:` branch of `_scale_axis` with:

```python
    elif max_rows is None and min_rows is None:
        return AxisScore("scale", UNKNOWN_SCORE, 0.0,
                         "has no published size envelope; unverified for your size",
                         known=False)
```

Replace `_governance_axis`:

```python
def _governance_axis(method: Method) -> AxisScore:
    evidence = method.governance.acceptance_evidence
    deployments = method.governance.known_deployments
    if evidence or deployments:
        return AxisScore("governance", 1.0, 0.0,
                         "has a track record you can point a review board to")
    if method.governance_checked():
        return AxisScore("governance", 0.2, 0.0,
                         "has no documented governance or regulatory acceptance")
    return AxisScore("governance", UNKNOWN_SCORE, 0.0,
                     "has not had its governance record checked yet", known=False)
```

- [ ] **Step 4: Implement in `explain.py`, `report.py`, `payload.py`, `app.js`**

`explain.py`: change the two comprehensions to

```python
    why = [a.note for a in ranked if a.known and a.score >= STRONG][:top_k]

    losers = [a for a in candidate.axes if a.known and a.score < WEAK]
```

`report.py` `comparison_rows`: replace the cell expression with

```python
            if a is None:
                row.append("—")
            elif not a.known:
                row.append("?")
            else:
                row.append(f"{a.score:.2f}")
```

`payload.py` `_candidate_json` axes entry becomes
`{"axis": a.axis, "score": round(a.score, 3), "weight": a.weight, "note": a.note, "known": a.known}`.

`web/app.js` `axes(m)`: change the value span to

```js
      <span class="v">${a.known === false ? "?" : a.score.toFixed(2)}</span></div>`).join("")}</div>`;
```

and the bar width to `data-w="${a.known === false ? 0 : Math.round(a.score * 100)}"`.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. If any pre-existing golden scenario fails, the rule is wrong, not the scenario; stop and report.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: unknown scale and governance evidence score neutral and render as ?"
```

---

### Task 4: Repository metadata sync and drift test

**Files:**
- Create: `src/synfinder/repometa.py` (pure logic)
- Create: `tools/sync_repos.py` (network, writes `catalog/repo_metadata.json`)
- Create: `catalog/repo_metadata.json` (output of running the script once)
- Create: `tests/test_repometa.py`, `tests/test_repo_drift.py`

**Interfaces:**
- Produces: `repometa.github_slug(url) -> str | None`; `repometa.normalise_license(spdx) -> str | None`; `repometa.map_language(name) -> str | None`; `repometa.is_maintained(pushed_at, archived, fetched_at) -> bool`; `repometa.drift(entry, meta) -> list[str]`; `repometa.load_metadata(path) -> dict`. JSON layout:

```json
{"fetched_at": "2026-10-14T09:00:00Z",
 "entries": {"ctgan": {"slug": "sdv-dev/CTGAN", "license_spdx": "MIT",
                       "language": "Python", "pushed_at": "2026-09-30T10:00:00Z",
                       "archived": false, "stars": 1234,
                       "latest_release": {"tag": "v0.11.0", "published_at": "2026-05-01T00:00:00Z"}}},
 "errors": {"old_method": {"slug": "x/y", "status": 404}},
 "unverifiable": {"hapgen2": "https://mathgen.stats.ox.ac.uk/genetics_software/hapgen/hapgen2.html"}}
```

Task 5 consumes `entries`.

- [ ] **Step 1: Write the failing pure-logic tests**

Create `tests/test_repometa.py`:

```python
import datetime as dt
from synfinder import repometa
from synfinder.schema import Maturity
from tests.factories import make_method


def test_github_slug_handles_the_shapes_in_the_catalog():
    assert repometa.github_slug("https://github.com/sdv-dev/CTGAN") == "sdv-dev/CTGAN"
    assert repometa.github_slug("https://github.com/sdv-dev/CTGAN/") == "sdv-dev/CTGAN"
    assert repometa.github_slug("https://github.com/sdv-dev/CTGAN.git") == "sdv-dev/CTGAN"
    assert repometa.github_slug(
        "https://github.com/org/repo/tree/main/src") == "org/repo"
    assert repometa.github_slug("https://gitlab.com/org/repo") is None
    assert repometa.github_slug(None) is None


def test_license_aliases_collapse_and_unknowns_are_none():
    assert repometa.normalise_license("GPL-3.0-only") == "GPL-3.0"
    assert repometa.normalise_license("MIT") == "MIT"
    assert repometa.normalise_license("NOASSERTION") is None
    assert repometa.normalise_license(None) is None


def test_language_mapping():
    assert repometa.map_language("Python") == "python"
    assert repometa.map_language("Jupyter Notebook") == "python"
    assert repometa.map_language("R") == "r"
    assert repometa.map_language("Brainfuck") is None


def test_maintained_is_a_24_month_window_and_not_archived():
    now = "2026-10-14T00:00:00Z"
    assert repometa.is_maintained("2025-01-01T00:00:00Z", False, now) is True
    assert repometa.is_maintained("2024-01-01T00:00:00Z", False, now) is False
    assert repometa.is_maintained("2026-01-01T00:00:00Z", True, now) is False


META = {"slug": "x/y", "license_spdx": "MIT", "language": "Python",
        "pushed_at": "2026-09-30T00:00:00Z", "archived": False}
FETCHED = "2026-10-14T00:00:00Z"


def test_no_drift_when_the_entry_matches():
    m = make_method(license="MIT", language="python", last_updated=2026,
                    maturity=Maturity(maintained=True, implementation_quality="research_code"))
    assert repometa.drift(m, META, FETCHED) == []


def test_every_drifting_field_is_named():
    m = make_method(license="Apache-2.0", language="r", last_updated=2023,
                    maturity=Maturity(maintained=False, implementation_quality="research_code"))
    msgs = repometa.drift(m, META, FETCHED)
    assert any("license" in s and "Apache-2.0" in s and "MIT" in s for s in msgs)
    assert any("language" in s for s in msgs)
    assert any("last_updated" in s and "2023" in s and "2026" in s for s in msgs)
    assert any("maintained" in s for s in msgs)


def test_multiple_language_and_missing_values_do_not_drift():
    m = make_method(license="MIT", language="multiple", last_updated=None,
                    maturity=Maturity(maintained=True, implementation_quality="research_code"))
    assert repometa.drift(m, dict(META, license_spdx="NOASSERTION"), FETCHED) == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_repometa.py -q`
Expected: FAIL, no module `synfinder.repometa`.

- [ ] **Step 3: Write `src/synfinder/repometa.py`**

```python
"""Compare catalog entries with what their repositories say.

Pure logic only; the network lives in tools/sync_repos.py, which writes
catalog/repo_metadata.json. Tests read that committed file, so CI never
depends on GitHub being reachable.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_GITHUB = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)")

LICENSE_ALIASES = {
    "GPL-3.0-only": "GPL-3.0", "GPL-3.0-or-later": "GPL-3.0",
    "GPL-2.0-only": "GPL-2.0", "GPL-2.0-or-later": "GPL-2.0",
    "LGPL-3.0-only": "LGPL-3.0", "LGPL-3.0-or-later": "LGPL-3.0",
    "LGPL-2.1-only": "LGPL-2.1", "LGPL-2.1-or-later": "LGPL-2.1",
    "BSD-3-Clause-Clear": "BSD-3-Clause",
}
_UNKNOWN_LICENSE = {None, "", "NOASSERTION", "other"}

LANGUAGE_MAP = {
    "python": "python", "jupyter notebook": "python", "r": "r",
    "julia": "julia", "c++": "cpp", "c": "cpp", "java": "java",
    "javascript": "javascript", "typescript": "javascript",
}

MAINTAINED_WINDOW_DAYS = 730  # 24 months


def github_slug(url: str | None) -> str | None:
    if not url:
        return None
    m = _GITHUB.match(url.strip())
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}"


def normalise_license(spdx: str | None) -> str | None:
    if spdx in _UNKNOWN_LICENSE:
        return None
    return LICENSE_ALIASES.get(spdx, spdx)


def map_language(name: str | None) -> str | None:
    if not name:
        return None
    return LANGUAGE_MAP.get(name.lower())


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def is_maintained(pushed_at: str, archived: bool, fetched_at: str) -> bool:
    if archived:
        return False
    return (_parse(fetched_at) - _parse(pushed_at)).days <= MAINTAINED_WINDOW_DAYS


def drift(entry, meta: dict, fetched_at: str) -> list[str]:
    """Human-readable disagreements between a catalog entry and its repo."""
    out: list[str] = []
    repo_license = normalise_license(meta.get("license_spdx"))
    if repo_license and normalise_license(entry.license) != repo_license:
        out.append(f"{entry.id}: license is {entry.license!r} but the "
                   f"repository says {repo_license!r}")
    repo_lang = map_language(meta.get("language"))
    lang = getattr(entry, "language", None)
    if repo_lang and lang and lang != "multiple" and lang != repo_lang:
        out.append(f"{entry.id}: language is {lang!r} but the repository "
                   f"says {repo_lang!r}")
    pushed = meta.get("pushed_at")
    year = getattr(entry, "last_updated", None)
    if pushed and year is not None and year != _parse(pushed).year:
        out.append(f"{entry.id}: last_updated is {year} but the repository "
                   f"was last pushed in {_parse(pushed).year}")
    maturity = getattr(entry, "maturity", None)
    if pushed and maturity is not None:
        expected = is_maintained(pushed, bool(meta.get("archived")), fetched_at)
        if maturity.maintained != expected:
            why = "archived" if meta.get("archived") else (
                f"last pushed {pushed[:10]}")
            out.append(f"{entry.id}: maintained is {maturity.maintained} but "
                       f"the repository is {why}, so it should be {expected}")
    return out


def load_metadata(path: Path) -> dict:
    return json.loads(Path(path).read_text())
```

- [ ] **Step 4: Run the pure-logic tests**

Run: `.venv/bin/python -m pytest tests/test_repometa.py -q`
Expected: PASS.

- [ ] **Step 5: Write `tools/sync_repos.py`**

```python
"""Fetch repository facts for every catalog entry with a GitHub code link.

Writes catalog/repo_metadata.json. Run by a maintainer, not by CI:

    .venv/bin/python tools/sync_repos.py            # resume, skip fresh entries
    .venv/bin/python tools/sync_repos.py --force    # refetch everything

Uses GITHUB_TOKEN or `gh auth token` when available (5,000 requests/hour);
unauthenticated access allows 60, so a full run takes about three sessions.
On a rate limit the partial file is written and the script exits 3 with the
reset time; rerun after it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synfinder.catalog import load_catalog  # noqa: E402
from synfinder.repometa import github_slug  # noqa: E402

OUT = ROOT / "catalog" / "repo_metadata.json"
FRESH_DAYS = 7


def _token() -> str | None:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        return r.stdout.strip() or None
    except FileNotFoundError:
        return None


def _get(url: str, token: str | None) -> tuple[int, dict | None, dict]:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "synfinder-sync",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, None, dict(e.headers)


def fetch(slug: str, token: str | None) -> tuple[dict | None, int, dict]:
    status, repo, headers = _get(f"https://api.github.com/repos/{slug}", token)
    if status != 200 or repo is None:
        return None, status, headers
    meta = {
        "slug": repo.get("full_name", slug),
        "license_spdx": (repo.get("license") or {}).get("spdx_id"),
        "language": repo.get("language"),
        "pushed_at": repo.get("pushed_at"),
        "archived": bool(repo.get("archived")),
        "stars": repo.get("stargazers_count"),
        "latest_release": None,
    }
    rstatus, rel, headers = _get(
        f"https://api.github.com/repos/{slug}/releases/latest", token)
    if rstatus == 200 and rel:
        meta["latest_release"] = {"tag": rel.get("tag_name"),
                                  "published_at": rel.get("published_at")}
    return meta, 200, headers


def _rate_limited(status: int, headers: dict) -> bool:
    return status in (403, 429) and headers.get("X-RateLimit-Remaining") == "0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="refetch fresh entries too")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    existing = json.loads(OUT.read_text()) if OUT.exists() else {}
    data = {"fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "entries": dict(existing.get("entries", {})),
            "errors": {}, "unverifiable": {}}
    stamps = existing.get("stamps", {})
    data["stamps"] = dict(stamps)
    token = _token()

    catalog = load_catalog(ROOT / "catalog")
    for entry in catalog.methods + catalog.datasets:
        slug = github_slug(entry.links.code)
        if slug is None:
            if entry.links.code:
                data["unverifiable"][entry.id] = entry.links.code
            continue
        stamp = stamps.get(entry.id)
        if (not args.force and stamp and entry.id in data["entries"]
                and now - datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                < timedelta(days=FRESH_DAYS)):
            continue
        meta, status, headers = fetch(slug, token)
        if _rate_limited(status, headers):
            OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
            reset = headers.get("X-RateLimit-Reset")
            when = (datetime.fromtimestamp(int(reset), timezone.utc).isoformat()
                    if reset else "unknown")
            print(f"rate limited; partial results written; resets at {when}",
                  file=sys.stderr)
            return 3
        if meta is None:
            data["errors"][entry.id] = {"slug": slug, "status": status}
            data["entries"].pop(entry.id, None)
            print(f"  {entry.id}: HTTP {status} for {slug}")
            continue
        data["entries"][entry.id] = meta
        data["stamps"][entry.id] = data["fetched_at"]
        print(f"  {entry.id}: {slug} ok")

    OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['entries'])} entries, "
          f"{len(data['errors'])} errors, {len(data['unverifiable'])} unverifiable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Write the drift test**

Create `tests/test_repo_drift.py`:

```python
"""Each catalog entry must agree with its repository on the mechanical
facts: licence, language, last push year, maintained. The facts come from
catalog/repo_metadata.json, written by tools/sync_repos.py and committed, so
this test needs no network.
"""
import pytest
from synfinder.catalog import load_catalog
from synfinder.cli import default_catalog_root
from synfinder.repometa import drift, load_metadata

META_PATH = default_catalog_root() / "repo_metadata.json"
if not META_PATH.exists():
    pytest.skip("catalog/repo_metadata.json not present; run tools/sync_repos.py",
                allow_module_level=True)

META = load_metadata(META_PATH)
CATALOG = load_catalog(default_catalog_root())
ENTRIES = {e.id: e for e in CATALOG.methods + CATALOG.datasets}


@pytest.mark.parametrize("entry_id", sorted(ENTRIES))
def test_entry_agrees_with_its_repository(entry_id):
    entry = ENTRIES[entry_id]
    if entry_id in META.get("errors", {}):
        pytest.skip(f"{entry_id}: repository returned HTTP "
                    f"{META['errors'][entry_id]['status']}; fix the code link")
    meta = META["entries"].get(entry_id)
    if meta is None:
        pytest.skip(f"{entry_id}: no GitHub repository to compare with")
    problems = drift(entry, meta, META["fetched_at"])
    assert not problems, "\n".join(problems)


def test_metadata_is_not_stale():
    """Facts older than a year are not facts. Rerun the sync."""
    from datetime import datetime, timezone
    fetched = datetime.fromisoformat(META["fetched_at"].replace("Z", "+00:00"))
    assert (datetime.now(timezone.utc) - fetched).days < 365
```

- [ ] **Step 7: Run the sync once, for real**

Run: `.venv/bin/python tools/sync_repos.py`
If it exits 3, wait for the printed reset time and rerun; it resumes. Expected final line: `wrote catalog/repo_metadata.json: ~62 entries, N errors, M unverifiable`. Open the file and check two entries by eye (ctgan should show `sdv-dev/CTGAN`, MIT, Python).

- [ ] **Step 8: Run the drift test and record the result**

Run: `.venv/bin/python -m pytest tests/test_repo_drift.py -q 2>&1 | tail -40`
Expected: a number of FAILs naming drifted entries. That is the point: do not edit the catalog in this task. Copy the failure summary into the commit message body.

- [ ] **Step 9: Commit the tooling and the metadata, with the drift test marked expected-fail until Task 5**

Add at the top of `test_entry_agrees_with_its_repository` a temporary marker so CI stays green for exactly one commit:

```python
@pytest.mark.xfail(strict=False, reason="drift fixed in the next commit")
```

Then:

```bash
git add src/synfinder/repometa.py tools/sync_repos.py catalog/repo_metadata.json tests/test_repometa.py tests/test_repo_drift.py
git commit -m "feat: repository metadata sync and drift test

Drift found on first run:
<paste the failing entry list>"
```

---

### Task 5: Apply the mechanical repository facts to the catalog

**Files:**
- Create: `tools/apply_repo_metadata.py`
- Modify: the YAML files the drift test names (fields `license`, `language`, `last_updated`, `maturity.maintained` only)
- Modify: `tests/test_repo_drift.py` (remove the xfail marker)
- Test: `tests/test_repometa.py`

**Interfaces:**
- Consumes: `catalog/repo_metadata.json` from Task 4.
- Produces: `repometa.rewrite_fields(text: str, updates: dict[str, str]) -> str`, a line-level YAML editor that preserves comments and ordering.

- [ ] **Step 1: Write the failing test for the line editor**

Append to `tests/test_repometa.py`:

```python
def test_rewrite_fields_touches_only_the_named_lines():
    text = ("id: m\n# keep this comment\nlicense: Apache-2.0\nlanguage: r\n"
            "last_updated: 2023\nmaturity:\n  maintained: false\n"
            "  last_release: \"2023-01\"\n  implementation_quality: research_code\n")
    out = repometa.rewrite_fields(text, {"license": "MIT", "language": "python",
                                         "last_updated": "2026",
                                         "maturity.maintained": "true"})
    assert "# keep this comment" in out
    assert "license: MIT\n" in out
    assert "language: python\n" in out
    assert "last_updated: 2026\n" in out
    assert "  maintained: true\n" in out
    assert '  last_release: "2023-01"\n' in out
    assert out.count("\n") == text.count("\n")


def test_rewrite_fields_adds_a_missing_top_level_field_after_license():
    text = "id: m\nlicense: MIT\npurposes: [education]\n"
    out = repometa.rewrite_fields(text, {"language": "python"})
    assert out == "id: m\nlicense: MIT\nlanguage: python\npurposes: [education]\n"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_repometa.py -q`
Expected: FAIL, no attribute `rewrite_fields`.

- [ ] **Step 3: Implement `rewrite_fields`**

Append to `src/synfinder/repometa.py`:

```python
def rewrite_fields(text: str, updates: dict[str, str]) -> str:
    """Replace scalar lines in a YAML file without reserialising it.

    Keys are top-level (`license`) or one level under `maturity`
    (`maturity.maintained`). A missing top-level key is inserted after the
    `license:` line. Comments, order and quoting elsewhere are untouched.
    """
    lines = text.split("\n")
    for key, value in updates.items():
        if "." in key:
            parent, child = key.split(".", 1)
            inside = False
            for i, line in enumerate(lines):
                if line.startswith(f"{parent}:"):
                    inside = True
                    continue
                if inside and line and not line.startswith(" "):
                    inside = False
                if inside and line.lstrip().startswith(f"{child}:"):
                    indent = line[:len(line) - len(line.lstrip())]
                    lines[i] = f"{indent}{child}: {value}"
                    break
            continue
        for i, line in enumerate(lines):
            if line.startswith(f"{key}:"):
                lines[i] = f"{key}: {value}"
                break
        else:
            for i, line in enumerate(lines):
                if line.startswith("license:"):
                    lines.insert(i + 1, f"{key}: {value}")
                    break
    return "\n".join(lines)
```

- [ ] **Step 4: Run the test**

Run: `.venv/bin/python -m pytest tests/test_repometa.py -q`
Expected: PASS.

- [ ] **Step 5: Write `tools/apply_repo_metadata.py`**

```python
"""Write the mechanical repository facts into the catalog.

Only four fields: license, language, last_updated, maturity.maintained.
Everything that needs a human reading a paper stays untouched.

    .venv/bin/python tools/apply_repo_metadata.py          # dry run
    .venv/bin/python tools/apply_repo_metadata.py --write
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synfinder.catalog import load_catalog  # noqa: E402
from synfinder.repometa import (drift, is_maintained, load_metadata,  # noqa: E402
                                map_language, normalise_license, rewrite_fields)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    meta_all = load_metadata(ROOT / "catalog" / "repo_metadata.json")
    fetched = meta_all["fetched_at"]
    catalog = load_catalog(ROOT / "catalog")
    changed = 0
    for entry in catalog.methods + catalog.datasets:
        meta = meta_all["entries"].get(entry.id)
        if meta is None or not drift(entry, meta, fetched):
            continue
        sub = "methods" if entry.id in {m.id for m in catalog.methods} else "datasets"
        path = ROOT / "catalog" / sub / f"{entry.id}.yaml"
        updates: dict[str, str] = {}
        lic = normalise_license(meta.get("license_spdx"))
        if lic and normalise_license(entry.license) != lic:
            updates["license"] = lic
        lang = map_language(meta.get("language"))
        if lang and getattr(entry, "language", None) not in (lang, "multiple"):
            updates["language"] = lang
        if meta.get("pushed_at"):
            year = meta["pushed_at"][:4]
            if str(getattr(entry, "last_updated", None)) != year:
                updates["last_updated"] = year
            if hasattr(entry, "maturity"):
                maintained = is_maintained(meta["pushed_at"], meta.get("archived", False), fetched)
                if entry.maturity.maintained != maintained:
                    updates["maturity.maintained"] = "true" if maintained else "false"
        print(f"{entry.id}: {updates}")
        if args.write and updates:
            path.write_text(rewrite_fields(path.read_text(), updates))
        changed += 1
    print(f"{changed} entries {'updated' if args.write else 'would change'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Dry-run, read the output, then write**

Run: `.venv/bin/python tools/apply_repo_metadata.py`
Read every proposed change. A `maintained: false` on a method everyone still uses is worth a second look (an archived mirror with a live fork, for instance); in that case fix the code link in the YAML to the live repository instead and rerun the sync for that entry with `--force`. Then:

Run: `.venv/bin/python tools/apply_repo_metadata.py --write`

- [ ] **Step 7: Remove the xfail and run everything**

Delete the `@pytest.mark.xfail(...)` line from `tests/test_repo_drift.py`.

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, including every parametrised drift case (skips for errors/unverifiable are fine).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "fix: catalog licence, language, year and maintained fields now match the repositories"
```

---

### Task 6: Entry validation shared by CLI, API and browser

**Files:**
- Modify: `src/synfinder/contribute.py` (new `validate_method`, `to_yaml`; `new_entry` uses them)
- Modify: `src/synfinder/web.py` (`POST /api/validate`)
- Modify: `web/boot.js` (`validate_json`)
- Test: `tests/test_contribute.py`, `tests/test_web_api.py`

**Interfaces:**
- Produces: `contribute.validate_method(answers: dict, taxonomy: dict) -> tuple[list[str], dict | None]`; `contribute.to_yaml(entry: dict) -> str`; HTTP `POST /api/validate` with body `{"answers": {...}}` returning `{"errors": [...], "yaml": str | None}`; static backend `validate(answers)` returning the same object. Task 7 consumes all three.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_contribute.py`:

```python
from synfinder.catalog import load_catalog
from synfinder.contribute import validate_method, to_yaml

TAX = load_catalog(default_catalog_root()).taxonomy


def test_validate_method_returns_no_errors_and_the_entry_for_good_answers():
    errors, entry = validate_method(ANSWERS, TAX)
    assert errors == []
    assert entry["id"] == "mymethod"
    assert "mymethod" in to_yaml(entry)


def test_validate_method_names_a_term_outside_the_taxonomy():
    errors, entry = validate_method(dict(ANSWERS, family="telepathy"), TAX)
    assert entry is None
    assert any("telepathy" in e and "family" in e for e in errors)


def test_validate_method_reports_dp_without_a_mechanism():
    errors, entry = validate_method(dict(ANSWERS, formal_dp=True), TAX)
    assert entry is None
    assert any("dp_mechanism" in e for e in errors)


def test_validate_method_reports_an_empty_caveat_list():
    errors, entry = validate_method(dict(ANSWERS, caveats=[]), TAX)
    assert entry is None
    assert any("caveats" in e for e in errors)


def test_validate_method_reports_a_missing_required_answer():
    bad = dict(ANSWERS)
    del bad["name"]
    errors, entry = validate_method(bad, TAX)
    assert entry is None
    assert any("name" in e for e in errors)
```

Append to `tests/test_web_api.py`:

```python
GOOD_ANSWERS = {
    "id": "mymethod", "name": "MyMethod", "family": "gan",
    "domains": ["biomedical"], "data_types": ["tabular_cross_sectional"],
    "variable_types": ["continuous"], "formal_dp": False, "compute": "cpu_fine",
    "license": "MIT", "purposes": ["ml_augmentation"], "preserves": ["marginals"],
    "expertise": "medium", "maintained": True,
    "implementation_quality": "research_code",
    "caveats": ["Falls over on high-cardinality columns."], "evaluation": [],
    "paper": None, "code": "https://github.com/example/mymethod",
    "preview_format": "tabular_csv", "preview_note": "One row per person.",
    "preview_body": "age,sex\n54,F\n",
}


def test_validate_endpoint_accepts_a_good_entry():
    body = client.post("/api/validate", json={"answers": GOOD_ANSWERS}).json()
    assert body["errors"] == []
    assert body["yaml"].startswith("id: mymethod")


def test_validate_endpoint_returns_errors_not_a_500():
    bad = dict(GOOD_ANSWERS, formal_dp=True, caveats=[])
    r = client.post("/api/validate", json={"answers": bad})
    assert r.status_code == 200
    body = r.json()
    assert body["yaml"] is None
    assert any("dp_mechanism" in e for e in body["errors"])
    assert any("caveats" in e for e in body["errors"])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_contribute.py tests/test_web_api.py -q`
Expected: FAIL on the imports and a 404 from `/api/validate`.

- [ ] **Step 3: Implement in `contribute.py`**

Add after `build_dataset`:

```python
def validate_method(answers: dict, taxonomy: dict) -> tuple[list[str], dict | None]:
    """Every reason this entry cannot enter the catalog, in plain words.

    Shared by `synfinder new method`, the HTTP API and the browser form, so
    the three can never disagree about what is valid.
    """
    try:
        entry = build_method(answers)
    except KeyError as exc:
        return [f"missing answer: {exc.args[0]}"], None

    errors: list[str] = []
    for field, key in CONTROLLED.items():
        value = entry.get(field)
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        for v in values:
            if v not in taxonomy.get(key, []):
                errors.append(f"'{v}' is not a permitted {field}; choose from "
                              f"{', '.join(taxonomy.get(key, []))}")
    if errors:
        return errors, None

    try:
        Method(**entry)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"]) or "entry"
            msg = err["msg"]
            if "dp_mechanism" in msg:
                loc = "dp_mechanism"
            errors.append(f"{loc}: {msg}")
        return errors, None
    return [], entry


def to_yaml(entry: dict) -> str:
    return yaml.safe_dump(entry, sort_keys=False, width=78, allow_unicode=True)
```

Then simplify `new_entry` so the method path goes through it:

```python
def new_entry(kind: str, catalog_root: Path, answers: dict | None = None,
              out_dir: Path | None = None) -> int:
    catalog = load_catalog(catalog_root)
    a = answers if answers is not None else _interview(kind, catalog.taxonomy)

    if kind == "method":
        errors, entry = validate_method(a, catalog.taxonomy)
    else:
        entry = build_dataset(a)
        errors = []
        for field, key in CONTROLLED.items():
            value = entry.get(field)
            if value is None:
                continue
            values = value if isinstance(value, list) else [value]
            errors += [f"'{v}' is not a permitted {field}" for v in values
                       if v not in catalog.taxonomy.get(key, [])]
        if not errors:
            try:
                Dataset(**entry)
            except ValidationError as exc:
                errors.append(str(exc))
        if errors:
            entry = None
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    target_dir = out_dir or (
        Path(catalog_root) / ("methods" if kind == "method" else "datasets")
    )
    target = Path(target_dir) / f"{entry['id']}.yaml"
    target.write_text(to_yaml(entry))
    print(f"\nwrote {target}")
    print("Now: run pytest, then open a pull request. If you authored this "
          "method, say so in the pull request.")
    return 0
```

- [ ] **Step 4: Add the API route and the static equivalent**

In `src/synfinder/web.py`:

```python
from .contribute import to_yaml, validate_method


class ValidateRequest(BaseModel):
    answers: dict


@app.post("/api/validate")
def validate(req: ValidateRequest) -> dict:
    errors, entry = validate_method(req.answers, _catalog().taxonomy)
    return {"errors": errors, "yaml": to_yaml(entry) if entry else None}
```

In `web/boot.js`, inside the `py.runPython(...)` string after `datasets_json`, add:

```python
from synfinder.contribute import to_yaml, validate_method

def validate_json(payload):
    answers = json.loads(payload)
    errors, entry = validate_method(answers, CAT.taxonomy)
    return json.dumps({"errors": errors,
                       "yaml": to_yaml(entry) if entry else None})
```

and extend the returned object:

```js
    validate: (answers) =>
      JSON.parse(py.globals.get("validate_json")(JSON.stringify(answers))),
```

In `web/app.js` add to `backend`:

```js
  async validate(answers) {
    if (window.SYNFINDER_STATIC) return (await window.synReady).validate(answers);
    const res = await fetch(API + "api/validate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
```

- [ ] **Step 5: Run the suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: one validate_method shared by the CLI, the API and the browser"
```

---

### Task 7: "Submit a method" tab

**Files:**
- Modify: `web/index.html` (third tab button; new `<main id="view-submit">`)
- Modify: `web/app.js` (tab switching, form fill, helpers, submit handler)
- Modify: `web/style.css` (textarea rule, `.badge.ok` if not added in Task 2)
- Modify: `.github/ISSUE_TEMPLATE/new_method.yml` (new `entry_yaml` textarea)
- Modify: `README.md` (how registration works)
- Test: `tests/test_frontend_rendering.js`, `tests/test_web_api.py`

**Interfaces:**
- Consumes: `backend.validate(answers)` from Task 6; taxonomy from `/api/taxonomy`.
- Produces: JS pure helpers `collectLines(text) -> string[]` and `issueUrl(answers, yamlText) -> string` under the marker `/* ---------- submission helpers ---------- */`.

- [ ] **Step 1: Write the failing node tests**

In `tests/test_frontend_rendering.js`, after the existing `load(...)` calls add:

```js
load("/* ---------- submission helpers ---------- */", "/* ---------- submission ---------- */",
     ["collectLines", "issueUrl", "ISSUE_BASE"]);
```

and before the final summary add:

```js
console.log("submission helpers");
check("lines split and blanks dropped",
  JSON.stringify(collectLines(" a \n\n b\n")) === JSON.stringify(["a", "b"]));
const answers = { name: "My Method", domains: ["biomedical"], data_types: ["images"],
  compute: "cpu_fine", expertise: "low", formal_dp: false,
  caveats: ["It breaks."], preview_body: "x,y\n1,2", paper: "doi:1", code: "https://github.com/a/b" };
const url = issueUrl(answers, "id: my_method\n");
check("issue url targets the method form", url.startsWith(ISSUE_BASE) && url.includes("template=new_method.yml"));
check("title is prefilled", decodeURIComponent(url).includes("title=[method] My Method"));
check("yaml is carried", decodeURIComponent(url).includes("entry_yaml=id: my_method"));
check("authorship is not prefilled", !url.includes("authorship="));
const longUrl = issueUrl(answers, "id: x\n" + "preview: |\n" + "  row\n".repeat(5000));
check("url stays under the GitHub limit", longUrl.length < 8000);
check("truncation is announced", decodeURIComponent(longUrl).includes("truncated"));
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node tests/test_frontend_rendering.js`
Expected: fails at the `load` call (marker not found).

- [ ] **Step 3: Add the helpers to `app.js`**

Insert before `/* ---------- dataset browse ---------- */`:

```js
/* ---------- submission helpers ---------- */
const ISSUE_BASE = "https://github.com/sunchang0124/SynFinder/issues/new";
const MAX_ISSUE_URL = 7500;

// One item per non-blank line; the textarea fields use this.
function collectLines(text) {
  return String(text || "").split("\n").map(s => s.trim()).filter(Boolean);
}

// A prefilled GitHub issue. Field ids match .github/ISSUE_TEMPLATE/new_method.yml;
// the YAML goes into entry_yaml so a maintainer can save it as the catalog file.
// GitHub rejects very long URLs, so the YAML is cut with a note; the page also
// offers the full text through "Copy YAML".
function issueUrl(answers, yamlText) {
  const params = {
    template: "new_method.yml",
    title: `[method] ${answers.name || ""}`,
    name: answers.name || "",
    domains: (answers.domains || []).join(","),
    data_types: (answers.data_types || []).join(","),
    compute: answers.compute || "",
    expertise: answers.expertise || "",
    formal_dp: answers.formal_dp ? "yes - state the mechanism below" : "no",
    caveats: (answers.caveats || []).join("\n"),
    preview: answers.preview_body || "",
    links: [answers.paper, answers.code].filter(Boolean).join(" "),
  };
  const build = (yaml) => ISSUE_BASE + "?" +
    Object.entries({ ...params, entry_yaml: yaml })
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
  let url = build(yamlText);
  if (url.length > MAX_ISSUE_URL) {
    let keep = yamlText.length;
    while (url.length > MAX_ISSUE_URL && keep > 0) {
      keep = Math.floor(keep * 0.8);
      url = build(yamlText.slice(0, keep) + "\n# ... truncated for the URL; paste the full YAML from the app\n");
    }
  }
  return url;
}
```

- [ ] **Step 4: Run the node tests**

Run: `node tests/test_frontend_rendering.js`
Expected: all checks pass.

- [ ] **Step 5: Add the tab and form to `index.html`**

In the `<nav class="tabs">` add a third button:

```html
    <button class="tab" data-view="submit" role="tab">Submit a method</button>
```

Before `<script>/*__JS__*/</script>` add:

```html
<!-- ============ SUBMIT ============ -->
<main class="layout hidden" id="view-submit">
  <aside class="panel">
    <form id="submitForm" autocomplete="off">
      <div class="panel-head">
        <h2>Register a method</h2>
        <p>Checked against the same schema as the catalog. A valid entry opens a prefilled GitHub issue; a maintainer reviews it and it appears here after merge.</p>
      </div>
      <div class="field"><label for="s_id">Identifier (lowercase, underscores)</label><input type="text" id="s_id" placeholder="my_method"></div>
      <div class="field"><label for="s_name">Display name</label><input type="text" id="s_name"></div>
      <div class="field"><label for="s_family">Family</label><div class="select"><select id="s_family"></select></div></div>
      <div class="field"><label>Domains</label><div class="chips" id="s_domains"></div></div>
      <div class="field"><label>Data types</label><div class="chips" id="s_data_types"></div></div>
      <div class="field"><label>Variable types</label><div class="chips" id="s_variable_types"></div></div>
      <div class="field"><label for="s_formal_dp">Formal differential privacy</label><div class="select"><select id="s_formal_dp"><option value="no">No</option><option value="yes">Yes</option></select></div></div>
      <div class="field"><label for="s_dp_mechanism">DP mechanism (if yes)</label><input type="text" id="s_dp_mechanism" placeholder="DP-SGD with an RDP accountant"></div>
      <div class="field"><label for="s_compute">Compute</label><div class="select"><select id="s_compute"></select></div></div>
      <div class="field"><label for="s_license">Licence (SPDX id)</label><input type="text" id="s_license" placeholder="MIT"></div>
      <div class="field"><label>Purposes</label><div class="chips" id="s_purposes"></div></div>
      <div class="field"><label>Preserves</label><div class="chips" id="s_preserves"></div></div>
      <div class="field"><label for="s_expertise">Expertise needed</label><div class="select"><select id="s_expertise"></select></div></div>
      <label class="check"><input type="checkbox" id="s_maintained" checked><span></span>Actively maintained</label>
      <div class="field"><label for="s_quality">Implementation quality</label><div class="select"><select id="s_quality"></select></div></div>
      <div class="field"><label for="s_caveats">Caveats, one per line (real failure modes, not marketing)</label><textarea id="s_caveats" rows="4"></textarea></div>
      <div class="field"><label for="s_evaluation">How to check it worked, one per line</label><textarea id="s_evaluation" rows="3"></textarea></div>
      <div class="field"><label for="s_preview_format">Output preview format</label><div class="select"><select id="s_preview_format"></select></div></div>
      <div class="field"><label for="s_preview_note">One line describing the output</label><input type="text" id="s_preview_note"></div>
      <div class="field"><label for="s_preview_body">A few lines showing the shape (not real output)</label><textarea id="s_preview_body" rows="4"></textarea></div>
      <div class="field"><label for="s_paper">Paper DOI or URL</label><input type="text" id="s_paper"></div>
      <div class="field"><label for="s_code">Code repository URL</label><input type="text" id="s_code"></div>
      <label class="check"><input type="checkbox" id="s_author"><span></span>I am an author of this method</label>
      <button class="btn-primary" type="submit" id="validateBtn"><span class="btn-label">Check and prepare submission</span></button>
    </form>
  </aside>
  <section class="results" id="submitResults">
    <div class="empty-state">
      <h3>Add a method to the catalog</h3>
      <p>Fill in the form. Nothing is sent anywhere until you open the GitHub issue yourself.</p>
    </div>
  </section>
</main>
```

In `web/style.css`, next to the rule that styles `.field input`, add `textarea` to the selector so it inherits the same look, and add:

```css
.field textarea{resize:vertical; font-family:inherit; width:100%}
```

- [ ] **Step 6: Wire the form in `app.js`**

Replace the tab handler:

```js
/* ---------- tabs ---------- */
const VIEWS = ["find", "browse", "submit"];
document.querySelectorAll(".tab").forEach(t => {
  t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("is-active", x === t));
    VIEWS.forEach(v => $("#view-" + v).classList.toggle("hidden", t.dataset.view !== v));
    if (t.dataset.view === "browse") loadDatasets();
  };
});
```

In `boot()` after the browse selects:

```js
  fill("#s_family", TAX.families);
  chips("#s_domains", TAX.domains);
  chips("#s_data_types", TAX.data_types);
  chips("#s_variable_types", TAX.variable_types);
  fill("#s_compute", TAX.compute);
  chips("#s_purposes", TAX.purposes);
  chips("#s_preserves", TAX.preserves);
  fill("#s_expertise", TAX.expertise);
  fill("#s_quality", TAX.implementation_quality);
  fill("#s_preview_format", TAX.preview_formats);
```

Insert after the helpers block and before `/* ---------- dataset browse ---------- */`:

```js
/* ---------- submission ---------- */
function collectSubmission() {
  const v = id => $("#" + id).value.trim();
  return {
    id: v("s_id"), name: v("s_name"), family: v("s_family"),
    domains: chosen("#s_domains"), data_types: chosen("#s_data_types"),
    variable_types: chosen("#s_variable_types"),
    formal_dp: v("s_formal_dp") === "yes",
    dp_mechanism: v("s_dp_mechanism") || null,
    compute: v("s_compute"), license: v("s_license"),
    purposes: chosen("#s_purposes"), preserves: chosen("#s_preserves"),
    expertise: v("s_expertise"), maintained: $("#s_maintained").checked,
    implementation_quality: v("s_quality"),
    caveats: collectLines(v("s_caveats")), evaluation: collectLines(v("s_evaluation")),
    preview_format: v("s_preview_format"), preview_note: v("s_preview_note"),
    preview_body: v("s_preview_body"),
    paper: v("s_paper") || null, code: v("s_code") || null,
    author: $("#s_author").checked,
  };
}

$("#submitForm").onsubmit = async e => {
  e.preventDefault();
  const answers = collectSubmission();
  const el = $("#submitResults");
  let result;
  try { result = await backend.validate(answers); }
  catch (err) { el.innerHTML = `<div class="notice"><b>Validation failed to run.</b><br>${esc(err.message)}</div>`; return; }
  if (result.errors.length) {
    el.innerHTML = `<div class="notice"><b>Not valid yet.</b><ul>${result.errors.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    return;
  }
  const url = issueUrl(answers, result.yaml);
  el.innerHTML = `<p class="section-label">Valid entry</p>
    <div class="card">
      <p class="why">This is the catalog file a maintainer will review.${answers.author ? " You declared authorship; thank you." : ""}</p>
      <pre id="yamlOut">${esc(result.yaml)}</pre>
      <div class="dl-row">
        <button class="dl" id="openIssue">Open a prefilled GitHub issue</button>
        <button class="dl" id="copyYaml">Copy YAML</button>
      </div>
      <p class="why dim">Prefer a pull request? Save the YAML as <code>catalog/methods/${esc(answers.id)}.yaml</code>, run <code>pytest</code>, and open the PR.</p>
    </div>`;
  $("#openIssue").onclick = () => window.open(url, "_blank", "noopener");
  $("#copyYaml").onclick = async () => {
    try { await navigator.clipboard.writeText(result.yaml); $("#copyYaml").textContent = "Copied"; }
    catch (err) { $("#copyYaml").textContent = "Select the text above and copy"; }
  };
};
```

- [ ] **Step 7: Add the YAML field to the issue form**

In `.github/ISSUE_TEMPLATE/new_method.yml`, before the `authorship` checkboxes add:

```yaml
  - type: textarea
    id: entry_yaml
    attributes:
      label: Generated catalog entry (YAML)
      description: Filled in by the app's Submit tab. Leave empty if you used the form by hand.
      render: yaml
```

- [ ] **Step 8: Add a page test and update the README**

Append to `tests/test_web_api.py`:

```python
def test_the_page_carries_the_submit_tab():
    html = client.get("/").text
    assert 'data-view="submit"' in html
    assert 'id="submitForm"' in html
    assert "api/validate" in html, "the submit flow must call the shared validator"
```

In `README.md`, in the "Contributing" section, add as the first route:

```
**From the app.** Open the *Submit a method* tab, fill in the form, and press
*Check and prepare submission*. The entry is validated against the same
schema the catalog uses; a valid one opens a prefilled GitHub issue with the
YAML attached. A maintainer reviews it, saves the YAML into
`catalog/methods/`, and the method appears on the live page after the next
deploy. Nothing is sent until you open the issue yourself.
```

- [ ] **Step 9: Run everything, then look at it**

Run: `.venv/bin/python -m pytest -q && node tests/test_frontend_rendering.js`
Expected: all pass.

Run: `./run_web.sh` and open `http://localhost:8501`, click *Submit a method*, submit an empty form (expect inline errors), fill a valid one (expect YAML and two buttons; the issue button opens GitHub with the fields prefilled). Stop the server.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: Submit a method tab, validated in the browser, opens a prefilled GitHub issue"
```

---

### Task 8: LLM narration on the served web path

**Files:**
- Modify: `src/synfinder/llm.py` (model id, request shape)
- Modify: `src/synfinder/web.py` (narration in `/api/recommend`)
- Modify: `src/synfinder/payload.py` (`narration: None` default)
- Modify: `web/app.js` (`card()` renders narration)
- Test: `tests/test_llm.py`, `tests/test_web_api.py`

**Interfaces:**
- Consumes: `llm.available()`, `llm.narrate(explanation, method, intake)`, `explain.explain(candidate)`.
- Produces: `"narration": str | None` on every shortlist candidate from `/api/recommend`; the static page always sends `null`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm.py`:

```python
def test_model_is_the_current_opus():
    assert llm.MODEL == "claude-opus-5-5"
```

Append to `tests/test_web_api.py`:

```python
def test_recommend_carries_narration_when_a_model_is_available(monkeypatch):
    from synfinder import llm, web
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "narrate", lambda e, m, i: f"Fluent prose about {m.name}.")
    body = client.post("/api/recommend", json=INTAKE).json()
    first = body["shortlist"][0]
    assert first["narration"] == f"Fluent prose about {first['name']}."
    assert all(c["narration"] is None for c in body["also_ranked"])


def test_recommend_narration_is_null_without_a_model(monkeypatch):
    from synfinder import llm
    monkeypatch.setattr(llm, "available", lambda: False)
    body = client.post("/api/recommend", json=INTAKE).json()
    assert all(c["narration"] is None for c in body["shortlist"])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_llm.py tests/test_web_api.py -q`
Expected: FAIL (model id, missing key).

- [ ] **Step 3: Update `llm.py`**

```python
MODEL = "claude-opus-5-5"
```

and `_call`:

```python
def _call(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    # Opus 5.5 always thinks; depth is set through effort. Low is right for
    # rewriting three sentences. Thinking tokens count against max_tokens.
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        output_config={"effort": "low"},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    if message.stop_reason == "refusal":
        return ""
    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
```

- [ ] **Step 4: Thread it through the API and the page**

`payload.py` `_candidate_json`: add `"narration": None,` after `"verified"`.

`web.py` `recommend`: import `from . import llm` and `from .explain import explain`; after computing `top`:

```python
    shortlist_json = [_candidate_json(c) for c in top]
    if llm.available():
        for c, j in zip(top, shortlist_json):
            j["narration"] = llm.narrate(explain(c), c.method, intake)
```

and use `shortlist_json` in the returned dict instead of recomputing.

`web/app.js` `card(m, i)`: after the `why_fits` paragraph add

```js
    ${m.narration ? `<p class="why"><span class="dim">In plain words —</span> ${esc(m.narration)} <span class="dim">(rewritten from the catalog text by an AI model; it cannot add claims)</span></p>` : ""}
```

- [ ] **Step 5: Run the suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: optional LLM narration on the served web path, Opus 5.5"
```

---

### Task 9: Docs, contributor checklist, version

**Files:**
- Modify: `README.md` ("How it decides" gains the unknown rule; new "Keeping the catalog honest" section)
- Modify: `CONTRIBUTING.md` (maintainer verification procedure)
- Modify: `pyproject.toml` (`version = "0.3.0"`)
- Test: `tests/test_links.py` already checks README links; no new test.

- [ ] **Step 1: README**

Under "How it decides" add a fourth point:

```
4. **Unknown is not fine.** An axis the catalog records nothing on scores a
   neutral 0.5 and shows as `?`, never as a silent 1.0. The explanation does
   not praise or blame a method for something nobody checked.
```

Add a section before "Adding a catalog entry":

```
## Keeping the catalog honest

Every entry can carry a `provenance` block: who checked it, on what date,
against which sources, and which fields. The app and the report show
"Verified <date> by <name>" or "Not yet verified"; the label is rendered by
code, so no entry can claim a check it does not carry. CI prints how many
entries are unverified.

The mechanical facts are checked by machine. `tools/sync_repos.py` reads
licence, language, last push, archived status and latest release from GitHub
into `catalog/repo_metadata.json`; `tests/test_repo_drift.py` fails when an
entry disagrees with its repository; `tools/apply_repo_metadata.py` writes
the corrections. Run the sync a few times a year.
```

- [ ] **Step 2: CONTRIBUTING**

Add after the maintainer review checklist:

```
## Verifying an entry

1. Run `tools/sync_repos.py` and `pytest tests/test_repo_drift.py`; fix any
   mechanical drift with `tools/apply_repo_metadata.py --write`.
2. Open the paper. Confirm `data_types`, `variable_types`, `purposes`,
   `preserves`, `formal_dp` and `dp_mechanism`. Record scale bounds only
   with the table or figure they come from; otherwise leave them empty.
3. Look for governance evidence: a named regulator, ethics board,
   statistics agency or deployment. Record what you find, or nothing, and
   list `governance` in `fields_checked` either way.
4. Reread the caveats against the paper's limitations section and the
   repository issues. Sharpen them.
5. Write the `provenance` block:

   ```yaml
   provenance:
     verified_on: 2026-10-14
     verified_by: Your Name
     sources_checked: [paper, code]
     fields_checked: [data_types, formal_dp, scale, governance, caveats]
     notes: Scale from Table 3; DP accountant checked in train.py.
   ```
```

- [ ] **Step 3: Version and final run**

Set `version = "0.3.0"` in `pyproject.toml`.

Run: `.venv/bin/python -m pytest -q && node tests/test_frontend_rendering.js && .venv/bin/python tools/build_pages.py`
Expected: all pass; the static bundle builds. Open `docs_site/index.html` through a local static server (`python -m http.server -d docs_site 8600`) and confirm the Submit tab validates in the browser (Pyodide path). Stop the server.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: v3 honesty mechanisms, verification procedure, version 0.3.0"
```

---

## Self-review notes

- Spec §3 → Task 1. §4 → Tasks 4, 5. §5 → Task 2. §6 → Task 3. §7 → Tasks 6, 7. §8 → Task 8. §10 testing table → each row has a test above. §9 and §11 deliberately excluded (content plans).
- Names used across tasks: `Provenance`, `governance_checked()`, `provenance_line`, `AxisScore.known`, `UNKNOWN_SCORE`, `validate_method`, `to_yaml`, `backend.validate`, `issueUrl`, `collectLines`, `ISSUE_BASE`, `drift`, `rewrite_fields` are each defined once and reused with the same signature.
- Review Focus items 1 to 5 are pinned in Tasks 2, 4, 4, 6, 7 respectively.
