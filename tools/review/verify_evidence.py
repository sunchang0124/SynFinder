"""Reject any evidence quote that is not in the fetched sources.

    .venv/bin/python tools/review/verify_evidence.py          # all
    .venv/bin/python tools/review/verify_evidence.py ctgan    # one

Marks each quote `verified: true|false` in review/evidence/<id>.json and
downgrades a `supported` verdict with no verified quote to `unclear`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "review" / "sources"
EVD = ROOT / "review" / "evidence"


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("ﬁ", "fi").replace("ﬂ", "fl")
    # Compare letters and digits only: PDF hyphenation, line breaks, curly
    # quotes and spacing all vanish, so a real quote survives extraction noise.
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def source_texts(rec: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    p = rec.get("paper") or {}
    out["paper"] = norm(" ".join(filter(None, [p.get("title"), p.get("abstract"),
                                               (p.get("s2") or {}).get("abstract"),
                                               (p.get("s2") or {}).get("tldr"),
                                               p.get("fulltext")])))
    c = rec.get("code") or {}
    out["readme"] = norm(" ".join(filter(None, [c.get("description"), c.get("readme"), c.get("text")])))
    d = rec.get("docs") or {}
    out["docs"] = norm(" ".join(filter(None, [d.get("description"), d.get("readme"), d.get("text"), d.get("title")])))
    return out


def verify(mid: str) -> tuple[int, int]:
    ev = json.loads((EVD / f"{mid}.json").read_text())
    rec = json.loads((SRC / f"{mid}.json").read_text())
    texts = source_texts(rec)
    ok = bad = 0
    for purpose, block in ev.get("purposes", {}).items():
        good = 0
        for q in block.get("quotes", []):
            hay = texts.get(q.get("source", ""), "")
            found = bool(q.get("text")) and norm(q["text"]) in hay
            q["verified"] = found
            ok += found; bad += not found; good += found
        if block.get("verdict") == "supported" and not good:
            block["verdict"] = "unclear"
            block["rationale"] = "(downgraded: no quote could be verified against the fetched sources) " + block.get("rationale", "")
    (EVD / f"{mid}.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False))
    return ok, bad


def main() -> int:
    ids = sys.argv[1:] or sorted(p.stem for p in EVD.glob("*.json"))
    tot_ok = tot_bad = 0
    for mid in ids:
        ok, bad = verify(mid)
        tot_ok += ok; tot_bad += bad
        print(f"{mid}: {ok} verified, {bad} rejected")
    print(f"total: {tot_ok} verified, {tot_bad} rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
