"""Command line entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import CatalogError, load_catalog
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
    p.add_argument("--domain", required=True)
    p.add_argument("--data-type", required=True)
    p.add_argument("--purpose", required=True)
    p.add_argument("--privacy", required=True,
                   choices=["none", "deidentified_ok", "formal_dp_required"])
    p.add_argument("--compute",
                   choices=["cpu_fine", "gpu_recommended", "gpu_required"])
    p.add_argument("--expertise", choices=["low", "medium", "high"])
    p.add_argument("--rows", type=int, dest="expected_rows")
    p.add_argument("--variable-types", nargs="*", default=[])
    p.add_argument("--preserves", nargs="*", default=[])
    p.add_argument("--open-license", action="store_true",
                   dest="require_open_license")
    p.add_argument("--governance-evidence", action="store_true",
                   dest="needs_governance_evidence")
    p.add_argument("--catalog", type=Path, default=None)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--out", type=Path, default=None,
                   help="write the report here (.md or .html)")
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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
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

    matching = [
        d for d in catalog.datasets
        if d.domain in (intake.domain, "general")
        and d.data_type == intake.data_type
    ]

    covered = catalog.covers(intake.data_type)

    if args.out and args.out.suffix == ".html":
        args.out.write_text(render_html(intake, ranking, matching, covered))
        print(f"wrote {args.out}")
        return 0

    markdown = render_markdown(intake, ranking, matching, covered)
    if args.out:
        args.out.write_text(markdown)
        print(f"wrote {args.out}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
