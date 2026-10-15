from synfinder.catalog import search_methods
from tests.factories import make_method

METHODS = [
    make_method(id="synthea", name="Synthea", family="agent_simulation",
                aliases=["SyntheticMass generator"]),
    make_method(id="ctgan", name="CTGAN", family="gan"),
    make_method(id="copula_gan", name="CopulaGAN", family="gan"),
]


def ids(found):
    return [m.id for m in found]


def test_empty_query_returns_everything_sorted_by_name():
    assert ids(search_methods(METHODS, "")) == ["copula_gan", "ctgan", "synthea"]


def test_query_matches_name_case_insensitively():
    assert ids(search_methods(METHODS, "SYNTH")) == ["synthea"]


def test_query_matches_aliases_and_ids():
    assert ids(search_methods(METHODS, "syntheticmass")) == ["synthea"]
    assert ids(search_methods(METHODS, "copula_")) == ["copula_gan"]


def test_query_matches_family_words():
    assert ids(search_methods(METHODS, "agent simulation")) == ["synthea"]


def test_family_filter_narrows_and_any_means_no_filter():
    assert ids(search_methods(METHODS, "", family="gan")) == ["copula_gan", "ctgan"]
    assert len(search_methods(METHODS, "", family="any")) == 3


def test_no_match_is_an_empty_list():
    assert search_methods(METHODS, "zzz") == []
