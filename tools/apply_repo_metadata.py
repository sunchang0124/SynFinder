"""Write the mechanical repository facts into the catalog.

Only five fields: license, language, last_updated, maturity.maintained,
maturity.last_pushed.
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
from synfinder.schema import Method  # noqa: E402
from synfinder.repometa import (drift, is_maintained, load_metadata,  # noqa: E402
                                map_language, normalise_license, rewrite_fields)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    meta_all = load_metadata(ROOT / "catalog" / "repo_metadata.json")
    fetched = meta_all["fetched_at"]
    catalog = load_catalog(ROOT / "catalog")
    method_ids = {m.id for m in catalog.methods}
    changed = 0
    for entry in catalog.methods + catalog.datasets:
        meta = meta_all["entries"].get(entry.id)
        if meta is None or not drift(entry, meta, fetched):
            continue
        sub = "methods" if entry.id in method_ids else "datasets"
        path = ROOT / "catalog" / sub / f"{entry.id}.yaml"
        updates: dict[str, str] = {}
        lic = normalise_license(meta.get("license_spdx"))
        if isinstance(entry, Method) and lic and normalise_license(entry.license) != lic:
            updates["license"] = lic
        lang = map_language(meta.get("language"))
        cur_lang = getattr(entry, "language", None)
        if lang and cur_lang and cur_lang not in (lang, "multiple"):
            updates["language"] = lang
        if meta.get("pushed_at"):
            year = meta["pushed_at"][:4]
            cur_year = getattr(entry, "last_updated", None)
            if cur_year is not None and str(cur_year) != year:
                updates["last_updated"] = year
            if hasattr(entry, "maturity"):
                if entry.maturity.last_pushed != meta["pushed_at"][:10]:
                    updates["maturity.last_pushed"] = meta["pushed_at"][:10]
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
