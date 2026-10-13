# SynFinder v3 — evidence-grade catalog

**Date:** 2026-10-13
**Status:** approved design
**Author:** Chang Sun (with Claude)
**Builds on:** `2026-09-18-synfinder-design.md` (v1) and
`2026-09-18-synfinder-v2-design.md` (v2), both shipped at commit `89e0923`.

## 1. Why v3

The BioHackathon 2026 report audited the v2 catalog honestly and found the
weak spots: only 3 of 66 rankable entries carry scale bounds, 35 have no
governance record, an entry with nothing recorded scores the same as an
entry that was checked and found fine, and nothing records who verified an
entry or when. The tool's claim is that its judgement is reviewed; v3 makes
that claim checkable.

v3 also narrows scope. SynFinder is for health, clinical and biomedical
researchers. The social-science roadmap is dropped.

v3 is the version demonstrated at MIE 2027 (Tallinn, 26–30 April 2027,
demonstration track, 1–3 IOS Press pages, deadline 26 January 2027).

## 2. What v3 adds, in build order

1. Biomedical-only taxonomy (removes `ssh`).
2. Repository metadata sync and a drift test.
3. A `provenance` block on every entry, shown in the app and the report.
4. Unknown evidence scored and displayed as unknown, not as fine.
5. In-app registration: a "Submit a method" tab that validates in the
   browser and opens a prefilled GitHub issue.
6. LLM narration wired to the FastAPI path.
7. Catalog verification of every existing entry, then gap filling.
8. The MIE 2027 demonstration paper (separate repository, see §11).

Order matters: 2–4 define what "verified" means before 7 does the verifying,
and 8 describes the finished tool.

## 3. Biomedical only

- `catalog/taxonomy.yaml`: `domains: [biomedical, general]`.
- `simpop` (the one entry tagged `ssh`) becomes `[general]`.
- `.github/ISSUE_TEMPLATE/new_method.yml` and `new_dataset.yml`: drop `ssh`
  from the domain dropdown. The method form also gains `single_cell_omics`,
  which the taxonomy already has and the form does not.
- `web/app.js`: remove the `ssh` acronym entry.
- `tests/test_hard_filters.py`: the domain-mismatch test currently tags a
  method `ssh`; it will tag the method `biomedical` and use a `general`
  intake, which is still a mismatch under the existing rule.
- README and CONTRIBUTING: remove the "social sciences and humanities are
  next" sentence; state the scope as health, clinical and biomedical.

The `domains` field stays. A method tagged `general` is shown for a
biomedical intake, exactly as before.

## 4. Repository sync and drift test

### 4.1 `tools/sync_repos.py`

For every method and dataset whose `links.code` is a `github.com/<owner>/<repo>`
URL, fetch from the GitHub REST API:

