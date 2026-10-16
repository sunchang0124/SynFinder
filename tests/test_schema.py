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
        scale=Scale(min_rows=1000, max_rows=1_000_000, max_cols=200,
                    evidence="test fixture"),
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


import datetime as dt  # noqa: E402
from synfinder.schema import Provenance  # noqa: E402
from tests.factories import make_method  # noqa: E402


def test_provenance_accepts_a_quoted_or_unquoted_date():
    a = Provenance(verified_on="2026-10-14", verified_by="Chang Sun",
                   sources_checked=["paper"])
    b = Provenance(verified_on=dt.date(2026, 10, 14), verified_by="Chang Sun",
                   sources_checked=["paper"])
    assert a.verified_on == b.verified_on == dt.date(2026, 10, 14)


def test_provenance_rejects_a_future_date():
    with pytest.raises(ValidationError, match="future"):
        Provenance(verified_on=dt.date.today() + dt.timedelta(days=1),
                   verified_by="x", sources_checked=["paper"])


def test_provenance_rejects_an_unknown_source():
    with pytest.raises(ValidationError, match="sources_checked"):
        Provenance(verified_on="2026-10-14", verified_by="x",
                   sources_checked=["blog"])


def test_a_checked_source_must_have_a_link_on_the_entry():
    with pytest.raises(ValidationError, match="no paper link"):
        make_method(links=Links(code="https://github.com/x/y"),
                    provenance=Provenance(verified_on="2026-10-14",
                                          verified_by="x",
                                          sources_checked=["paper"]))


def test_fields_checked_must_be_real_fields():
    with pytest.raises(ValidationError, match="fields_checked"):
        make_method(links=Links(code="https://github.com/x/y"),
                    provenance=Provenance(verified_on="2026-10-14",
                                          verified_by="x",
                                          sources_checked=["code"],
                                          fields_checked=["telepathy"]))


def test_governance_checked_reads_the_provenance():
    unchecked = make_method()
    checked = make_method(links=Links(code="https://github.com/x/y"),
                          provenance=Provenance(verified_on="2026-10-14",
                                                verified_by="x",
                                                sources_checked=["code"],
                                                fields_checked=["governance"]))
    assert unchecked.governance_checked() is False
    assert checked.governance_checked() is True
