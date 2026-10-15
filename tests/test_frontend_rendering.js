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
load("/* ---------- submission helpers ---------- */", "/* ---------- submission ---------- */",
     ["collectLines", "issueUrl", "ISSUE_BASE"]);

load("/* ---------- method browse ---------- */", "/* ---------- dataset browse ---------- */",
     ["methodCard"]);

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

console.log("submission helpers");
check("lines split and blanks dropped",
  JSON.stringify(collectLines(" a \n\n b\n")) === JSON.stringify(["a", "b"]));
const answers = { name: "My Method", domains: ["biomedical"], data_types: ["images"],
  compute: "cpu_fine", expertise: "low", formal_dp: false,
  caveats: ["It breaks."], preview_body: "x,y\n1,2", paper: "doi:1", code: "https://github.com/a/b" };
const url = issueUrl(answers, "id: my_method\n");
check("issue url targets the method form", url.startsWith(ISSUE_BASE) && url.includes("template=new_method.yml"));
check("title is prefilled", decodeURIComponent(url).includes("title=[method] My Method"));
check("yaml is carried", decodeURIComponent(url).includes("entry_yaml=id: my_method"));
check("authorship is not prefilled", !url.includes("authorship="));
const longBody = "age,sex,bmi\n" + "54,F,23.1\n".repeat(800);
const longUrl = issueUrl(Object.assign({}, answers, { preview_body: longBody }),
  "id: x\n" + "preview: |\n" + "  row\n".repeat(5000) + longBody);
check("url stays under the GitHub limit", longUrl.length < 8000);
check("truncation is announced", decodeURIComponent(longUrl).includes("truncated"));
let emojiOk = true, emojiUrl = "";
try {
  emojiUrl = issueUrl(Object.assign({}, answers, { preview_body: "😀".repeat(3000) }),
    "😀".repeat(3000));
  decodeURIComponent(emojiUrl);
} catch (err) { emojiOk = false; }
check("emoji at the cut boundary does not throw", emojiOk && emojiUrl.length < 8000);

console.log("method cards");
const mc = methodCard({ id: "synthea", name: "Synthea", family: "agent_simulation",
  verified: "Not yet verified", domains: ["biomedical"], data_types: ["coded_event_sequences"],
  purposes: ["education"], caveats: ["Only a simulation."], evaluation: [],
  formal_dp: false, compute: "cpu_fine", license: "Apache-2.0", language: "java",
  maintained: true, quality: "production_ready", is_framework: false,
  links: { code: "https://github.com/synthetichealth/synthea", paper: null, docs: null } });
check("card shows the name", mc.includes("Synthea"));
check("card shows the verification label", mc.includes("Not yet verified"));
check("card shows the family", mc.includes("Agent simulation"));
check("card shows caveats", mc.includes("Only a simulation."));
check("card links the code", mc.includes("synthetichealth/synthea"));
check("card escapes html", !methodCard({ id: "x", name: "<b>", family: "gan", verified: "Not yet verified",
  domains: [], data_types: [], purposes: [], caveats: [], evaluation: [], links: {} }).includes("<b>"));

console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
