/* Headless checks for the pure rendering helpers in web/app.js.
   Run: node tests/test_frontend_rendering.js */
const fs = require("fs");
const path = require("path");
const src = fs.readFileSync(path.join(__dirname, "..", "web", "app.js"), "utf8");
globalThis.esc = s => String(s).replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const slice = (a, b) => src.slice(src.indexOf(a), src.indexOf(b));
// eval'd `const` does not leak to module scope, so export explicitly.
const load = (a, b, names) =>
  (0, eval)(slice(a, b) + names.map(n => `;globalThis.${n}=${n};`).join(""));
load("// Words that should stay upper-case", "/* ---------- theme ---------- */",
     ["pretty"]);
load("/* ---------- preview rendering ---------- */", "/* ---------- rendering ---------- */",
     ["previewBody", "table", "splitCsv"]);

let failed = 0;
const check = (name, cond) => {
  console.log((cond ? "  ok   " : "  FAIL ") + name);
  if (!cond) failed++;
};

console.log("label capitalisation");
check("first letter capitalised", pretty("benchmarking") === "Benchmarking");
check("acronyms stay upper-case", pretty("ml_augmentation").startsWith("Machine"));
check("family acronym", pretty("gan") === "GAN");
check("underscores become spaces", pretty("joint_correlations") === "Joint correlations");

console.log("preview tables");
const csv = "patient_id,age,sex\ns0001,54,F\ns0002,38,M\n";
const out = previewBody({ format: "tabular_csv", body: csv });
check("csv becomes a table", out.includes("<table") && out.includes("<th>patient_id</th>"));
check("csv rows become cells", out.includes("<td>s0001</td>"));
check("no raw comma dump survives", !out.includes("s0001,54,F"));

const gen = "variant_id  chrom  pos\nrs0001   1   752721\n";
check("genotype matrix becomes a table",
  previewBody({ format: "genomic_matrix", body: gen }).includes("<th>variant_id</th>"));

const spec = "format      NIfTI\ndimensions  160 x 224 x 160 voxels\n";
check("image spec becomes key/value rows",
  previewBody({ format: "image_spec", body: spec }).includes("<td>dimensions</td>"));

check("event sequences stay preformatted",
  previewBody({ format: "event_sequence", body: "patient s0001\n  visit 1" }).includes("<pre>"));

console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
