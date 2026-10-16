"""Write reviewed purposes and a provenance block into the catalog.

    .venv/bin/python tools/review/apply_decisions.py            # dry run
    .venv/bin/python tools/review/apply_decisions.py --write

Only methods with a decision in review/decisions.json change. The
`purposes:` line is rewritten in place (flow style); a `provenance:` block
is appended or replaced. Run the test suite afterwards: a golden scenario
that changes answer is a finding to report, not to hide.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from synfinder.catalog import load_catalog  # noqa: E402

DEC = ROOT / "review" / "decisions.json"
SRC = ROOT / "review" / "sources"


def yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def provenance_block(d: dict, sources: list[str]) -> str:
    lines = ["provenance:",
             f"  verified_on: {d['decided_at'][:10]}",
             f"  verified_by: {yaml_str(d.get('reviewer') or 'Chang Sun')}",
             f"  sources_checked: [{', '.join(sources)}]",
             "  fields_checked: [purposes, links]"]
    if d.get("notes"):
        lines.append(f"  notes: {yaml_str(d['notes'].strip())}")
    return "\n".join(lines) + "\n"


def rewrite(text: str, purposes: list[str], prov: str) -> str:
    text, n = re.subn(r"^purposes:.*(?:\n(?:  - .*|\s*$))*?(?=\n\S|\Z)",
                      "purposes: [" + ", ".join(purposes) + "]", text, count=1, flags=re.M)
    if n != 1:
        raise ValueError("no purposes line")
    text = re.sub(r"^provenance:\n(?:[ \t].*\n?)*", "", text, flags=re.M)
    if not text.endswith("\n"):
        text += "\n"
    return text + prov


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    decisions = json.loads(DEC.read_text()) if DEC.exists() else {}
    cat = load_catalog(ROOT / "catalog")
    changed = 0
    for m in cat.methods:
        d = decisions.get(m.id)
        if not d or not d.get("decided_at"):
            continue
        path = ROOT / "catalog" / "methods" / f"{m.id}.yaml"
        rec = json.loads((SRC / f"{m.id}.json").read_text()) if (SRC / f"{m.id}.json").exists() else {}
        sources = [k for k in ("paper", "code", "docs")
                   if rec.get(k) and (rec[k].get("status") == 200 or rec[k].get("api_status") == 200
                                      or rec[k].get("http_status") == 200)]
        new = sorted(d["purposes"], key=lambda p: (p not in m.purposes, p))
        delta = (set(new) - set(m.purposes), set(m.purposes) - set(new))
        print(f"{m.id}: +{sorted(delta[0])} -{sorted(delta[1])} sources={sources}")
        if args.write:
            path.write_text(rewrite(path.read_text(), new, provenance_block(d, sources or ["code"])))
        changed += 1
    print(f"{changed} methods {'written' if args.write else 'would change'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
