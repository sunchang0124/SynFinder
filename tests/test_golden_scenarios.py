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


def test_longitudinal_ehr_surfaces_sequence_methods(catalog, weights):
    """Batch 2: cross-sectional-only methods must not appear for visit data."""
    ids, result = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="coded_event_sequences",
        purpose="ml_augmentation", privacy="none")
    assert any(i in ids for i in ("halo", "synteg", "eva_ehr", "promptehr"))
    for cross_sectional_only in ("ctgan", "tvae", "gaussian_copula", "metasyn"):
        assert cross_sectional_only not in ids
    assert any(e.method_id == "ctgan" for e in result.excluded)


def test_a_simulator_survives_when_formal_dp_is_demanded(catalog, weights):
    """Synthea uses no real records, so a DP requirement must not drop it."""
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="coded_event_sequences",
        purpose="open_release", privacy="formal_dp_required")
    assert "synthea" in ids


def test_time_series_intake_excludes_cross_sectional_methods(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="time_series",
        purpose="ml_augmentation", privacy="none",
        preserves=["temporal_dynamics"])
    assert any(i in ids for i in
               ("timeautodiff", "doppelganger", "timegan", "rtsgan", "ehr_safe"))
    assert "ctgan" not in ids


def test_survival_data_surfaces_the_survival_method(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="survival",
        purpose="statistical_replication", privacy="none")
    assert "survivalgan" in ids


def test_dp_open_release_now_prefers_the_marginal_based_default(catalog, weights):
    """MST/AIM is the honest DP baseline; it must be on the list."""
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="general", data_type="tabular_cross_sectional",
        purpose="open_release", privacy="formal_dp_required",
        compute="cpu_fine")
    assert "mst_aim" in ids


def test_frameworks_never_appear_in_a_shortlist(catalog, weights):
    ids, result = shortlist_ids(
        catalog, weights,
        domain="general", data_type="tabular_cross_sectional",
        purpose="pipeline_testing", privacy="none")
    # Frameworks are filtered out before ranking, so they are simply absent
    # rather than carrying an exclusion reason.
    assert "sdv" not in ids and "synthcity" not in ids
    assert all(c.method.is_framework is False for c in
               rank(catalog.generation_methods(),
                    Intake(domain="general",
                           data_type="tabular_cross_sectional",
                           purpose="pipeline_testing", privacy="none"),
                    weights).shortlist)
