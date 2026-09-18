import yaml
from synfinder.cli import default_catalog_root
from synfinder.contribute import build_method, new_entry

ANSWERS = {
    "id": "mymethod", "name": "MyMethod", "family": "gan",
    "domains": ["biomedical"], "data_types": ["tabular_cross_sectional"],
    "variable_types": ["continuous", "categorical"],
    "formal_dp": False, "compute": "cpu_fine", "license": "MIT",
    "purposes": ["ml_augmentation"], "preserves": ["marginals"],
    "expertise": "medium", "maintained": True,
    "implementation_quality": "research_code",
    "caveats": ["Falls over on high-cardinality columns."],
    "evaluation": ["SDMetrics column shape"],
    "paper": None, "code": "https://github.com/example/mymethod",
    "preview_format": "tabular_csv", "preview_note": "One row per person.",
    "preview_body": "age,sex\n54,F\n",
}


def test_generated_entry_validates_against_the_schema():
    from synfinder.schema import Method
    Method(**build_method(ANSWERS))


def test_new_entry_writes_a_loadable_yaml_file(tmp_path):
    out = tmp_path / "methods"
    out.mkdir()
    assert new_entry("method", default_catalog_root(), ANSWERS, out) == 0
    written = out / "mymethod.yaml"
    assert written.exists()
    assert yaml.safe_load(written.read_text())["id"] == "mymethod"


def test_a_caveat_is_required(tmp_path):
    out = tmp_path / "methods"
    out.mkdir()
    assert new_entry("method", default_catalog_root(),
                     dict(ANSWERS, caveats=[]), out) == 1


def test_a_term_outside_the_taxonomy_is_refused(tmp_path):
    out = tmp_path / "methods"
    out.mkdir()
    assert new_entry("method", default_catalog_root(),
                     dict(ANSWERS, family="telepathy"), out) == 1