| field | source |
|---|---|
| `license_spdx` | `GET /repos/{o}/{r}` → `license.spdx_id` |
| `language` | same → `language` (mapped to the taxonomy's `languages`) |
| `pushed_at` | same |
| `archived` | same |
| `stars` | same → `stargazers_count` |
| `latest_release` | `GET /repos/{o}/{r}/releases/latest` → `tag_name`, `published_at`; 404 means none |

Output: `catalog/repo_metadata.json`, one object per entry id plus a
top-level `fetched_at`. Entries whose code link is not on GitHub (GitLab,
CRAN, a lab page) are listed under `unverifiable` with the URL, so the gap
is visible rather than silent.

Authentication: uses `GITHUB_TOKEN` or `gh auth token` when present;
otherwise unauthenticated, which allows 60 requests an hour. Two calls per
repo for ~65 repos is one run when authenticated and about three when not;
the script writes partial results and resumes from them rather than failing
on a 403 rate limit.

The script is run by a maintainer, not by CI. The JSON is committed. CI
tests against the committed file so test results do not depend on network
access or on GitHub being up.

### 4.2 `tests/test_repo_drift.py`

For every entry present in `repo_metadata.json`:

- `license` must equal `license_spdx` when the API returned one. Known
  aliases are tolerated through a small map (`GPL-3.0` ≈ `GPL-3.0-only`,
  `MIT` ≈ `MIT`). `NOASSERTION` and `null` do not fail.
- `language` must equal the mapped repository language when both are set.
  Multi-language repositories (`multiple`) pass against any value.
- `last_updated` must equal the year of `pushed_at`.
- `maturity.maintained` must be `true` if and only if the repository is not
  archived and `pushed_at` is within 24 months of `fetched_at`.

Failure message names the entry, the field, the catalog value and the
repository value. A single test parametrised over entries, so one drifted
entry fails alone.

### 4.3 What this does not check

Anything that needs reading a paper: data types, purposes, DP claims,
caveats, scale bounds. Those are what §9 is for.

## 5. Provenance

### 5.1 Schema

New optional block on `Method` and `Dataset`:

```yaml
provenance:
  verified_on: 2026-10-14        # ISO date
  verified_by: Chang Sun         # person or GitHub handle
  sources_checked: [paper, code, docs]   # subset of {paper, code, docs}
  fields_checked: [data_types, formal_dp, scale, governance, caveats]
  notes: >-
    Scale bounds from Table 3 of the paper. DP claim checked against the
    training loop in train.py; the accountant is RDP.
```

Validation:

- `sources_checked` values must be a subset of `{paper, code, docs}` and
  each named source must have a matching non-null link on the entry.
- `fields_checked` values must be top-level `Method` field names (or the
  two special names `scale` and `governance`).
- `verified_on` must not be in the future.

### 5.2 Display

- App card and report: "Verified 14 Oct 2026 by Chang Sun" or
  "Not yet verified". Rendered by code, not stored, so no entry can claim a
  verification it does not carry.
- The comparison table gains no column; provenance is per-card text.

### 5.3 Visibility in CI

`tests/test_catalog_integrity.py` gains a test that lists unverified
entries to stdout and passes. The count is therefore in every CI log and can
be cited. Nothing forces 100 %: a contributor's fresh entry is unverified
until a maintainer verifies it, and that is the honest state.

## 6. Unknown is not fine

### 6.1 Scale

Today an entry with no row bounds scores 1.0 ("has no published size
envelope in the catalog yet"), which is 63 of 66 entries. New rule:

| situation | score | table cell | note |
|---|---|---|---|
| bounds present, rows inside | 1.0 | `1.00` | handles N rows comfortably |
| bounds present, rows ≤ 2× over max | 0.4 | `0.40` | usually run on at most ~M rows |
| bounds present, rows > 2× over max | 0.1 | `0.10` | same |
| bounds present, rows under min | 0.4 | `0.40` | needs roughly m rows to train well |
| no bounds | 0.5 | `?` | no published size envelope; unverified for your size |

The axis still only activates when the user gave `expected_rows`.

### 6.2 Governance

Today "no records" scores 0.2. That conflates "checked, none found" with
"nobody looked". New rule:

| situation | score | table cell | note |
|---|---|---|---|
| any acceptance evidence or deployment | 1.0 | `1.00` | has a track record you can point a review board to |
| none, and `governance` in `provenance.fields_checked` | 0.2 | `0.20` | no documented governance or regulatory acceptance |
| none, and governance not checked | 0.5 | `?` | governance not yet checked |

### 6.3 Mechanics

`AxisScore` gains `known: bool = True`. The two axes above set it to
`False` for the unknown case. `report.comparison_rows` renders `?` when
`known` is false. `explain` treats an unknown axis as neither a strength nor
a weakness: it is excluded from `why_fits` and from the weakness pick, so a
method is never praised or blamed for something nobody checked.

Tie-breaking keeps using governance record counts; an unknown counts as 0,
which is the status quo.

### 6.4 Golden scenarios

All existing golden scenarios must pass unchanged. If one fails, the weights
or the rule are wrong, not the scenario. Two scenarios are added: an intake
with `expected_rows` where an entry with verified bounds outranks an
otherwise identical entry without them; and an intake with
`needs_governance_evidence` where checked-and-empty scores below unchecked.

## 7. In-app registration

### 7.1 Surface

A third tab, "Submit a method", next to "Find a method" and "Datasets".
One form, fields in the same order as `synfinder new method`:

id, name, family, domains, data types, variable types, formal DP (+ mechanism),
compute, licence, purposes, preserves, expertise, maintained,
implementation quality, caveats (one per line, at least one), evaluation
steps (one per line), preview format, preview note, preview body, paper URL,
code URL, authorship checkbox.

Dropdowns and chip groups are built from the live taxonomy, exactly as the
intake form is, so the form cannot drift from the taxonomy.

### 7.2 Validation

A new pure function `contribute.validate_method(answers: dict) -> list[str]`
returns human-readable errors (empty list when valid). It reuses
`build_method` and the `Method` model, and it is what `synfinder new method`
calls too, so the CLI and the form agree.

- FastAPI: `POST /api/validate` → `{"errors": [...], "yaml": "..." | null}`.
- Static page: `boot.js` exposes `validate_json(payload)` calling the same
  function.

Errors are shown inline next to the form, not as an alert.

### 7.3 Submission

On a valid entry the page:

1. Renders the YAML (same dump settings as the CLI).
2. Opens `https://github.com/sunchang0124/SynFinder/issues/new` in a new
   tab with `template=new_method.yml`, `title=[method] <name>` and the form
   fields prefilled through query parameters (GitHub issue forms accept a
   query parameter per field id). The generated YAML goes into a new
   `entry_yaml` textarea added to the issue form.
3. Offers "Copy YAML" and a one-line instruction for the pull-request route.

A maintainer converts the issue into a pull request by saving the YAML as
`catalog/methods/<id>.yaml`. The entry appears on the live page after merge
and the Pages redeploy, which the README states.

### 7.4 Out of scope

Dataset submission from the app (the issue form remains); automatic pull
requests; any server-side state.

## 8. LLM narration on the web path

- `web.recommend` adds `"narration": str | None` to each shortlist
  candidate when `llm.available()` is true on the server. Narration failures
  degrade to `None`, as today.
- `app.js` renders the narration under the template rationale with the
  label "Rewritten from the catalog text by an AI model; it cannot add
  claims." When `null`, nothing is rendered.
- The static page never calls a model; `boot.js` returns `null`.
- `llm.MODEL` is updated to the current Claude model id; the request shape
  is checked against the current SDK before the change (claude-api skill).
- Test: with narration mocked, the JSON carries the string; with the key
  unset, the field is `null` and the page renders without it.

## 9. Catalog verification and gap filling

### 9.1 Verification pass

For each of the 66 rankable entries, 3 frameworks and 6 datasets:

1. Run the drift test; fix `license`, `language`, `last_updated`,
   `maintained` from `repo_metadata.json`.
2. Open the paper. Confirm `data_types`, `variable_types`, `purposes`,
   `preserves`, `formal_dp` and `dp_mechanism`. Record scale bounds with the
   table or figure they come from, where the paper gives them; otherwise
   leave bounds empty (unknown is now honest).
3. Check governance: a documented regulator, ethics board, statistical
   agency or named deployment goes in; a vague "used in healthcare" does
   not. Either way, `governance` goes into `fields_checked`.
4. Reread caveats against the paper's own limitations section and the
   repository issues. Add or sharpen as needed.
5. Remove any `UNVERIFIED` marker. Write the `provenance` block.

Entries are verified in batches of ~10, each batch a commit, so review is
by diff.

### 9.2 Gap filling

Sources: the synthcity plugin list, two or three 2024–2026 surveys of
synthetic health data generation, and GitHub topic search. Inclusion rule:
public code, a paper or documentation, and documented biomedical use.
Target 10–15 new entries, each drafted with a full provenance block and
reviewed by Chang before merge. Nothing enters unreviewed.

Starting list, to be confirmed during drafting: CopulaGAN, DataSynthesizer,
SDV PAR (sequential), MOSTLY AI open-source SDK, gretel-synthetics,
ydata-synthetic, Synthia, simsurv, survsim, TabuLa, CLLM, scVI, SymSim,
stdpopsim; MONAI Generative as a framework. Datasets: CPRD synthetic data,
NHS England synthetic A&E, SyntheticMass.

Commercial, closed tools (MDClone, Syntegra, Gretel cloud) are out of scope:
with no inspectable code there is nothing to verify.

## 10. Testing summary

| area | test |
|---|---|
| taxonomy | no entry, form or source file mentions `ssh` |
| sync | parser handles a GitHub URL with trailing path, a non-GitHub URL, a 404 release |
| drift | parametrised per entry; aliases; archived repos |
| provenance | subset checks; future date rejected; render text for both states |
| unknown | axis `known` flag; `?` in table; excluded from explanation; two new golden scenarios |
| registration | `validate_method` errors for each controlled field; `/api/validate` round trip; issue URL builder |
| narration | mocked round trip through `/api/recommend`; absent without key |
| catalog | unverified count printed; all existing golden scenarios unchanged |

## 11. MIE 2027 demonstration paper

- Repository: `~/papers/synfinder-mie2027-demo/`, built with the IOS Press
  Word template in `~/Documents/MIE_submission_template/` through the
  `build_docx.py` approach used for the VENI MIE paper.
- Length: 3 pages. Sections: problem; system (catalog, engine, interfaces);
  demonstration walk-through of one scenario with a screenshot of the live
  page; what makes the catalog trustworthy (provenance, drift test, unknown
  handling, review gate); limits and availability.
- Track: Clinical Decision Support, Trustworthy AI, and Learning Health
  Systems. Deadline 26 January 2027; notification 7 February 2027.
- Honesty constraints carried over from the BH26 report: no claim of
  recommendation quality without an independent evaluation; counts are
  counts of recorded information; previews are illustrative.

## 12. Out of scope for v3

Social-science entries; dataset submission from the app; automatic pull
requests; an expert or user evaluation study (a separate paper); hosting
datasets; per-field provenance (one block per entry is enough for now).
