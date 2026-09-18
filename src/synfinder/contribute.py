"""Generate a valid catalog entry, so a contributor cannot write an invalid one."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from .catalog import load_catalog
from .schema import Dataset, Method

# field on the entry -> taxonomy key it must draw from
CONTROLLED = {
    "domains": "domains", "data_types": "data_types",
    "variable_types": "variable_types", "purposes": "purposes",
    "preserves": "preserves", "compute": "compute",
    "expertise": "expertise", "family": "families",
}


def build_method(a: dict) -> dict:
    return {
        "id": a["id"], "name": a["name"], "family": a["family"],
        "domains": a["domains"], "data_types": a["data_types"],
        "variable_types": a["variable_types"],
        "formal_dp": a["formal_dp"],
        "dp_mechanism": a.get("dp_mechanism"),
        "compute": a["compute"], "license": a["license"],
        "purposes": a["purposes"], "preserves": a["preserves"],
        "scale": {"evidence": None},
        "expertise": a["expertise"],
        "maturity": {
            "maintained": a["maintained"],
            "last_release": a.get("last_release"),
            "implementation_quality": a["implementation_quality"],
        },
        "governance": {
            "acceptance_evidence": a.get("acceptance_evidence", []),
            "known_deployments": a.get("known_deployments", []),
        },
        "caveats": a["caveats"],
        "evaluation": a.get("evaluation", []),
        "links": {"paper": a.get("paper"), "code": a.get("code"),
                  "docs": a.get("docs")},
        "related_datasets": [],
        "output_preview": {
            "format": a["preview_format"],
            "note": a["preview_note"],
            "preview": a["preview_body"],
        },
    }


def build_dataset(a: dict) -> dict:
    return {
        "id": a["id"], "name": a["name"], "domains": a["domains"],
        "data_types": a["data_types"], "purposes": a.get("purposes", []),
        "n_records": a["n_records"], "formal_dp": a.get("formal_dp", False),
        "dp_mechanism": a.get("dp_mechanism"),
        "generated_by": a.get("generated_by"),
        "access_conditions": a["access_conditions"], "license": a["license"],
        "realism_caveats": a["realism_caveats"],
        "links": {"paper": a.get("paper"), "code": a.get("code"),
                  "docs": a.get("docs")},
    }


def _collect(label: str) -> list[str]:
    items: list[str] = []
    while True:
        value = input(f"  {label} (blank to finish): ").strip()
        if not value:
            return items
        items.append(value)


def _ask(prompt: str, options: list[str] | None = None,
         multi: bool = False):
    if options:
        print(f"\n{prompt}")
        for i, o in enumerate(options, 1):
            print(f"  {i}. {o}")
        raw = input("choose number(s), comma separated: " if multi
                    else "choose a number: ").strip()
        picks = [options[int(x) - 1] for x in raw.split(",") if x.strip()]
        return picks if multi else picks[0]
    return input(f"{prompt}: ").strip()


def _interview(kind: str, tax: dict) -> dict:
    """Ask the questions, constraining every controlled answer."""
    a: dict = {"id": _ask("id (lowercase, no spaces)"),
               "name": _ask("display name")}
    a["domains"] = _ask("domains", tax["domains"], multi=True)
    a["data_types"] = _ask("data types", tax["data_types"], multi=True)
    a["license"] = _ask("licence (e.g. MIT)")
    if kind == "method":
        a["family"] = _ask("family", tax["families"])
        a["variable_types"] = _ask("variable types", tax["variable_types"],
                                   multi=True)
        a["formal_dp"] = _ask("formal differential privacy?",
                              ["no", "yes"]) == "yes"
        if a["formal_dp"]:
            a["dp_mechanism"] = _ask("dp mechanism, one line")
        a["compute"] = _ask("compute", tax["compute"])
        a["purposes"] = _ask("purposes", tax["purposes"], multi=True)
        a["preserves"] = _ask("preserves", tax["preserves"], multi=True)
        a["expertise"] = _ask("expertise needed", tax["expertise"])
        a["maintained"] = _ask("actively maintained?", ["no", "yes"]) == "yes"
        a["implementation_quality"] = _ask("implementation quality",
                                           tax["implementation_quality"])
        print("\nCaveats are the point of this catalog. Name real failure "
              "modes, not marketing. Blank line to finish.")
        a["caveats"] = _collect("caveat")
        a["evaluation"] = _collect("evaluation step")
        a["preview_format"] = _ask("output preview format",
                                   tax["preview_formats"])
        a["preview_note"] = _ask("one line describing the output")
        print("Paste a few lines illustrating the output. Blank to finish.")
        a["preview_body"] = "\n".join(_collect("line"))
    else:
        a["purposes"] = _ask("purposes", tax["purposes"], multi=True)
        a["n_records"] = _ask("size, e.g. '1,000 patients'")
        a["access_conditions"] = _ask("how does someone get it")
        a["generated_by"] = _ask(
            "method id it was generated with (blank if none)") or None
        print("\nRealism caveats. Blank line to finish.")
        a["realism_caveats"] = _collect("caveat")
    a["paper"] = _ask("paper DOI or URL (blank if none)") or None
    a["code"] = _ask("code URL (blank if none)") or None
    return a


def new_entry(kind: str, catalog_root: Path, answers: dict | None = None,
              out_dir: Path | None = None) -> int:
    catalog = load_catalog(catalog_root)
    a = answers if answers is not None else _interview(kind, catalog.taxonomy)

    build = build_method if kind == "method" else build_dataset
    model = Method if kind == "method" else Dataset
    entry = build(a)

    for field, key in CONTROLLED.items():
        value = entry.get(field)
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        for v in values:
            if v not in catalog.taxonomy.get(key, []):
                print(f"'{v}' is not a permitted {field}", file=sys.stderr)
                return 1

    try:
        model(**entry)
    except ValidationError as exc:
        print(f"that entry is not valid:\n{exc}", file=sys.stderr)
        return 1

    target_dir = out_dir or (
        Path(catalog_root) / ("methods" if kind == "method" else "datasets")
    )
    target = Path(target_dir) / f"{entry['id']}.yaml"
    target.write_text(yaml.safe_dump(entry, sort_keys=False, width=78,
                                     allow_unicode=True))
    print(f"\nwrote {target}")
    print("Now: run pytest, then open a pull request. If you authored this "
          "method, say so in the pull request.")
    return 0
