import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from synfinder.web import app  # noqa: E402

client = TestClient(app)

INTAKE = {"domain": "biomedical", "data_type": "tabular_cross_sectional",
          "purpose": "open_release", "privacy": "formal_dp_required"}


def test_taxonomy_exposes_the_form_options():
    body = client.get("/api/taxonomy").json()
    assert "biomedical" in body["domains"]
    assert "formal_dp_required" in body["privacy"]
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
