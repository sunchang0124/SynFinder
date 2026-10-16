"""The shortlist order is purpose, then answered optional axes, then how
recently the repository was pushed, then name. No weights, no number."""
from datetime import date

from synfinder.intake import Intake
from synfinder.ranking import rank, score_method
from synfinder.repometa import maintenance_bucket
from synfinder.schema import Maturity
from tests.factories import make_method

TODAY = date(2026, 10, 16)


def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="not_required")
    base.update(over)
    return Intake(**base)


def maturity(last_pushed, maintained=True):
    return Maturity(maintained=maintained, last_release=None,
                    implementation_quality="research_code", last_pushed=last_pushed)


def test_buckets_follow_the_six_twelve_twentyfour_thirtysix_month_lines():
    assert maintenance_bucket("2026-10-01", TODAY)[0] == 0
    assert maintenance_bucket("2026-04-20", TODAY)[0] == 0   # 179 days
    assert maintenance_bucket("2026-04-10", TODAY)[0] == 1   # 189 days
    assert maintenance_bucket("2025-10-20", TODAY)[0] == 1
    assert maintenance_bucket("2025-10-10", TODAY)[0] == 2
    assert maintenance_bucket("2024-10-20", TODAY)[0] == 2
    assert maintenance_bucket("2024-10-10", TODAY)[0] == 3
    assert maintenance_bucket("2023-10-20", TODAY)[0] == 3
    assert maintenance_bucket("2023-10-10", TODAY)[0] == 4
    assert maintenance_bucket(None, TODAY)[0] == 5


def test_bucket_labels_name_the_window_and_the_month():
    assert maintenance_bucket("2026-10-01", TODAY)[1] == "last updated within 6 months (Oct 2026)"
    assert maintenance_bucket("2024-07-13", TODAY)[1] == "last updated within 36 months (Jul 2024)"
    assert maintenance_bucket("2019-08-19", TODAY)[1] == "last updated more than 36 months ago (Aug 2019)"
    assert maintenance_bucket(None, TODAY)[1] == "no repository update date on record"


def test_purpose_beats_everything_else():
    fresh_wrong = make_method(id="a", name="A", purposes=["education"],
                              maturity=maturity("2026-10-01"))
    stale_right = make_method(id="b", name="B", purposes=["ml_augmentation"],
                              maturity=maturity("2015-01-01"))
    ids = [c.method.id for c in rank([fresh_wrong, stale_right], intake(), today=TODAY).shortlist]
    assert ids == ["b"]


def test_answered_optional_axes_come_before_recency():
    fresh_hard = make_method(id="a", name="A", expertise="high", maturity=maturity("2026-10-01"))
    old_easy = make_method(id="b", name="B", expertise="low", maturity=maturity("2022-01-01"))
    ids = [c.method.id for c in rank([fresh_hard, old_easy], intake(expertise="low"), today=TODAY).shortlist]
    assert ids == ["b", "a"]
    ids = [c.method.id for c in rank([fresh_hard, old_easy], intake(), today=TODAY).shortlist]
    assert ids == ["a", "b"]


def test_within_a_bucket_the_order_is_alphabetical_not_by_exact_date():
    zed = make_method(id="z", name="Zeta", maturity=maturity("2026-10-10"))
    alpha = make_method(id="a", name="Alpha", maturity=maturity("2026-06-01"))
    ids = [c.method.id for c in rank([zed, alpha], intake(), today=TODAY).shortlist]
    assert ids == ["a", "z"]


def test_name_order_ignores_case():
    lower = make_method(id="l", name="ctgan", maturity=maturity("2026-10-10"))
    upper = make_method(id="u", name="Bayesian", maturity=maturity("2026-10-10"))
    ids = [c.method.id for c in rank([lower, upper], intake(), today=TODAY).shortlist]
    assert ids == ["u", "l"]


def test_missing_date_sorts_last():
    dated = make_method(id="d", name="Zed", maturity=maturity("2015-01-01"))
    undated = make_method(id="u", name="Alpha", maturity=maturity(None))
    ids = [c.method.id for c in rank([dated, undated], intake(), today=TODAY).shortlist]
    assert ids == ["d", "u"]


def test_maintenance_note_is_on_the_candidate_and_in_the_axes():
    c = score_method(make_method(maturity=maturity("2019-08-19")), intake(), today=TODAY)
    assert c.maintenance_note == "last updated more than 36 months ago (Aug 2019)"
    assert any(a.axis == "maintenance" and a.score < 0.6 for a in c.axes)
