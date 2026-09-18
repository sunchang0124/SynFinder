"""Load and validate the YAML catalog."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from .schema import Dataset, Method

# catalog field -> taxonomy key it must draw from
CONTROLLED: dict[str, str] = {
    "domains": "domains",
    "data_types": "data_types",
    "variable_types": "variable_types",
    "compute": "compute",
    "expertise": "expertise",
    "purposes": "purposes",
    "preserves": "preserves",
    "family": "families",
}


class CatalogError(Exception):
    """A catalog file is malformed or uses a term outside the taxonomy."""


@dataclass
class Catalog:
    methods: list[Method] = field(default_factory=list)
    datasets: list[Dataset] = field(default_factory=list)
    taxonomy: dict[str, list[str]] = field(default_factory=dict)

    def generation_methods(self) -> list[Method]:
        return [m for m in self.methods if not m.is_framework]

    def frameworks(self) -> list[Method]:
        return [m for m in self.methods if m.is_framework]

    def by_id(self, method_id: str) -> Method | None:
        return next((m for m in self.methods if m.id == method_id), None)


def load_taxonomy(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        raise CatalogError(f"taxonomy file not found: {path}")
    return yaml.safe_load(path.read_text())


def _check_terms(entry: dict, taxonomy: dict[str, list[str]], source: Path) -> None:
    for field_name, tax_key in CONTROLLED.items():
        if field_name not in entry:
            continue
        allowed = set(taxonomy.get(tax_key, []))
        raw = entry[field_name]
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            if value not in allowed:
                raise CatalogError(
                    f"{source.name}: '{value}' is not a permitted value for "
                    f"'{field_name}'; taxonomy key '{tax_key}' allows "
                    f"{sorted(allowed)}"
                )
    quality = (entry.get("maturity") or {}).get("implementation_quality")
    if quality is not None and quality not in set(
        taxonomy.get("implementation_quality", [])
    ):
        raise CatalogError(
            f"{source.name}: '{quality}' is not a permitted implementation_quality"
        )


def load_catalog(root: Path) -> Catalog:
    root = Path(root)
    taxonomy = load_taxonomy(root / "taxonomy.yaml")
    catalog = Catalog(taxonomy=taxonomy)

    seen: dict[str, Path] = {}
    for path in sorted((root / "methods").glob("*.yaml")):
        entry = yaml.safe_load(path.read_text())
        _check_terms(entry, taxonomy, path)
        try:
            method = Method(**entry)
        except ValidationError as exc:
            raise CatalogError(f"{path.name}: {exc}") from exc
        if method.id in seen:
            raise CatalogError(
                f"duplicate method id '{method.id}' in {path.name} "
                f"and {seen[method.id].name}"
            )
        seen[method.id] = path
        catalog.methods.append(method)

    datasets_dir = root / "datasets"
    if datasets_dir.exists():
        for path in sorted(datasets_dir.glob("*.yaml")):
            entry = yaml.safe_load(path.read_text())
            try:
                catalog.datasets.append(Dataset(**entry))
            except ValidationError as exc:
                raise CatalogError(f"{path.name}: {exc}") from exc

    return catalog
