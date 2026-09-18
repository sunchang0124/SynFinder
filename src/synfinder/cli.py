"""Command line entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import CatalogError, load_catalog
from .datasets import match_datasets
from .intake import Intake
from .ranking import load_weights, rank
from .report import render_html, render_markdown


def default_catalog_root() -> Path:
    return Path(__file__).resolve().parents[2] / "catalog"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="synfinder",
        description="Find a synthetic data generation method that fits your study.",
    )
    sub = p.add_subparsers(dest="command")
    f = sub.add_parser("find", help="recommend methods for your situation")
    f.add_argument("--domain", required=True)
    f.add_argument("--data-type", required=True)
    f.add_argument("--purpose", required=True)
    f.add_argument("--privacy", required=True,
                   choices=["none", "deidentified_ok", "formal_dp_required"])
    f.add_argument("--compute",
                   choices=["cpu_fine", "gpu_recommended", "gpu_required"])
    f.add_argument("--expertise", choices=["low", "medium", "high"])
    f.add_argument("--rows", type=int, dest="expected_rows")
    f.add_argument("--variable-types", nargs="*", default=[])
    f.add_argument("--preserves", nargs="*", default=[])
    f.add_argument("--open-license", action="store_true",
                   dest="require_open_license")
    f.add_argument("--governance-evidence", action="store_true",
                   dest="needs_governance_evidence")
    f.add_argument("--catalog", type=Path, default=None)
    f.add_argument("--top", type=int, default=5)
    f.add_argument("--out", type=Path, default=None,
                   help="write the report here (.md or .html)")
    f.set_defaults(func=cmd_find)

    d = sub.add_parser("datasets", help="browse ready-made synthetic datasets")
    d.add_argument("--domain")
    d.add_argument("--data-type")
    d.add_argument("--license")
    d.add_argument("--catalog", type=Path, default=None)
    d.set_defaults(func=cmd_datasets)

    n = sub.add_parser("new", help="create a catalog entry to contribute")
    n.add_argument("kind", choices=["method", "dataset"])
    n.add_argument("--catalog", type=Path, default=None)
    n.set_defaults(func=cmd_new)

    return p


def _validate_against_taxonomy(args, taxonomy: dict) -> list[str]:
    checks = [
        ("domain", args.domain, "domains"),
        ("data-type", args.data_type, "data_types"),
        ("purpose", args.purpose, "purposes"),
    ]
    errors = [
        f"'{value}' is not a known {flag}; choose from "
        f"{', '.join(taxonomy.get(key, []))}"
        for flag, value, key in checks
        if value not in taxonomy.get(key, [])
    ]
    for value in args.preserves:
        if value not in taxonomy.get("preserves", []):
            errors.append(f"'{value}' is not a known preserves value")
    for value in args.variable_types:
        if value not in taxonomy.get("variable_types", []):
            errors.append(f"'{value}' is not a known variable type")
    return errors


def cmd_find(args) -> int:
    root = args.catalog or default_catalog_root()

    try:
        catalog = load_catalog(root)
    except CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 1

    errors = _validate_against_taxonomy(args, catalog.taxonomy)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 2

    intake = Intake(
        domain=args.domain, data_type=args.data_type, purpose=args.purpose,
        privacy=args.privacy, compute=args.compute, expertise=args.expertise,
        expected_rows=args.expected_rows, variable_types=args.variable_types,
        preserves=args.preserves,
        require_open_license=args.require_open_license or None,
        needs_governance_evidence=args.needs_governance_evidence or None,
    )

    weights_path = Path(root) / "weights.yaml"
    weights = load_weights(weights_path) if weights_path.exists() else None
    ranking = rank(catalog.generation_methods(), intake, weights, top_n=args.top)

    matching = match_datasets(catalog.datasets, intake)

    covered = catalog.covers(intake.data_type)
    also = catalog.covered_data_types()

    if args.out and args.out.suffix == ".html":
        args.out.write_text(render_html(intake, ranking, matching, covered, also))
        print(f"wrote {args.out}")
        return 0

    markdown = render_markdown(intake, ranking, matching, covered, also)
    if args.out:
        args.out.write_text(markdown)
        print(f"wrote {args.out}")
    else:
        print(markdown)
    return 0


def cmd_datasets(args) -> int:
    root = args.catalog or default_catalog_root()
    try:
        catalog = load_catalog(root)
    except CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 1

    found = catalog.datasets
    if args.domain:
        found = [d for d in found
                 if args.domain in d.domains or "general" in d.domains]
    if args.data_type:
        found = [d for d in found if args.data_type in d.data_types]
    if args.license:
        found = [d for d in found if d.license == args.license]

    if not found:
        print("No dataset in the registry matches those filters.")
        return 0

    for d in found:
        print(f"{d.name}  [{d.id}]")
        print(f"  {d.n_records} · {d.license} · {d.access_conditions}")
        print(f"  domains: {', '.join(d.domains)}"
              f" | data types: {', '.join(d.data_types)}")
        if d.generated_by:
            print(f"  generated with: {d.generated_by}")
        for caveat in d.realism_caveats:
            print(f"  caveat: {caveat}")
        link = d.links.docs or d.links.code
        if link:
            print(f"  {link}")
        print()
    return 0


def cmd_new(args) -> int:
    from .contribute import new_entry

    return new_entry(args.kind, args.catalog or default_catalog_root())


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
