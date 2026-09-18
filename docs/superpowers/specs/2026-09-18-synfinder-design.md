# SynFinder — design

**Date:** 2026-09-18
**Status:** approved design, no code yet
**Author:** Chang Sun (with Claude)

## 1. Problem

Researchers who need synthetic data cannot tell which generation method fits
their situation. The literature is large, the method names say little about
applicability, and the failure modes are learned only by running the methods.
The judgement that separates a good choice from a bad one currently lives in
the heads of a few people.

SynFinder encodes that judgement as a reviewed catalog and a deterministic
ranking engine: a researcher answers a short intake and gets a ranked shortlist
of methods (and ready-made synthetic datasets), each with a rationale, the
caveats that will actually bite them, and how to evaluate the result.

## 2. Users, in build order

1. **v1 — health / clinical / biomedical researchers.** The catalog ships
   biomedical methods only.
2. **v2 — social science and humanities researchers.** Added as catalog data,
   not as new code.
3. **later — other domains.**

Domain is a first-class field from day one so that (2) requires no schema
migration.

## 3. Design decisions (settled)

| Decision | Choice |
|---|---|
| Knowledge source | Curated catalog decides; LLM only narrates |
| Domain handling | First-class `domains` field on every entry |
| Ranking | Hard filters, then weighted score |
| LLM | Optional enrichment; app is fully functional with no API key |
| Form | Python package + Streamlit app |
| Catalog format | One YAML file per method, validated by pydantic |
| Datasets in scope | Ready-made synthetic datasets, not just public seed data |

## 4. Architecture

The product is a reviewable data file set plus a small deterministic engine.
Review happens on YAML, not Python.

```
SynFinder/
├── catalog/
│   ├── taxonomy.yaml          controlled vocabulary — single source of truth
│   ├── weights.yaml           scoring weights, tunable without code changes
│   ├── methods/*.yaml         one file per method (~25–35 in v1)
│   └── datasets/*.yaml        ready-made synthetic datasets
├── src/synfinder/
│   ├── schema.py     pydantic models; taxonomy terms become enums
│   ├── catalog.py    load, validate, query
│   ├── intake.py     answer model (core four + three optional blocks)
│   ├── ranking.py    hard filters → weighted score → per-axis breakdown
│   ├── explain.py    template rationale assembled from the breakdown
│   ├── llm.py        optional enrichment; no-op without a key
│   ├── report.py     markdown + HTML export
│   └── cli.py
├── app/streamlit_app.py
└── tests/
```

One method per file is deliberate: adding an SSH method later, or correcting a
claim about dp-cgans, is a one-file diff reviewable in a minute. A schema test
fails loudly if any file drifts from the taxonomy.

## 5. Method schema

Fields are grouped by what the engine does with them.

### 5.1 Hard-filter fields — can eliminate a candidate outright

- `domains` — biomedical | ssh | general
- `data_types` — tabular cross-sectional, tabular longitudinal, coded event
  sequences (EHR), time series, survival, survey instruments, text, images,
  graph/network
- `variable_types` — continuous, categorical, ordinal, count, datetime,
  free text
- `formal_dp` — boolean, plus `dp_mechanism` when true
- `compute` — cpu_fine | gpu_recommended | gpu_required
- `license`

### 5.2 Scored fields — weighted match, each contributing a visible sub-score

- `purposes` — open release, code/pipeline testing, ML augmentation,
  statistical replication, causal inference, education, method benchmarking,
  class imbalance correction
- `preserves` — marginals, joint correlations, temporal dynamics, causal
  structure, rare events / tails
- `scale` — practical row and column ranges
- `expertise` — low | medium | high
- `maturity` — maintained, last release, implementation quality
- `governance` — ethics/regulator acceptance evidence, known deployments

### 5.3 Narrative fields — never scored, always shown

- `caveats` — honest failure modes, stated concretely
- `evaluation` — which metrics and tools validate *this* method
- `links` — paper DOI, code repository, documentation
- `related_datasets` — ids from the dataset catalog

