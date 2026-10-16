# Purpose review

Chang reviews each method's `purposes` against evidence from its own paper
and repository. The tools collect and record; they never decide.

```
.venv/bin/python tools/review/fetch_sources.py      # links + sources -> review/sources/, review/links.md
.venv/bin/python tools/review/digest.py             # readable per-method digests (review/sources/<id>.txt)
# evidence files review/evidence/<id>.json are written by a reader of the digests
.venv/bin/python tools/review/verify_evidence.py    # drop any quote not found verbatim in the sources
.venv/bin/python tools/review/app.py                # http://localhost:8600 — tick purposes, save
.venv/bin/python tools/review/apply_decisions.py --write   # purposes + provenance into catalog/methods/*.yaml
.venv/bin/python -m pytest -q                       # golden scenarios may change answer: report it
```

In the app: tick or untick each purpose, add a note if you want it in the
provenance block, confirm the links, then **Save and next** (⌘⏎). Decisions
are kept in `review/decisions.json`; closing the page loses nothing.
Label meanings are in `PURPOSES.md` and under "What the labels mean" on the page.
