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


from synfinder.catalog import load_catalog
from synfinder.contribute import validate_method, to_yaml

TAX = load_catalog(default_catalog_root()).taxonomy


def test_validate_method_returns_no_errors_and_the_entry_for_good_answers():
    errors, entry = validate_method(ANSWERS, TAX)
    assert errors == []
    assert entry["id"] == "mymethod"
    assert "mymethod" in to_yaml(entry)


def test_validate_method_names_a_term_outside_the_taxonomy():
    errors, entry = validate_method(dict(ANSWERS, family="telepathy"), TAX)
    assert entry is None
    assert any("telepathy" in e and "family" in e for e in errors)


def test_validate_method_reports_dp_without_a_mechanism():
    errors, entry = validate_method(dict(ANSWERS, formal_dp=True), TAX)
    assert entry is None
    assert any("dp_mechanism" in e for e in errors)


def test_validate_method_reports_an_empty_caveat_list():
    errors, entry = validate_method(dict(ANSWERS, caveats=[]), TAX)
    assert entry is None
    assert any("caveats" in e for e in errors)


def test_validate_method_reports_a_missing_required_answer():
    bad = dict(ANSWERS)
    del bad["name"]
    errors, entry = validate_method(bad, TAX)
    assert entry is None
    assert any("name" in e for e in errors)
