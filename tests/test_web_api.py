import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from synfinder.web import app  # noqa: E402

client = TestClient(app)

INTAKE = {"domain": "biomedical", "data_type": "tabular_cross_sectional",
          "purpose": "open_release", "privacy": "required"}


def test_taxonomy_exposes_the_form_options():
    body = client.get("/api/taxonomy").json()
    assert "biomedical" in body["domains"]
    assert "required" in body["privacy"]
    assert body["counts"]["methods"] > 0


def test_recommend_returns_a_shortlist_with_explanations():
    body = client.post("/api/recommend", json=INTAKE).json()
    assert body["shortlist"], "expected recommendations"
    first = body["shortlist"][0]
    assert 0 <= first["fit"] <= 1
    assert first["caveats"], "every method carries caveats"
    assert first["preview"]["body"]


def test_api_and_engine_agree_on_the_shortlist():
    """The web layer must never reach a different answer than the CLI."""
    from synfinder.catalog import load_catalog
    from synfinder.cli import default_catalog_root
    from synfinder.intake import Intake
    from synfinder.ranking import load_weights, rank

    cat = load_catalog(default_catalog_root())
    engine = rank(cat.generation_methods(), Intake(**INTAKE),
                  load_weights(default_catalog_root() / "weights.yaml"),
                  top_n=5)
    api = client.post("/api/recommend", json=INTAKE).json()
    assert [c.method.id for c in engine.shortlist] == \
           [c["id"] for c in api["shortlist"]]


def test_recommend_no_longer_leads_with_datasets():
    """Datasets live on their own tab; the shortlist is the answer."""
    body = client.post("/api/recommend", json=INTAKE).json()
    assert "datasets" not in body
    assert "You may not need to generate anything" not in body["report_markdown"]


def test_methods_endpoint_searches_by_name_alias_and_family():
    assert [m["id"] for m in client.get("/api/methods?q=synthea").json()["methods"]] == ["synthea"]
    assert [m["id"] for m in client.get("/api/methods?q=syntheticmass").json()["methods"]] == ["synthea"]
    everything = client.get("/api/methods").json()["methods"]
    assert len(everything) == client.get("/api/taxonomy").json()["counts"]["methods"] + \
        client.get("/api/taxonomy").json()["counts"]["frameworks"]
    assert everything == sorted(everything, key=lambda m: m["name"].lower())
    gans = client.get("/api/methods?family=gan").json()["methods"]
    assert gans and all(m["family"] == "gan" for m in gans)


def test_method_json_carries_what_the_card_shows():
    m = client.get("/api/methods?q=synthea").json()["methods"][0]
    for key in ("name", "family", "verified", "data_types", "purposes", "caveats",
                "license", "maintained", "links", "is_framework", "formal_dp"):
        assert key in m, key
    assert m["verified"].startswith(("Verified", "Not yet"))


def test_recommend_reports_exclusions_with_reasons():
    body = client.post("/api/recommend", json=INTAKE).json()
    assert body["excluded"]
    assert all(e["reason"] for e in body["excluded"])


def test_datasets_endpoint_filters():
    all_sets = client.get("/api/datasets").json()["datasets"]
    assert all_sets
    none = client.get("/api/datasets?data_type=images").json()["datasets"]
    assert none == []


def test_the_page_and_its_assets_are_served():
    assert "<title>SynFinder</title>" in client.get("/").text
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_the_frontend_never_reimplements_scoring():
    """Ranking lives in Python. If app.js grows a weights table or a scoring
    loop, the two implementations will drift and the interface will lie."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text()
    for banned in ["DEFAULT_WEIGHTS", "hard_filter", "weights ="]:
        assert banned not in js, f"app.js appears to score client-side: {banned}"


def test_the_page_is_self_contained():
    """Behind a path-prefixing proxy an absolute /static/... URL 404s and the
    page renders unstyled and unreadable. The page must carry its own assets."""
    html = client.get("/").text
    assert 'href="/static' not in html
    assert 'src="/static' not in html
    assert "design tokens" in html, "CSS should be inlined"
    assert "api/taxonomy" in html, "JS should be inlined"


def test_api_calls_resolve_relative_to_the_page():
    """A leading slash breaks every fetch when served under a path prefix."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text()
    assert 'fetch("/api' not in js
    assert "const API" in js


