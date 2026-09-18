# Contributing to SynFinder

The live app: <https://sunchang0124.github.io/SynFinder/>

Thank you for wanting to add to this catalog.

## What this catalog is for

SynFinder helps researchers choose a synthetic data generation method. It is
useful only because its entries are honest about what goes wrong. A catalog
of methods that all sound good is a catalog nobody needs.

That makes the `caveats` field the most important thing you will write, and
the thing a maintainer will read hardest.

## Three rules

1. **Declare authorship.** If you wrote the method you are adding, say so in
   the pull request. This is not disqualifying. Concealing it is.
2. **Caveats must name real failure modes.** This catalog exists because its
   entries say what goes wrong. "Requires tuning" is not a caveat.
   "High-cardinality categoricals destabilise training and rare categories
   are dropped entirely" is a caveat. An entry whose caveats read as
   marketing will be rejected.
3. **Claims need sources.** Scale bounds require an `evidence` line citing
   the paper table or repository example they come from — the schema
   enforces this. Release dates come from the repository, never from memory.

## Adding an entry

The generator writes a valid file for you and refuses any term outside the
taxonomy:

```bash
pip install -e ".[dev]"
synfinder new method      # or: synfinder new dataset
pytest
```

Then open a pull request with the one new file. CI runs the full test suite
on every pull request, with no API key set, so a submission that breaks the
schema, the taxonomy or a golden scenario cannot merge unnoticed.

If you would rather not use git, open an issue with the **Submit a method**
or **Submit a dataset** form and a maintainer will turn it into a pull
request.

## Maintainer review checklist

These fields silently change what gets recommended. Check each against the
paper or the repository, not against the submission text:

- `data_types` — a wrong value makes the method appear for the wrong studies
- `formal_dp` — a false positive here is a privacy claim the method cannot meet
- `requires_no_source_data` — only true if the method never ingests real records
- `compute` — a wrong value hides the method from users who could run it
- `purposes` — the most heavily weighted axis in ranking
- `caveats` — the reason anyone trusts this catalog
- `output_preview` — must show the shape the method really emits; `image_spec`
  entries carry a written specification, never image data

## A note on output previews

Previews illustrate the *format* a method emits. They are not real generated
output, and the tool says so above every one. Do not submit a preview
presented as genuine model output.
