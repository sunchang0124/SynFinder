import pytest
from synfinder.intake import Intake
from synfinder.ranking import score_method, rank, DEFAULT_WEIGHTS
from synfinder.schema import Scale, Governance
from tests.factories import make_method


def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")
    base.update(over)
    return Intake(**base)


def axis(candidate, name):
    return next(a for a in candidate.axes if a.axis == name)


def test_purpose_match_scores_one():
    c = score_method(make_method(purposes=["ml_augmentation"]),
                     intake(), DEFAULT_WEIGHTS)
    assert axis(c, "purpose").score == 1.0


def test_purpose_mismatch_scores_zero_but_does_not_eliminate():
    c = score_method(make_method(purposes=["education"]),
                     intake(), DEFAULT_WEIGHTS)
    assert axis(c, "purpose").score == 0.0
    assert 0.0 <= c.fit <= 1.0


def test_preserves_is_the_fraction_of_needs_met():
    m = make_method(preserves=["marginals", "joint_correlations"])
    c = score_method(m, intake(preserves=["marginals", "temporal_dynamics"]),
                     DEFAULT_WEIGHTS)
    assert axis(c, "preserves").score == 0.5


def test_unanswered_axis_is_absent_not_zero():
    c = score_method(make_method(), intake(), DEFAULT_WEIGHTS)
    assert all(a.axis != "preserves" for a in c.axes)
    assert all(a.axis != "expertise" for a in c.axes)


def test_unanswered_axis_does_not_drag_the_fit_down():
    """A perfect method scores 1.0 even when most questions were skipped."""
    m = make_method(purposes=["ml_augmentation"])
    c = score_method(m, intake(), DEFAULT_WEIGHTS)
    assert c.fit == pytest.approx(1.0)


def test_method_needing_more_expertise_than_the_user_has_is_penalised():
    low = score_method(make_method(expertise="high"),
                       intake(expertise="low"), DEFAULT_WEIGHTS)
    ok = score_method(make_method(expertise="low"),
                      intake(expertise="low"), DEFAULT_WEIGHTS)
    assert axis(low, "expertise").score < axis(ok, "expertise").score


def test_scale_beyond_the_method_maximum_is_penalised():
    m = make_method(scale=Scale(min_rows=None, max_rows=10_000, max_cols=None,
                                evidence="test fixture"))
    c = score_method(m, intake(expected_rows=1_000_000), DEFAULT_WEIGHTS)
    assert axis(c, "scale").score < 0.5


def test_governance_evidence_is_rewarded_when_asked_for():
    with_ev = make_method(
        governance=Governance(acceptance_evidence=["Approved by an MREC in 2024"]))
    without = make_method(governance=Governance())
    i = intake(needs_governance_evidence=True)
    assert (axis(score_method(with_ev, i, DEFAULT_WEIGHTS), "governance").score
            > axis(score_method(without, i, DEFAULT_WEIGHTS), "governance").score)


def test_rank_returns_best_first_and_respects_top_n():
    good = make_method(id="good", purposes=["ml_augmentation"])
    poor = make_method(id="poor", purposes=["education"])
    result = rank([poor, good], intake(), top_n=1)
    assert [c.method.id for c in result.shortlist] == ["good"]


def test_rank_reports_exclusions():
    result = rank([make_method(id="img", data_types=["images"])], intake())
    assert result.shortlist == []
    assert result.excluded[0].method_id == "img"


def test_ties_break_towards_the_method_with_a_track_record():
    """With only the core four answered, many methods score identically."""
    from synfinder.schema import Governance
    proven = make_method(id="proven", governance=Governance(
        acceptance_evidence=["Accepted by a national statistics office"]))
    unproven = make_method(id="unproven", governance=Governance())
    result = rank([unproven, proven], intake(), top_n=1)
    assert [c.method.id for c in result.shortlist] == ["proven"]
