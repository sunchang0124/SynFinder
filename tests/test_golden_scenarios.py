"""Fixed intakes with known-correct outcomes.

These guard the weights: change catalog/weights.yaml and run this file.
"""
import pytest
from synfinder.catalog import load_catalog
from synfinder.cli import default_catalog_root
from synfinder.intake import Intake
from synfinder.ranking import load_weights, rank


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(default_catalog_root())


@pytest.fixture(scope="module")
def weights():
    return load_weights(default_catalog_root() / "weights.yaml")


def shortlist_ids(catalog, weights, **intake_kwargs):
    intake = Intake(**intake_kwargs)
    result = rank(catalog.generation_methods(), intake, weights, top_n=3)
    return [c.method.id for c in result.shortlist], result


def test_dp_requirement_keeps_only_dp_methods(catalog, weights):
    ids, result = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="tabular_cross_sectional",
        purpose="open_release", privacy="formal_dp_required")
    assert "ctgan" not in ids
    assert any(i in ids for i in ("dp_cgans", "privbayes"))
    assert any("differential privacy" in e.reason for e in result.excluded)


def test_low_expertise_cpu_only_prefers_simple_methods(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="tabular_cross_sectional",
        purpose="pipeline_testing", privacy="none",
        compute="cpu_fine", expertise="low")
    assert ids, "expected at least one recommendation"
    assert any(i in ids for i in ("metasyn", "gaussian_copula", "synthpop"))


def test_causal_structure_need_surfaces_a_graphical_method(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="tabular_cross_sectional",
        purpose="causal_inference", privacy="none",
        preserves=["causal_structure"])
    assert "bayesian_network" in ids
