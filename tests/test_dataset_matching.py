from synfinder.datasets import match_datasets
from synfinder.intake import Intake
from synfinder.ranking import rank
from synfinder.report import render_markdown
from synfinder.schema import Dataset
from tests.factories import make_method


def intake(**over):
    base = dict(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="education", privacy="not_required")
    base.update(over)
    return Intake(**base)


def dataset(**over):
    base = dict(id="d1", name="Ready Set", domains=["biomedical"],
                data_types=["tabular_cross_sectional"],
                purposes=["education"], n_records="1,000 patients",
                access_conditions="Free download", license="CC0-1.0",
                realism_caveats=["Not a real population."])
    base.update(over)
    return Dataset(**base)


def test_a_matching_dataset_is_returned():
    assert [d.id for d in match_datasets([dataset()], intake())] == ["d1"]


def test_a_general_domain_dataset_matches_a_biomedical_intake():
    assert match_datasets([dataset(domains=["general"])], intake())


def test_the_wrong_data_type_does_not_match():
    assert match_datasets([dataset(data_types=["images"])], intake()) == []


def test_the_wrong_purpose_does_not_match():
    assert match_datasets([dataset(purposes=["causal_inference"])],
                          intake()) == []


def test_a_dataset_with_no_stated_purpose_still_matches():
    """Absence of a purpose list is silence, not unsuitability."""
    assert match_datasets([dataset(purposes=[])], intake())


def test_the_report_leads_with_datasets_when_any_match():
    md = render_markdown(intake(), rank([make_method()], intake()),
                         [dataset()])
    lead = md.index("You may not need to generate anything")
    methods = md.index("## Recommended methods")
    assert lead < methods, "datasets must appear above the shortlist"
