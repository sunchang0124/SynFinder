/* Static-hosting bootstrap.
 *
 * Runs the real synfinder package in the browser via Pyodide, and exposes the
 * same three calls the HTTP API provides. app.js talks to whichever backend is
 * present, so the rendering code is identical either way and the ranking logic
 * exists in exactly one place: Python.
 */
window.SYNFINDER_STATIC = true;

window.synReady = (async () => {
  const results = document.getElementById("results");
  const idle = results ? results.innerHTML : "";
  const status = (msg) => {
    if (results) results.innerHTML =
      `<div class="empty-state"><h3>Starting the engine</h3><p>${msg}</p></div>`;
  };
  // Every same-origin asset is fetched with the build id, so a browser that
  // cached an earlier deployment can never mix an old engine with a new
  // catalog (or the other way round).
  const build = window.SYNFINDER_BUILD || "dev";
  const fetchOk = async (url) => {
    const r = await fetch(`${url}?v=${build}`, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    return r;
  };
  status("Loading Python in your browser. First visit takes a few seconds; after that it is cached.");

  const py = await loadPyodide();
  await py.loadPackage("micropip");
  const micropip = py.pyimport("micropip");
  status("Installing the catalog engine…");
  await micropip.install(["pydantic", "pyyaml"]);
  const wheel = window.SYNFINDER_WHEEL;
  const bytes = new Uint8Array(await (await fetchOk(wheel)).arrayBuffer());
  py.FS.writeFile(`/tmp/${wheel}`, bytes);
  await micropip.install(`emfs:/tmp/${wheel}`);

  status("Loading the catalog…");
  const catalog = await (await fetchOk("catalog.json")).json();
  const n = Object.keys(catalog).length;
  if (!n) throw new Error("catalog.json is empty");
  py.FS.mkdirTree("/catalog");
  for (const [rel, text] of Object.entries(catalog)) {
    const dir = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
    if (dir) py.FS.mkdirTree(`/catalog/${dir}`);
    py.FS.writeFile(`/catalog/${rel}`, text);
  }
  status(`Validating ${n} catalog entries…`);
  py.runPython(`
import json, pathlib
root = pathlib.Path("/catalog")

from synfinder.catalog import load_catalog, search_methods
from synfinder.intake import Intake
from synfinder.ranking import rank
from synfinder.report import (empty_result_message, render_html,
                              render_markdown)
from synfinder.payload import _candidate_json, _dataset_json, _method_json

CAT = load_catalog(root)

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
    ranking = rank(CAT.generation_methods(), intake)
    top = ranking.shortlist
    covered = CAT.covers(intake.data_type)
    trimmed = ranking
    return json.dumps({
        "shortlist": [_candidate_json(c) for c in top],
        "excluded": [{"id": e.method_id, "name": e.method_name,
                      "reason": e.reason} for e in ranking.excluded],
        "no_purpose_match": ranking.no_purpose_match,
        "covered": covered,
        "empty_message": (None if top else empty_result_message(
            intake, covered, CAT.covered_data_types())),
        "report_markdown": render_markdown(intake, trimmed, covered,
                                           CAT.covered_data_types()),
        "report_html": render_html(intake, trimmed, covered,
                                   CAT.covered_data_types()),
    })

def methods_json(q, family):
    found = search_methods(CAT.methods, q or "", family)
    return json.dumps({"methods": [_method_json(m) for m in found]})

def datasets_json(domain, data_type):
    found = CAT.datasets
    if domain and domain != "any":
        found = [d for d in found if domain in d.domains or "general" in d.domains]
    if data_type and data_type != "any":
        found = [d for d in found if data_type in d.data_types]
    return json.dumps({"datasets": [_dataset_json(d) for d in found]})

from synfinder.contribute import to_yaml, validate_method

def validate_json(payload):
    answers = json.loads(payload)
    errors, entry = validate_method(answers, CAT.taxonomy,
                                    {m.id for m in CAT.methods})
    return json.dumps({"errors": errors,
                       "yaml": to_yaml(entry) if entry else None})
`);

  // Put the panel back the way the page shipped it; otherwise the last
  // progress line stays on screen and the ready engine looks stuck.
  if (results) results.innerHTML = idle;
  return {
    taxonomy: () => JSON.parse(py.globals.get("taxonomy_json")()),
    recommend: (body) =>
      JSON.parse(py.globals.get("recommend_json")(JSON.stringify(body))),
    methods: (q, family) =>
      JSON.parse(py.globals.get("methods_json")(q, family)),
    datasets: (domain, dataType) =>
      JSON.parse(py.globals.get("datasets_json")(domain, dataType)),
    validate: (answers) =>
      JSON.parse(py.globals.get("validate_json")(JSON.stringify(answers))),
  };
})();
