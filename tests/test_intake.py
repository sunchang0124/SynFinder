import pytest
from pydantic import ValidationError
from synfinder.intake import Intake


def test_core_four_are_required():
    with pytest.raises(ValidationError):
        Intake(domain="biomedical", data_type="tabular_cross_sectional")


def test_optional_axes_default_to_unanswered():
    i = Intake(domain="biomedical", data_type="tabular_cross_sectional",
               purpose="open_release", privacy="formal_dp_required")
    assert i.expertise is None
    assert i.preserves == []
    assert i.answered("expertise") is False
    assert i.answered("preserves") is False
    assert i.answered("purpose") is True


def test_answered_is_true_once_an_optional_axis_is_filled():
    i = Intake(domain="biomedical", data_type="tabular_cross_sectional",
               purpose="open_release", privacy="none",
               preserves=["temporal_dynamics"], expertise="low")
    assert i.answered("preserves") is True
    assert i.answered("expertise") is True
