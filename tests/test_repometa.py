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
                    maturity=Maturity(maintained=True, implementation_quality="research_code",
                                      last_pushed="2026-09-30"))
    assert repometa.drift(m, META, FETCHED) == []


def test_last_pushed_drifts_when_it_lags_the_repository():
    m = make_method(license="MIT", language="python", last_updated=2026,
                    maturity=Maturity(maintained=True, implementation_quality="research_code",
                                      last_pushed="2026-01-01"))
    msgs = repometa.drift(m, META, FETCHED)
    assert msgs == ["m: last_pushed is '2026-01-01' but the repository was last pushed 2026-09-30"]


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
                    maturity=Maturity(maintained=True, implementation_quality="research_code",
                                      last_pushed="2026-09-30"))
    assert repometa.drift(m, dict(META, license_spdx="NOASSERTION"), FETCHED) == []


def test_rewrite_fields_touches_only_the_named_lines():
    text = ("id: m\n# keep this comment\nlicense: Apache-2.0\nlanguage: r\n"
            "last_updated: 2023\nmaturity:\n  maintained: false\n"
            "  last_release: \"2023-01\"\n  implementation_quality: research_code\n")
    out = repometa.rewrite_fields(text, {"license": "MIT", "language": "python",
                                         "last_updated": "2026",
                                         "maturity.maintained": "true"})
    assert "# keep this comment" in out
    assert "license: MIT\n" in out
    assert "language: python\n" in out
    assert "last_updated: 2026\n" in out
    assert "  maintained: true\n" in out
    assert '  last_release: "2023-01"\n' in out
    assert out.count("\n") == text.count("\n")


def test_rewrite_fields_appends_a_missing_child_to_the_end_of_its_block():
    text = ("id: m\nmaturity:\n  maintained: true\n  implementation_quality: research_code\n"
            "governance:\n  acceptance_evidence: []\n")
    out = repometa.rewrite_fields(text, {"maturity.last_pushed": "2026-09-30"})
    assert out == ("id: m\nmaturity:\n  maintained: true\n  implementation_quality: research_code\n"
                   "  last_pushed: 2026-09-30\ngovernance:\n  acceptance_evidence: []\n")


def test_rewrite_fields_adds_a_missing_top_level_field_after_license():
    text = "id: m\nlicense: MIT\npurposes: [education]\n"
    out = repometa.rewrite_fields(text, {"language": "python"})
    assert out == "id: m\nlicense: MIT\nlanguage: python\npurposes: [education]\n"


def test_dataset_licence_is_not_compared_with_the_repository():
    from synfinder.schema import Dataset, Links
    d = Dataset(id="d", name="D", domains=["health"], data_types=["tabular"],
                n_records="1k", access_conditions="open", license="CC-BY-4.0",
                realism_caveats=["synthetic"], links=Links(code="https://github.com/o/r"))
    assert not any("license" in s for s in repometa.drift(d, dict(META, license_spdx="GPL-3.0"), FETCHED))
