"""Trim review/sources/<id>.json into a readable review/sources/<id>.txt.

Everything in the digest is a verbatim substring of the JSON sources, so a
quote taken from the digest verifies against the full record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "review" / "sources"
FULL, README, DOCS = 32_000, 14_000, 6_000


def digest(mid: str) -> str:
    r = json.loads((SRC / f"{mid}.json").read_text())
    p, c, d = r.get("paper") or {}, r.get("code") or {}, r.get("docs") or {}
    s2 = p.get("s2") or {}
    out = [f"# {r['name']}  (id: {mid})", f"Current purposes in catalog: {', '.join(r['purposes_current'])}", ""]
    out += ["## PAPER", f"URL: {p.get('url')}", f"Title: {p.get('title')}", f"Year: {p.get('year')}", ""]
    if p.get("abstract"):
        out += ["### Abstract (source: paper)", p["abstract"], ""]
    elif s2.get("abstract"):
        out += ["### Abstract via Semantic Scholar (source: paper)", s2["abstract"], ""]
    if s2.get("tldr"):
        out += ["### TLDR (source: paper)", s2["tldr"], ""]
    if p.get("fulltext"):
        out += [f"### Full text, first {FULL} characters (source: paper)", p["fulltext"][:FULL], ""]
    else:
        out += ["### Full text: NOT AVAILABLE (paywalled or no PDF)", ""]
    out += ["## CODE", f"URL: {c.get('url')}", f"Repo: {c.get('full_name') or c.get('final_url')}", f"Description: {c.get('description')}", ""]
    if c.get("readme"):
        out += [f"### README, first {README} characters (source: readme)", c["readme"][:README], ""]
    elif c.get("text"):
        out += ["### Page text (source: readme)", c["text"][:README], ""]
    else:
        out += ["### README: NOT AVAILABLE", ""]
    if d:
        out += ["## DOCS", f"URL: {d.get('url')}", ""]
        txt = d.get("readme") or d.get("text")
        if txt and d.get("url") != c.get("url"):
            out += [f"### Docs text, first {DOCS} characters (source: docs)", txt[:DOCS], ""]
    return "\n".join(out)


def main() -> int:
    ids = sys.argv[1:] or sorted(p.stem for p in SRC.glob("*.json"))
    for mid in ids:
        (SRC / f"{mid}.txt").write_text(digest(mid))
    print(f"{len(ids)} digests written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
