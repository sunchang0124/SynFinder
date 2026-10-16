"""JSON API over the ranking engine, plus the static frontend.

Deliberately thin: every decision is made by catalog/ranking/explain, so the
web interface and the CLI can never disagree about a recommendation.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog import Catalog, load_catalog, search_methods
from .contribute import to_yaml, validate_method
from . import llm
from .explain import explain
from .intake import Intake
from .payload import _candidate_json, _dataset_json, _method_json, _top_only
from .ranking import Ranking, rank
from .report import empty_result_message, render_html, render_markdown

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"
CATALOG_DIR = ROOT / "catalog"

app = FastAPI(title="SynFinder", docs_url="/api/docs")


@lru_cache(maxsize=1)
def _catalog() -> Catalog:
    return load_catalog(CATALOG_DIR)


class IntakeRequest(BaseModel):
    domain: str
    data_type: str
    purpose: str
    privacy: str
    compute: str | None = None
    expertise: str | None = None
    expected_rows: int | None = None
    variable_types: list[str] = Field(default_factory=list)
    preserves: list[str] = Field(default_factory=list)
    require_open_license: bool | None = None
    needs_governance_evidence: bool | None = None

    def to_intake(self) -> Intake:
        return Intake(**self.model_dump())


@app.get("/api/taxonomy")
def taxonomy() -> dict:
    cat = _catalog()
    return {
        **cat.taxonomy,
        "privacy": ["not_required", "required"],
        "counts": {
            "methods": len(cat.generation_methods()),
            "frameworks": len(cat.frameworks()),
            "datasets": len(cat.datasets),
        },
        "covered_data_types": cat.covered_data_types(),
    }


@app.get("/api/methods")
def methods(q: str | None = None, family: str | None = None) -> dict:
    """Browse the catalog by name, alias, id or family. Frameworks included."""
    found = search_methods(_catalog().methods, q or "", family)
    return {"methods": [_method_json(m) for m in found]}


@app.get("/api/datasets")
def datasets(domain: str | None = None, data_type: str | None = None,
             license: str | None = None) -> dict:
    found = _catalog().datasets
    if domain and domain != "any":
        found = [d for d in found
                 if domain in d.domains or "general" in d.domains]
    if data_type and data_type != "any":
        found = [d for d in found if data_type in d.data_types]
    if license and license != "any":
        found = [d for d in found if d.license == license]
    return {"datasets": [_dataset_json(d) for d in found]}


@app.post("/api/recommend")
def recommend(req: IntakeRequest) -> dict:
    cat = _catalog()
    intake = req.to_intake()
    # Rank deeply, then split. With many methods tying on the core four, a
    # hard cut at five buries whole families - which is how every
    # privacy-preserving method fell off a list it had not been excluded from.
    ranking: Ranking = rank(cat.generation_methods(), intake, top_n=24)
    top, rest = ranking.shortlist[:5], ranking.shortlist[5:]
    covered = cat.covers(intake.data_type)

    shortlist_json = [_candidate_json(c) for c in top]
    if llm.available():
        for c, j in zip(top, shortlist_json):
            j["narration"] = llm.narrate(explain(c), c.method, intake)

    return {
        "shortlist": shortlist_json,
        "also_ranked": [_candidate_json(c) for c in rest],
        "excluded": [
            {"id": e.method_id, "name": e.method_name, "reason": e.reason}
            for e in ranking.excluded
        ],
        "no_purpose_match": ranking.no_purpose_match,
        "covered": covered,
        "empty_message": (
            None if top
            else empty_result_message(intake, covered,
                                      cat.covered_data_types())
        ),
        "report_markdown": render_markdown(intake, _top_only(ranking, top),
                                           covered, cat.covered_data_types()),
        "report_html": render_html(intake, _top_only(ranking, top),
                                   covered, cat.covered_data_types()),
    }


def _build_id() -> str:
    """Short hash of the frontend sources, shown in the UI.

    Makes "are you looking at the current version?" answerable instead of
    guessable when the page is served through a caching proxy.
    """
    h = hashlib.sha256()
    for name in ("index.html", "style.css", "app.js"):
        h.update((WEB_DIR / name).read_bytes())
    return h.hexdigest()[:7]


def _page() -> str:
    """Inline CSS and JS into the page.

    Reverse proxies (HPC OnDemand, JupyterHub) serve apps under a path
    prefix, where an absolute asset path like /static/style.css resolves to
    the portal root and 404s - leaving an unstyled, unreadable page. Having
    no asset paths at all removes the failure mode entirely.
    """
    html = (WEB_DIR / "index.html").read_text()
    css = (WEB_DIR / "style.css").read_text()
    js = (WEB_DIR / "app.js").read_text()
    return (html.replace("/*__CSS__*/", css)
                .replace("/*__JS__*/", js)
                .replace("__BUILD__", _build_id()))


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    # The page carries its own CSS and JS, so a cached copy pins the whole
    # interface to an old version. Never cache it.
    return HTMLResponse(_page(), headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    })


# kept so a direct link still works, but the page does not depend on it
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class ValidateRequest(BaseModel):
    answers: dict


@app.post("/api/validate")
def validate(req: ValidateRequest) -> dict:
    errors, entry = validate_method(req.answers, _catalog().taxonomy,
                                    {m.id for m in _catalog().methods})
    return {"errors": errors, "yaml": to_yaml(entry) if entry else None}
