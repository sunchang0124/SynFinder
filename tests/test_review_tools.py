"""The review tooling that writes into the catalog or vets evidence."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "review" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


apply = load("apply_decisions")
verify = load("verify_evidence")

YAML = """id: m
name: M
purposes: [ml_augmentation, benchmarking]
preserves: [marginals]
caveats:
  - One.
"""
PROV = "provenance:\n  verified_on: 2026-10-15\n  verified_by: \"Chang Sun\"\n  sources_checked: [paper]\n  fields_checked: [purposes, links]\n"


def test_rewrite_replaces_the_purposes_line_in_place():
    out = apply.rewrite(YAML, ["education"], PROV)
    assert "purposes: [education]\n" in out
    assert "ml_augmentation" not in out
    assert out.index("purposes:") < out.index("preserves:"), "order preserved"


def test_rewrite_appends_provenance_once_and_replaces_an_old_block():
    once = apply.rewrite(YAML, ["education"], PROV)
    twice = apply.rewrite(once, ["education", "benchmarking"], PROV.replace("2026-10-15", "2026-11-01"))
    assert twice.count("provenance:") == 1
    assert "2026-11-01" in twice and "2026-10-15" not in twice


def test_rewrite_refuses_a_file_without_purposes():
    import pytest
    with pytest.raises(ValueError):
        apply.rewrite("id: m\nname: M\n", ["education"], PROV)


def test_norm_tolerates_pdf_hyphenation_and_curly_quotes():
    assert verify.norm("privacy-\npreserving ‘data’") == verify.norm("privacy preserving 'data'")


def test_quote_verification_uses_substring_after_normalisation(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(verify, "SRC", tmp_path)
    monkeypatch.setattr(verify, "EVD", tmp_path)
    # one file plays both roles: sources and evidence share the id
    record = {"paper": {"fulltext": "We evaluate machine-\nlearning efficacy."},
              "code": {"readme": "A README."},
              "purposes": {
                  "ml_augmentation": {"verdict": "supported", "quotes": [
                      {"source": "paper", "text": "evaluate machine learning efficacy"},
                      {"source": "readme", "text": "not there"}]},
                  "education": {"verdict": "supported", "quotes": [{"source": "readme", "text": "nope"}]}}}
    (tmp_path / "x.json").write_text(json.dumps(record))
    ok, bad = verify.verify("x")
    out = json.loads((tmp_path / "x.json").read_text())
    assert (ok, bad) == (1, 2)
    assert out["purposes"]["ml_augmentation"]["verdict"] == "supported"
    assert out["purposes"]["education"]["verdict"] == "unclear"