def test_frontend_rendering_checks_pass():
    """Runs tests/test_frontend_rendering.js - label capitalisation and the
    preview table renderers. Skipped where node is unavailable."""
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    script = Path(__file__).resolve().parent / "test_frontend_rendering.js"
    r = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_privacy_not_required_still_surfaces_privacy_preserving_methods():
    """Reported by Chang: with no privacy requirement she saw no privacy
    methods. They were ranked but cut off by the top-5 shortlist."""
    body = client.post("/api/recommend", json={
        "domain": "biomedical", "data_type": "tabular_cross_sectional",
        "purpose": "open_release", "privacy": "not_required"}).json()
    everything = body["shortlist"] + body["also_ranked"]
    assert any(c["formal_dp"] for c in everything), \
        "privacy-preserving methods must be reachable when privacy is not required"
    assert not any("privacy measures" in e["reason"] for e in body["excluded"]), \
        "nothing may be excluded on privacy grounds when none was required"


def test_privacy_is_binary():
    body = client.get("/api/taxonomy").json()
    assert body["privacy"] == ["not_required", "required"]


def test_the_page_is_never_cached():
    """The page carries its own CSS and JS, so a cached copy pins the entire
    interface to an old version - which is indistinguishable from a bug."""
    r = client.get("/")
    assert "no-store" in r.headers.get("cache-control", "")


def test_the_page_carries_a_build_id():
    import re
    html = client.get("/").text
    assert "__BUILD__" not in html, "build placeholder was not substituted"
    assert re.search(r"build [0-9a-f]{7}", html)


def test_candidates_carry_the_language_and_year_tags():
    body = client.post("/api/recommend", json={
        "domain": "biomedical", "data_type": "tabular_cross_sectional",
        "purpose": "ml_augmentation", "privacy": "not_required"}).json()
    assert any(c["language"] for c in body["shortlist"])
    assert any(c["last_updated"] for c in body["shortlist"])


def test_candidates_and_datasets_carry_a_verification_label():
    body = client.post("/api/recommend", json=INTAKE).json()
    assert all("verified" in c for c in body["shortlist"])
    sets = client.get("/api/datasets").json()["datasets"]
    assert all("verified" in d for d in sets)


GOOD_ANSWERS = {
    "id": "mymethod", "name": "MyMethod", "family": "gan",
    "domains": ["biomedical"], "data_types": ["tabular_cross_sectional"],
    "variable_types": ["continuous"], "formal_dp": False, "compute": "cpu_fine",
    "license": "MIT", "purposes": ["ml_augmentation"], "preserves": ["marginals"],
    "expertise": "medium", "maintained": True,
    "implementation_quality": "research_code",
    "caveats": ["Falls over on high-cardinality columns."], "evaluation": [],
    "paper": None, "code": "https://github.com/example/mymethod",
    "preview_format": "tabular_csv", "preview_note": "One row per person.",
    "preview_body": "age,sex\n54,F\n",
}


def test_validate_endpoint_accepts_a_good_entry():
    body = client.post("/api/validate", json={"answers": GOOD_ANSWERS}).json()
    assert body["errors"] == []
    assert body["yaml"].startswith("id: mymethod")


def test_validate_endpoint_returns_errors_not_a_500():
    bad = dict(GOOD_ANSWERS, formal_dp=True, caveats=[])
    r = client.post("/api/validate", json={"answers": bad})
    assert r.status_code == 200
    body = r.json()
    assert body["yaml"] is None
    assert any("dp_mechanism" in e for e in body["errors"])
    assert any("caveats" in e for e in body["errors"])


def test_the_page_carries_the_submit_tab():
    html = client.get("/").text
    assert 'data-view="submit"' in html
    assert 'id="submitForm"' in html
    assert "api/validate" in html, "the submit flow must call the shared validator"


def test_recommend_carries_narration_when_a_model_is_available(monkeypatch):
    from synfinder import llm, web
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "narrate", lambda e, m, i: f"Fluent prose about {m.name}.")
    body = client.post("/api/recommend", json=INTAKE).json()
    first = body["shortlist"][0]
    assert first["narration"] == f"Fluent prose about {first['name']}."
    assert all(c["narration"] is None for c in body["also_ranked"])


def test_recommend_narration_is_null_without_a_model(monkeypatch):
    from synfinder import llm
    monkeypatch.setattr(llm, "available", lambda: False)
    body = client.post("/api/recommend", json=INTAKE).json()
    assert all(c["narration"] is None for c in body["shortlist"])


def test_validate_endpoint_rejects_an_id_already_in_the_catalog():
    body = client.post("/api/validate",
                       json={"answers": dict(GOOD_ANSWERS, id="ctgan")}).json()
    assert body["yaml"] is None
    assert any("already exists" in e for e in body["errors"])
