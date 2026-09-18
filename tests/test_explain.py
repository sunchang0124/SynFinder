from synfinder.explain import explain, as_text
from synfinder.intake import Intake
from synfinder.ranking import score_method, DEFAULT_WEIGHTS
from tests.factories import make_method


def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="not_required")
    base.update(over)
    return Intake(**base)


def test_why_fits_names_the_strongest_axes():
    c = score_method(make_method(purposes=["ml_augmentation"]),
                     intake(), DEFAULT_WEIGHTS)
    e = explain(c)
    assert any("ml augmentation" in reason for reason in e.why_fits)


def test_weakness_names_the_lowest_scoring_axis():
    # purpose must MATCH here, so that `preserves` is unambiguously the
    # weakest axis; if both scored 0.0 the tie-break would pick purpose.
    m = make_method(purposes=["ml_augmentation"], preserves=["marginals"])
    c = score_method(m, intake(preserves=["temporal_dynamics"]), DEFAULT_WEIGHTS)
    e = explain(c)
    assert e.weakness is not None
    assert "temporal dynamics" in e.weakness


def test_caveats_are_carried_verbatim():
    m = make_method(caveats=["Breaks on irregular visit spacing."])
    e = explain(score_method(m, intake(), DEFAULT_WEIGHTS))
    assert e.caveats == ["Breaks on irregular visit spacing."]


def test_no_weakness_when_everything_scores_full():
    m = make_method(purposes=["ml_augmentation"])
    e = explain(score_method(m, intake(), DEFAULT_WEIGHTS))
    assert e.weakness is None


def test_as_text_contains_every_section_present():
    m = make_method(purposes=["education"],
                    caveats=["A caveat."],
                    evaluation=["Run SDMetrics."])
    text = as_text(explain(score_method(m, intake(), DEFAULT_WEIGHTS)))
    assert "Watch out" in text
    assert "How to check" in text
    assert "Run SDMetrics." in text
