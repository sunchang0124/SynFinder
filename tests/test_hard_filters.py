from synfinder.intake import Intake
from synfinder.ranking import hard_filter
from tests.factories import make_method


def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")
    base.update(over)
    return Intake(**base)


def test_general_domain_methods_survive_a_biomedical_intake():
    kept, dropped = hard_filter([make_method(domains=["general"])], intake())
    assert [m.id for m in kept] == ["m"]
    assert dropped == []


def test_wrong_domain_is_excluded_with_a_reason():
    kept, dropped = hard_filter([make_method(domains=["ssh"])], intake())
    assert kept == []
    assert "biomedical" in dropped[0].reason


def test_unsupported_data_type_is_excluded():
    kept, dropped = hard_filter([make_method(data_types=["images"])], intake())
    assert kept == []
    assert "tabular_cross_sectional" in dropped[0].reason


def test_no_formal_dp_when_dp_is_required():
    kept, dropped = hard_filter(
        [make_method(formal_dp=False)], intake(privacy="formal_dp_required"))
    assert kept == []
    assert "differential privacy" in dropped[0].reason


def test_gpu_required_when_user_has_cpu_only():
    kept, dropped = hard_filter(
        [make_method(compute="gpu_required")], intake(compute="cpu_fine"))
    assert kept == []
    assert "GPU" in dropped[0].reason


def test_free_text_requirement_the_method_cannot_meet():
    kept, dropped = hard_filter(
        [make_method(variable_types=["continuous"])],
        intake(variable_types=["continuous", "free_text"]))
    assert kept == []
    assert "free text" in dropped[0].reason


def test_closed_license_when_open_is_required():
    kept, dropped = hard_filter(
        [make_method(license="proprietary")], intake(require_open_license=True))
    assert kept == []
    assert "proprietary" in dropped[0].reason


def test_unanswered_compute_does_not_exclude_a_gpu_method():
    kept, _ = hard_filter([make_method(compute="gpu_required")], intake())
    assert [m.id for m in kept] == ["m"]


def test_frameworks_are_never_ranked():
    kept, dropped = hard_filter([make_method(is_framework=True)], intake())
    assert kept == []
    assert "framework" in dropped[0].reason