The narrative fields are what make the catalog worth more than a literature
list. Example of the intended register: *"TimeAutoDiff assumes regular sampling
intervals; irregular EHR visit spacing breaks it."*

### 5.4 Dataset schema (thinner)

`domain`, `data_type`, `size`, `generated_by` (method id), `access_conditions`,
`license`, `realism_caveats`, `links`.

## 6. Intake

**Core four, required:** domain · data type · primary purpose · privacy and
sharing requirement.

**Optional refinement blocks:** constraints and resources · fidelity and
evaluation needs · governance and acceptance.

## 7. Ranking

1. **Hard filters.** Every eliminated method records *why*. The app surfaces
   this: "18 methods ruled out — 11 cannot handle irregular longitudinal data,
   5 have no formal DP, 2 require a GPU you said you do not have." Exclusions
   are as informative as the shortlist and are the fastest way to spot a wrong
   catalog field.
2. **Weighted score.** Each scored axis yields a sub-score in [0,1], multiplied
   by its weight from `weights.yaml`; fit is the weighted mean.
3. **Skipped questions do not penalize.** An optional axis left blank is
   dropped from both numerator and denominator — never scored as zero.
4. **Ties** break on `maturity`.
5. **Output** is the top 3–5 plus the ruled-out list with reasons.

## 8. Explanation

The rationale is assembled from the score breakdown, not written freehand:

- *why it fits* — the top contributing axes
- *where it is weak* — the lowest-scoring axis
- *what will bite you* — the `caveats` field, verbatim
- *how to check it worked* — the `evaluation` field

When an API key is present, the LLM rewrites this into prose. It cannot add a
claim that is not already in the catalog. Without a key, the template text is
shown as-is and every feature still works.

## 9. Output surface

- Ranked cards: fit score, rationale, paper and code links
- Comparison table of the shortlist across the scored axes
- Ruled-out panel with reasons
- Matching ready-made synthetic datasets
- One-click markdown / HTML report

The report is the distribution mechanism: it is written to be pasted into a
data management plan or an ethics application, which is how the tool reaches
people who never open the app.

## 10. v1 catalog

Biomedical only, ~25–35 methods, drafted by Claude in batches of roughly eight
and reviewed by Chang before entry. Nothing enters the catalog unreviewed.

Candidate list (final set decided during drafting):

*Tabular cross-sectional:* CTGAN, TVAE, CopulaGAN, Gaussian Copula (SDV),
metasyn, synthpop, Bayesian networks (pgmpy/bnlearn), dp-cgans, PATE-GAN,
DP-CTGAN, PrivBayes, MST/AIM, TabDDPM, TabSyn, GReaT, rule-based expert
simulation, SMOTE-family (as a labelled contrast, not a recommendation).

*Longitudinal and EHR:* Synthea, HALO, medGAN, EVA, SynTEG, PromptEHR,
EHR-Safe, CorGAN.

*Time series and survival:* TimeAutoDiff, DoppelGANger, TimeGAN, RTSGAN,
SurvivalGAN.

*Toolkits* (catalogued as frameworks, not ranked as methods): SDV, synthcity.

Medical imaging and clinical free-text methods are deferred to v1.1.

## 11. Testing

- **Schema validation** — every YAML file validates against the pydantic model
  and the taxonomy; no free-text drift in controlled fields.
- **Golden scenarios** — fixed intakes with asserted outcomes, e.g.
  "longitudinal EHR + open release + formal DP required" asserts an expected
  method appears in the top three and an unsuitable one is excluded. These
  catch ranking regressions when weights change.
- **Engine unit tests** — hard-filter elimination reasons, weighted-mean
  arithmetic, the skipped-axis rule, tie-breaking.

## 12. Out of scope for v1

User accounts; a hosted public deployment; SSH catalog entries; automated
paper ingestion or literature scraping; imaging and free-text methods.

## 13. Open questions

None blocking. Weight values in `weights.yaml` start at sensible defaults and
are tuned against the golden scenarios during catalog drafting.
