from synfinder.intake import Intake
from synfinder.ranking import rank
from synfinder.report import render_markdown, render_html, comparison_rows
from tests.factories import make_method


def intake(**over) -> Intake:
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="not_required")
    base.update(over)
    return Intake(**base)


def test_markdown_lists_the_shortlist_and_the_exclusions():
    methods = [make_method(id="good", name="Good", purposes=["ml_augmentation"]),
               make_method(id="img", name="Imgs", data_types=["images"])]
    md = render_markdown(intake(), rank(methods, intake()))
    assert "Good" in md
    assert "Imgs" in md
    assert "cannot handle tabular_cross_sectional data" in md


def test_markdown_records_the_intake_so_the_report_is_self_contained():
    md = render_markdown(intake(), rank([make_method()], intake()))
    assert "ml_augmentation" in md
    assert "biomedical" in md


def test_comparison_rows_has_one_row_per_shortlisted_method():
    methods = [make_method(id="a", name="A"), make_method(id="b", name="B")]
    header, rows = comparison_rows(rank(methods, intake()))
    assert header[0] == "Method"
    assert len(rows) == 2


def test_html_is_wrapped_in_a_document():
    html = render_html(intake(), rank([make_method()], intake()))
    assert html.lstrip().startswith("<!doctype html>")
    assert "</html>" in html


def test_an_uncovered_modality_says_so_instead_of_claiming_no_match():
    """An empty shortlist for images is a catalog gap, not a no-match."""
    md = render_markdown(intake(data_type="images"),
                         rank([make_method()], intake(data_type="images")),
                         covered=False)
    assert "no entries for images data yet" in md
    assert "not a statement that no method exists" in md


def test_a_covered_modality_with_no_match_says_that_instead():
    md = render_markdown(intake(), rank([], intake()), covered=True)
    assert "No method in the catalog meets these requirements" in md
