import datetime as dt
from synfinder import repometa
from synfinder.schema import Maturity
from tests.factories import make_method


def test_github_slug_handles_the_shapes_in_the_catalog():
    assert repometa.github_slug("https://github.com/sdv-dev/CTGAN") == "sdv-dev/CTGAN"
    assert repometa.github_slug("https://github.com/sdv-dev/CTGAN/") == "sdv-dev/CTGAN"
    assert repometa.github_slug("https://github.com/sdv-dev/CTGAN.git") == "sdv-dev/CTGAN"
    assert repometa.github_slug(
        "https://github.com/org/repo/tree/main/src") == "org/repo"
    assert repometa.github_slug("https://gitlab.com/org/repo") is None
    assert repometa.github_slug(None) is None


def test_license_aliases_collapse_and_unknowns_are_none():
    assert repometa.normalise_license("GPL-3.0-only") == "GPL-3.0"
    assert repometa.normalise_license("MIT") == "MIT"
    assert repometa.normalise_license("NOASSERTION") is None
    assert repometa.normalise_license(None) is None


def test_language_mapping():
    assert repometa.map_language("Python") == "python"
    assert repometa.map_language("Jupyter Notebook") == "python"
    assert repometa.map_language("R") == "r"
    assert repometa.map_language("Brainfuck") is None


def test_maintained_is_a_24_month_window_and_not_archived():
    now = "2026-10-14T00:00:00Z"
    assert repometa.is_maintained("2025-01-01T00:00:00Z", False, now) is True
    assert repometa.is_maintained("2024-01-01T00:00:00Z", False, now) is False
    assert repometa.is_maintained("2026-01-01T00:00:00Z", True, now) is False


META = {"slug": "x/y", "license_spdx": "MIT", "language": "Python",
        "pushed_at": "2026-09-30T00:00:00Z", "archived": False}
FETCHED = "2026-10-14T00:00:00Z"


def test_no_drift_when_the_entry_matches():
    m = make_method(license="MIT", language="python", last_updated=2026,
                    maturity=Maturity(maintained=True, implementation_quality="research_code"))
    assert repometa.drift(m, META, FETCHED) == []


def test_every_drifting_field_is_named():
    m = make_method(license="Apache-2.0", language="r", last_updated=2023,
                    maturity=Maturity(maintained=False, implementation_quality="research_code"))
    msgs = repometa.drift(m, META, FETCHED)
    assert any("license" in s and "Apache-2.0" in s and "MIT" in s for s in msgs)
    assert any("language" in s for s in msgs)
    assert any("last_updated" in s and "2023" in s and "2026" in s for s in msgs)
    assert any("maintained" in s for s in msgs)


def test_multiple_language_and_missing_values_do_not_drift():
    m = make_method(license="MIT", language="multiple", last_updated=None,
                    maturity=Maturity(maintained=True, implementation_quality="research_code"))
    assert repometa.drift(m, dict(META, license_spdx="NOASSERTION"), FETCHED) == []
