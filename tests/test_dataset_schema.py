import pytest
from pydantic import ValidationError
from synfinder.schema import Dataset


def dataset(**over):
    base = dict(
        id="d1", name="D", domains=["biomedical"],
        data_types=["tabular_cross_sectional"], purposes=["education"],
        n_records="1,000 patients", formal_dp=False,
        access_conditions="Free download", license="CC0-1.0",
        realism_caveats=["Not a real population."],
    )
    base.update(over)
    return Dataset(**base)


def test_dataset_accepts_lists_for_domain_and_data_type():
    d = dataset()
    assert d.domains == ["biomedical"]
    assert d.data_types == ["tabular_cross_sectional"]


def test_dataset_requires_a_realism_caveat():
    with pytest.raises(ValidationError):
        dataset(realism_caveats=[])


def test_formal_dp_requires_a_mechanism():
    with pytest.raises(ValidationError):
        dataset(formal_dp=True, dp_mechanism=None)
