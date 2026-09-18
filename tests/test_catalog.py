from pathlib import Path
import pytest
import yaml
from synfinder.catalog import load_catalog, CatalogError

TAXONOMY = {
    "domains": ["biomedical", "general"],
    "data_types": ["tabular_cross_sectional"],
    "variable_types": ["continuous", "categorical"],
    "compute": ["cpu_fine", "gpu_recommended", "gpu_required"],
    "expertise": ["low", "medium", "high"],
    "implementation_quality": ["research_code", "production_ready"],
    "purposes": ["ml_augmentation", "open_release"],
    "preserves": ["marginals", "joint_correlations"],
    "families": ["gan", "toolkit"],
}

ENTRY = {
    "id": "ctgan", "name": "CTGAN", "family": "gan",
    "domains": ["general"], "data_types": ["tabular_cross_sectional"],
    "variable_types": ["continuous", "categorical"],
    "formal_dp": False, "compute": "gpu_recommended", "license": "MIT",
    "purposes": ["ml_augmentation"], "preserves": ["joint_correlations"],
    "scale": {"min_rows": 1000, "max_rows": 1000000, "max_cols": 200},
    "expertise": "medium",
    "maturity": {"maintained": True, "last_release": "2024-06",
                 "implementation_quality": "production_ready"},
    "caveats": ["Struggles with high-cardinality categoricals."],
}


def build(tmp_path: Path, entry: dict) -> Path:
    (tmp_path / "methods").mkdir()
    (tmp_path / "datasets").mkdir()
    (tmp_path / "taxonomy.yaml").write_text(yaml.safe_dump(TAXONOMY))
    (tmp_path / "methods" / f"{entry['id']}.yaml").write_text(yaml.safe_dump(entry))
    return tmp_path


def test_loads_a_valid_method(tmp_path):
    cat = load_catalog(build(tmp_path, ENTRY))
    assert [m.id for m in cat.methods] == ["ctgan"]


def test_rejects_a_term_missing_from_the_taxonomy(tmp_path):
    bad = dict(ENTRY, purposes=["time_travel"])
    with pytest.raises(CatalogError) as exc:
        load_catalog(build(tmp_path, bad))
    assert "time_travel" in str(exc.value)
    assert "purposes" in str(exc.value)


def test_frameworks_are_separated_from_generation_methods(tmp_path):
    root = build(tmp_path, ENTRY)
    sdv = dict(ENTRY, id="sdv", name="SDV", family="toolkit", is_framework=True)
    (root / "methods" / "sdv.yaml").write_text(yaml.safe_dump(sdv))
    cat = load_catalog(root)
    assert [m.id for m in cat.generation_methods()] == ["ctgan"]
    assert [m.id for m in cat.frameworks()] == ["sdv"]


def test_duplicate_ids_are_rejected(tmp_path):
    root = build(tmp_path, ENTRY)
    (root / "methods" / "ctgan_copy.yaml").write_text(yaml.safe_dump(ENTRY))
    with pytest.raises(CatalogError) as exc:
        load_catalog(root)
    assert "ctgan" in str(exc.value)
