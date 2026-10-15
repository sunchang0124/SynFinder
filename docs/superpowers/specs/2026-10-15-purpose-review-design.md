# Purpose review: design

Chang reviews the `purposes` field of every method, including the three toolkits (SDV, synthcity, medigan), herself. The
tooling's job is to put the evidence in front of her and write her
decisions back into the catalog with a provenance block. Nothing here
decides a purpose; it only collects, shows, and records.

## Pieces

1. `tools/review/fetch_sources.py` — for every method and dataset, check
   each link (`paper`, `code`, `docs`): follow redirects, record status and
   final URL; resolve DOIs through Crossref and arXiv, OpenReview through its
   API, PMLR/NeurIPS pages through their HTML, GitHub repos through the API
   (exists, renamed, archived, description) plus the README; fetch open
   access PDFs (arXiv, PMLR, OpenReview, NeurIPS, Semantic Scholar
   open-access link) and extract text with `pdftotext`. Writes
   `review/sources/<id>.json` (git-ignored, large) and
   `review/links.md`, a table of link status and fetched paper title next
   to the method name, for a human to spot a wrong link.
2. Evidence extraction — one JSON per method in `review/evidence/<id>.json`:
   for each of the eight taxonomy purposes, a verdict
   (`supported` / `not_supported` / `unclear`), one to three verbatim quotes
   with their source (`paper` or `readme`), and a one-sentence rationale.
   Produced by reading the fetched sources, never from memory.
   `tools/review/verify_evidence.py` rejects any quote that is not a
   substring (whitespace-normalised) of the fetched text, so no quote can
   be invented.
3. `tools/review/app.py` — a local page (`http://localhost:8600`) listing
   every method with its current purposes as checkboxes, the evidence per
   purpose, the link-check result, and a notes box. Saving writes
   `review/decisions.json`; progress survives restarts. No account, no
   network, nothing leaves the machine.
4. `tools/review/apply_decisions.py` — writes each reviewed method's
   `purposes` back into its YAML file in place (flow style preserved) and
   adds or replaces a `provenance` block: `verified_on` = decision date,
   `verified_by` = reviewer name, `sources_checked` = the link kinds that
   resolved, `fields_checked: [purposes, links]`, `notes` from the review.
   Golden-scenario tests run afterwards; a changed answer is reported, not
   hidden.

## Out of scope

Other fields (data types, scale, governance) are not reviewed here; the
same app can be extended later. Frameworks and datasets get their links
checked but not their purposes reviewed.
