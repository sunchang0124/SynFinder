# SynFinder

Find the synthetic data generation method that fits your study — with the
caveats that will actually bite you.

Answer four questions (research domain, what your real data looks like, what
the synthetic data is for, and your privacy requirement) and SynFinder returns
a ranked shortlist of methods, each with a rationale, its honest failure modes,
and how to check the output was any good. It also tells you what it ruled out
and why.

Built for health, clinical and biomedical researchers first. Social sciences
and humanities are next, and will arrive as catalog entries rather than as new
code.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -e ".[app,dev]"
```

## Use it

Command line:

```bash
# recommend methods for your situation
synfinder find --domain biomedical \
               --data-type tabular_cross_sectional \
               --purpose open_release \
               --privacy formal_dp_required \
               --out recommendation.md

# browse ready-made synthetic datasets - you may not need to generate anything
synfinder datasets --domain biomedical

# create a catalog entry to contribute
synfinder new method
```

The bare `synfinder --domain ...` form was replaced by `synfinder find` in v2.

App:

```bash
streamlit run app/streamlit_app.py
```

**No API key is required.** Ranking, rationales, the comparison table and the
exported report are all produced from the catalog with no network call. If an
`ANTHROPIC_API_KEY` is present, an LLM rewrites the rationale into fluent
prose — it cannot add a claim that is not already in the catalog.

## Ready-made datasets come first

When a synthetic dataset already exists that matches what you described, it is
shown **above** the method shortlist. Using one costs nothing and avoids every
risk of training your own. Browse the registry with `synfinder datasets` or
the app's second tab.

## What the output looks like

Every method carries a preview of the shape it emits — a CSV header for
tabular methods, a visit-and-code nesting for EHR, a genotype matrix for
genomic, a written specification for imaging. These illustrate the **format**;
they are not real generated output, and the tool says so above every one.

## How it decides

1. **Hard filters** eliminate methods that cannot serve you at all — wrong data
   type, no formal DP when you need it, needs a GPU you do not have. Every
   exclusion records its reason and is shown to you.
2. **A weighted score** over the axes you answered: purpose, what must be
   preserved, scale, expertise, maturity, governance. Weights live in
   `catalog/weights.yaml`.
3. **Questions you skip are dropped** from the average entirely — they never
   count against a method as a zero.

## Adding a catalog entry

Copy an existing file in `catalog/methods/`, fill it in, then:

```bash
pytest tests/test_catalog_integrity.py tests/test_golden_scenarios.py
```

Controlled fields must draw their values from `catalog/taxonomy.yaml`; the
loader fails loudly otherwise. Every entry needs at least one `caveat` — an
entry with no honest failure mode has not really been reviewed.

## Layout

| Path | What it is |
|---|---|
| `catalog/taxonomy.yaml` | controlled vocabulary, the single source of truth |
| `catalog/methods/*.yaml` | one file per method |
| `catalog/datasets/*.yaml` | ready-made synthetic datasets |
| `catalog/weights.yaml` | scoring weights |
| `src/synfinder/` | schema, loader, intake, ranking, explanations, report, CLI |
| `app/streamlit_app.py` | the app |
| `docs/superpowers/specs/` | the design |

## Tests

```bash
pytest
```

`tests/test_golden_scenarios.py` holds fixed intakes with known-correct
answers. If one fails after a weight change, the test is usually right and the
weights are wrong.

## Contributing

Anyone can add a method or a dataset. The fastest route:

```bash
synfinder new method      # writes a valid entry, refuses invalid terms
pytest
```

then open a pull request with the one new file. If you would rather not use
git, open an issue with the **Submit a method** or **Submit a dataset** form.

CI runs the full test suite on every pull request with no API key set, so a
submission that breaks the schema, the taxonomy or a golden scenario cannot
merge unnoticed.

Read [CONTRIBUTING.md](CONTRIBUTING.md) first. The short version: declare it
if you authored the method, write caveats that name real failure modes, and
cite a source for any numeric claim.
