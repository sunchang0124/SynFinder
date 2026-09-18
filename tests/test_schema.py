import pytest
from pydantic import ValidationError
from synfinder.schema import Method, Scale, Maturity, Governance, Links


def minimal_method(**over):
    base = dict(
        id="ctgan", name="CTGAN", family="gan",
        domains=["general"], data_types=["tabular_cross_sectional"],
        variable_types=["continuous", "categorical"],
        formal_dp=False, dp_mechanism=None,
        compute="gpu_recommended", license="MIT",
        purposes=["ml_augmentation"], preserves=["joint_correlations"],
        scale=Scale(min_rows=1000, max_rows=1_000_000, max_cols=200),
        expertise="medium",
        maturity=Maturity(maintained=True, last_release="2024-06",
                          implementation_quality="production_ready"),
        governance=Governance(acceptance_evidence=[], known_deployments=[]),
        caveats=["Struggles with high-cardinality categorical columns."],
        evaluation=["SDMetrics column-shape and column-pair-trend scores"],
        links=Links(paper="10.48550/arXiv.1907.00503",
                    code="https://github.com/sdv-dev/CTGAN", docs=None),
        related_datasets=[], is_framework=False,
    )
    base.update(over)
    return Method(**base)


def test_method_accepts_a_complete_entry():
    m = minimal_method()
    assert m.id == "ctgan"
    assert m.is_framework is False


def test_method_requires_caveats():
    with pytest.raises(ValidationError):
        minimal_method(caveats=[])


def test_formal_dp_requires_a_mechanism():
    with pytest.raises(ValidationError):
        minimal_method(formal_dp=True, dp_mechanism=None)
