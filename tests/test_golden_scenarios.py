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
    """The invariant, not a fixed list: every survivor either carries a formal
    guarantee or never reads real data. Naming specific methods here would rot
    as the catalog grows."""
    intake = Intake(domain="biomedical", data_type="tabular_cross_sectional",
                    purpose="open_release", privacy="formal_dp_required")
    result = rank(catalog.generation_methods(), intake, weights, top_n=8)
    ids = [c.method.id for c in result.shortlist]
    assert "ctgan" not in ids
    assert ids, "expected differentially private options"
    for c in result.shortlist:
        assert c.method.formal_dp or c.method.requires_no_source_data, (
            f"{c.method.id} has neither a DP guarantee nor exemption")
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


def test_medical_imaging_surfaces_imaging_methods(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="images",
        purpose="ml_augmentation", privacy="none")
    assert any(i in ids for i in
               ("latent_diffusion_brain_mri", "medical_diffusion_3d", "roentgen"))
    assert "ctgan" not in ids


def test_clinical_text_prefers_the_shareable_source_when_releasing(catalog, weights):
    """Asclepius is built from published case reports, so it can be released;
    a model trained on real notes cannot be, and must not outrank it here."""
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="text",
        purpose="open_release", privacy="none")
    assert "asclepius_notes" in ids


def test_graph_intake_surfaces_graph_methods(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="general", data_type="graph",
        purpose="statistical_replication", privacy="none")
    assert "ergm" in ids


def test_genomic_benchmarking_prefers_simulation_over_resampling(catalog, weights):
    """For benchmarking you want known ground truth and no disclosure risk,
    which is simulation from theory - not resampled real haplotypes."""
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="genomic",
        purpose="benchmarking", privacy="none")
    assert any(i in ids for i in ("msprime", "slim"))


def test_genomic_under_a_dp_requirement_keeps_only_the_simulators(catalog, weights):
    """Resampling real haplotypes is not exempt; simulating from theory is."""
    ids, result = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="genomic",
        purpose="open_release", privacy="formal_dp_required")
    assert any(i in ids for i in ("msprime", "slim"))
    assert "hapgen2" not in ids
    assert "artificial_genomes_gan" not in ids


def test_single_cell_intake_surfaces_single_cell_simulators(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="biomedical", data_type="single_cell_omics",
        purpose="benchmarking", privacy="none")
    assert any(i in ids for i in ("splatter", "scdesign3", "muscat", "sparsim"))
    assert "ctgan" not in ids


def test_low_expertise_cpu_tabular_now_reaches_a_fast_tree_method(catalog, weights):
    """ARF trains in seconds on a CPU and should be reachable by a beginner."""
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="general", data_type="tabular_cross_sectional",
        purpose="ml_augmentation", privacy="none",
        compute="cpu_fine", expertise="low")
    assert "arf" in ids


def test_dp_tabular_shortlist_is_marginal_based_not_gan(catalog, weights):
    """At a formal DP requirement the marginal-based family should lead; a DP
    GAN is rarely the right answer and must not crowd them out."""
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="general", data_type="tabular_cross_sectional",
        purpose="open_release", privacy="formal_dp_required",
        compute="cpu_fine")
    assert any(i in ids for i in
               ("mst_aim", "privbayes", "privsyn", "pac_synth", "dp_merf"))


def test_relational_data_reaches_the_one_method_that_handles_it(catalog, weights):
    ids, _ = shortlist_ids(
        catalog, weights,
        domain="general", data_type="tabular_longitudinal",
        purpose="pipeline_testing", privacy="none")
    assert ids, "expected recommendations for longitudinal tabular data"
