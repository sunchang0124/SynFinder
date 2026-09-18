/* Static-hosting bootstrap.
 *
 * Runs the real synfinder package in the browser via Pyodide, and exposes the
 * same three calls the HTTP API provides. app.js talks to whichever backend is
 * present, so the rendering code is identical either way and the ranking logic
 * exists in exactly one place: Python.
 */
window.SYNFINDER_STATIC = true;

window.synReady = (async () => {
  const status = (msg) => {
    const el = document.getElementById("results");
    if (el) el.innerHTML =
      `<div class="empty-state"><h3>Starting the engine</h3><p>${msg}</p></div>`;
  };
  status("Loading Python in your browser. First visit takes a few seconds; after that it is cached.");

  const py = await loadPyodide();
  await py.loadPackage("micropip");
  const micropip = py.pyimport("micropip");
  status("Installing the catalog engine…");
  await micropip.install(["pydantic", "pyyaml"]);
  await micropip.install(window.SYNFINDER_WHEEL);

  status("Loading the catalog…");
  const catalog = await (await fetch("catalog.json")).json();
  py.globals.set("catalog_files", py.toPy(catalog));
  py.runPython(`
import json, pathlib
root = pathlib.Path("/catalog")
for rel, text in catalog_files.items():
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

from synfinder.catalog import load_catalog
from synfinder.datasets import match_datasets
from synfinder.intake import Intake
from synfinder.ranking import load_weights, rank
from synfinder.report import (empty_result_message, render_html,
                              render_markdown)
from synfinder.payload import _candidate_json, _dataset_json, _top_only

CAT = load_catalog(root)
W = load_weights(root / "weights.yaml")

def taxonomy_json():
    return json.dumps({**CAT.taxonomy,
        "privacy": ["not_required", "required"],
        "counts": {"methods": len(CAT.generation_methods()),
                   "frameworks": len(CAT.frameworks()),
                   "datasets": len(CAT.datasets)},
        "covered_data_types": CAT.covered_data_types()})

def recommend_json(payload):
    req = json.loads(payload)
    intake = Intake(**req)
    ranking = rank(CAT.generation_methods(), intake, W, top_n=24)
    top, rest = ranking.shortlist[:5], ranking.shortlist[5:]
    matching = match_datasets(CAT.datasets, intake)
    covered = CAT.covers(intake.data_type)
    trimmed = _top_only(ranking, top)
    return json.dumps({
        "datasets": [_dataset_json(d) for d in matching],
        "shortlist": [_candidate_json(c) for c in top],
        "also_ranked": [_candidate_json(c) for c in rest],
        "excluded": [{"id": e.method_id, "name": e.method_name,
                      "reason": e.reason} for e in ranking.excluded],
        "no_purpose_match": ranking.no_purpose_match,
        "covered": covered,
        "empty_message": (None if top else empty_result_message(
            intake, covered, CAT.covered_data_types())),
        "report_markdown": render_markdown(intake, trimmed, matching, covered,
                                           CAT.covered_data_types()),
        "report_html": render_html(intake, trimmed, matching, covered,
                                   CAT.covered_data_types()),
    })

def datasets_json(domain, data_type):
    found = CAT.datasets
    if domain and domain != "any":
        found = [d for d in found if domain in d.domains or "general" in d.domains]
    if data_type and data_type != "any":
        found = [d for d in found if data_type in d.data_types]
    return json.dumps({"datasets": [_dataset_json(d) for d in found]})
`);

  return {
    taxonomy: () => JSON.parse(py.globals.get("taxonomy_json")()),
    recommend: (body) =>
      JSON.parse(py.globals.get("recommend_json")(JSON.stringify(body))),
    datasets: (domain, dataType) =>
      JSON.parse(py.globals.get("datasets_json")(domain, dataType)),
  };
})();
