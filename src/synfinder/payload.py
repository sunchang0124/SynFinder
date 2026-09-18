"""Turn engine results into JSON payloads.

Deliberately free of FastAPI: the browser build runs this same code under
Pyodide, where FastAPI is not available. Keeping it here means the hosted
static page and the served API cannot produce different payloads.
"""
from __future__ import annotations

from .explain import explain
from .ranking import Ranking

def _top_only(ranking: Ranking, top: list) -> Ranking:
    """The exported report carries the shortlist, not the long tail."""
    return Ranking(shortlist=top, excluded=ranking.excluded,
                   no_purpose_match=ranking.no_purpose_match)


def _dataset_json(d) -> dict:
    return {
        "id": d.id, "name": d.name, "n_records": d.n_records,
        "license": d.license, "access_conditions": d.access_conditions,
        "domains": d.domains, "data_types": d.data_types,
        "generated_by": d.generated_by,
        "realism_caveats": d.realism_caveats,
        "link": d.links.docs or d.links.code,
    }


def _candidate_json(c) -> dict:
    e = explain(c)
    m = c.method
    return {
        "id": m.id, "name": m.name, "family": m.family,
        "fit": round(c.fit, 4),
        "why_fits": e.why_fits,
        "weakness": e.weakness,
        "caveats": e.caveats,
        "evaluation": e.evaluation,
        "formal_dp": m.formal_dp,
        "compute": m.compute,
        "expertise": m.expertise,
        "license": m.license,
        "language": m.language,
        "last_updated": m.last_updated,
        "maintained": m.maturity.maintained,
        "quality": m.maturity.implementation_quality,
        "links": {"paper": m.links.paper, "code": m.links.code,
                  "docs": m.links.docs},
        "axes": [{"axis": a.axis, "score": round(a.score, 3),
                  "weight": a.weight, "note": a.note} for a in c.axes],
        "preview": (
            {"format": m.output_preview.format,
             "note": m.output_preview.note,
             "body": m.output_preview.preview}
            if m.output_preview else None
        ),
    }


