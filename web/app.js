const $ = (s, r = document) => r.querySelector(s);

// Behind a proxy the app may live under a path prefix. Resolve every API
// call against the page's own directory rather than the server root.
const API = new URL(".", location.href).href;
// Words that should stay upper-case rather than being title-cased.
const ACRONYM = {
  gan: "GAN", vae: "VAE", llm: "LLM", dp: "DP", ssh: "SSH", cpu: "CPU",
  gpu: "GPU", ml: "ML", ok: "OK", csv: "CSV", ehr: "EHR", id: "ID",
};
// A few taxonomy terms read badly when merely capitalised.
const LABEL = {
  cpu_fine: "CPU is fine",
  gpu_recommended: "GPU recommended",
  gpu_required: "GPU required",
  deidentified_ok: "De-identified is enough",
  formal_dp_required: "Formal differential privacy required",
  none: "No specific requirement",
  tabular_cross_sectional: "Tabular, one row per subject",
  tabular_longitudinal: "Tabular, repeated measures",
  coded_event_sequences: "Coded event sequences (EHR visits)",
  survey_instrument: "Survey or questionnaire",
  ml_augmentation: "Machine learning augmentation",
};
const pretty = s => {
  if (LABEL[s]) return LABEL[s];
  const words = String(s).split("_").map(w => ACRONYM[w.toLowerCase()] || w);
  const first = words[0];
  const head = ACRONYM[String(first).toLowerCase()]
    ? first
    : first.charAt(0).toUpperCase() + first.slice(1);
  return [head, ...words.slice(1)].join(" ");
};
const esc = s => String(s).replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let TAX = null;
let lastReport = null;

/* ---------- theme ---------- */
const root = document.documentElement;
try {
  const saved = localStorage.getItem("synfinder-theme");
  if (saved) root.dataset.theme = saved;
  else if (matchMedia("(prefers-color-scheme: light)").matches) root.dataset.theme = "light";
} catch (e) { /* private mode: keep the default */ }
$("#themeToggle").onclick = () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  try { localStorage.setItem("synfinder-theme", root.dataset.theme); } catch (e) {}
};

/* ---------- tabs ---------- */
document.querySelectorAll(".tab").forEach(t => {
  t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("is-active", x === t));
    $("#view-find").classList.toggle("hidden", t.dataset.view !== "find");
    $("#view-browse").classList.toggle("hidden", t.dataset.view !== "browse");
    if (t.dataset.view === "browse") loadDatasets();
  };
});

/* ---------- form scaffolding ---------- */
function fill(sel, values, { blank = null } = {}) {
  const el = $(sel);
  el.innerHTML = (blank ? [`<option value="">${blank}</option>`] : [])
    .concat(values.map(v => `<option value="${esc(v)}">${esc(pretty(v))}</option>`))
    .join("");
}
function chips(sel, values) {
  $(sel).innerHTML = values
    .map(v => `<span class="chip" data-v="${esc(v)}">${esc(pretty(v))}</span>`).join("");
  $(sel).querySelectorAll(".chip").forEach(c =>
    c.onclick = () => c.classList.toggle("on"));
}
const chosen = sel => [...$(sel).querySelectorAll(".chip.on")].map(c => c.dataset.v);

async function boot() {
  TAX = await (await fetch(API + "api/taxonomy")).json();
  fill("#domain", TAX.domains);
  fill("#data_type", TAX.data_types);
  fill("#purpose", TAX.purposes);
  fill("#privacy", TAX.privacy);
  fill("#compute", TAX.compute, { blank: "not specified" });
  fill("#expertise", TAX.expertise, { blank: "not specified" });
  chips("#variable_types", TAX.variable_types);
  chips("#preserves", TAX.preserves);
  fill("#b_domain", ["any", ...TAX.domains]);
  fill("#b_data_type", ["any", ...TAX.data_types]);
  $("#b_domain").onchange = $("#b_data_type").onchange = loadDatasets;
  const c = TAX.counts;
  $("#catalogCount").textContent =
    `${c.methods} methods · ${c.frameworks} frameworks · ${c.datasets} datasets`;
  $("#brandSub").textContent = "synthetic data, chosen well";
}

/* ---------- submit ---------- */
$("#intakeForm").onsubmit = async e => {
  e.preventDefault();
  const btn = $("#submitBtn");
  btn.classList.add("is-loading");
  const rows = parseInt($("#expected_rows").value, 10);
  const body = {
    domain: $("#domain").value,
    data_type: $("#data_type").value,
    purpose: $("#purpose").value,
    privacy: $("#privacy").value,
    compute: $("#compute").value || null,
    expertise: $("#expertise").value || null,
    expected_rows: Number.isFinite(rows) && rows > 0 ? rows : null,
    variable_types: chosen("#variable_types"),
    preserves: chosen("#preserves"),
    require_open_license: $("#require_open_license").checked || null,
    needs_governance_evidence: $("#needs_governance_evidence").checked || null,
  };
  try {
    const res = await fetch(API + "api/recommend", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    render(await res.json());
  } catch (err) {
    $("#results").innerHTML =
      `<div class="notice"><b>Something went wrong.</b><br>${esc(err.message)}</div>`;
  } finally {
    btn.classList.remove("is-loading");
    if (innerWidth < 900) $("#results").scrollIntoView({ behavior: "smooth" });
  }
};


/* ---------- preview rendering ---------- */
// Minimal CSV split that respects double-quoted fields.
function splitCsv(line) {
  const out = []; let cur = "", q = false;
  for (const ch of line) {
    if (ch === '"') q = !q;
    else if (ch === "," && !q) { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out.map(s => s.trim());
}

function table(head, rows) {
  return `<div class="tbl-wrap"><table class="tbl">
    <thead><tr>${head.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
}

// CSV text, possibly broken into "# caption" sections, becomes real tables.
function csvTables(body) {
  const blocks = []; let caption = null, lines = [];
  const flush = () => {
    if (lines.length > 1) blocks.push({ caption, head: splitCsv(lines[0]),
                                        rows: lines.slice(1).map(splitCsv) });
    else if (lines.length === 1) blocks.push({ caption, pre: lines[0] });
    lines = [];
  };
  for (const raw of body.split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    if (line.trim().startsWith("#")) { flush(); caption = line.replace(/^\s*#\s*/, ""); }
    else lines.push(line.trim());
  }
  flush();
  return blocks.map(b =>
    (b.caption ? `<p class="tbl-cap">${esc(b.caption)}</p>` : "") +
    (b.pre ? `<pre>${esc(b.pre)}</pre>` : table(b.head, b.rows))
  ).join("");
}

// Whitespace-aligned columns (genotype matrices).
function spacedTable(body) {
  const rows = body.split("\n").filter(l => l.trim()).map(l => l.trim().split(/\s{1,}/));
  if (rows.length < 2) return `<pre>${esc(body)}</pre>`;
  return table(rows[0], rows.slice(1));
}

// "key   value" specification blocks.
function specTable(body) {
  const rows = [];
  for (const raw of body.split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    const m = line.match(/^(\S+)\s{2,}(.*)$/);
    if (m) rows.push([m[1], m[2]]);
    else if (rows.length) rows[rows.length - 1][1] += " " + line.trim();
  }
  if (!rows.length) return `<pre>${esc(body)}</pre>`;
  return table(["Field", "Value"], rows);
}

function previewBody(p) {
  const body = p.body.replace(/\s+$/, "");
  try {
    if (p.format === "tabular_csv" || p.format === "graph_edgelist") return csvTables(body);
    if (p.format === "genomic_matrix") return spacedTable(body);
    if (p.format === "image_spec") return specTable(body);
  } catch (e) { /* fall through to the raw text */ }
  return `<pre>${esc(body)}</pre>`;
}

/* ---------- rendering ---------- */
const CIRC = 2 * Math.PI * 26;

function ring(fit) {
  const off = CIRC * (1 - fit);
  return `<div class="ring">
    <svg width="62" height="62" viewBox="0 0 62 62">
      <defs><linearGradient id="fitGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="var(--accent)"/><stop offset="1" stop-color="var(--accent-2)"/>
      </linearGradient></defs>
      <circle class="track" cx="31" cy="31" r="26"/>
      <circle class="val" cx="31" cy="31" r="26"
              stroke-dasharray="${CIRC.toFixed(1)}" stroke-dashoffset="${CIRC.toFixed(1)}"
              data-off="${off.toFixed(1)}"/>
    </svg>
    <b>${Math.round(fit * 100)}%</b>
  </div>`;
}

function badges(m) {
  const b = [];
  b.push(`<span class="badge">${esc(pretty(m.family))}</span>`);
  if (m.formal_dp) b.push(`<span class="badge dp">formal DP</span>`);
  if (m.compute === "gpu_required") b.push(`<span class="badge gpu">GPU required</span>`);
  else if (m.compute === "gpu_recommended") b.push(`<span class="badge">GPU recommended</span>`);
  else b.push(`<span class="badge">runs on CPU</span>`);
  b.push(`<span class="badge">${esc(m.expertise)} expertise</span>`);
  if (!m.maintained) b.push(`<span class="badge stale">unmaintained</span>`);
  b.push(`<span class="badge">${esc(m.license)}</span>`);
  return `<div class="badges">${b.join("")}</div>`;
}

function axes(m) {
  if (!m.axes.length) return "";
  return `<div class="axes">${m.axes.map(a => `
    <div class="axis"><span>${esc(pretty(a.axis))}</span>
      <span class="bar"><i style="width:0" data-w="${Math.round(a.score * 100)}"></i></span>
      <span class="v">${a.score.toFixed(2)}</span></div>`).join("")}</div>`;
}

function card(m, i) {
  const links = Object.entries(m.links)
    .filter(([, v]) => v)
    .map(([k, v]) => `<a href="${esc(v)}" target="_blank" rel="noopener">${k}</a>`).join("");
  return `<article class="card" style="animation-delay:${i * 60}ms">
    <div class="card-top">
      <div class="card-title"><h3>${esc(m.name)}</h3>${badges(m)}</div>
      ${ring(m.fit)}
    </div>
    ${m.why_fits.length ? `<p class="why"><span class="dim">Why it fits —</span> ${esc(m.why_fits.join("; "))}.</p>` : ""}
    ${m.weakness ? `<p class="why"><span class="dim">Weaker on —</span> it ${esc(m.weakness)}.</p>` : ""}
    ${m.caveats.length ? `<div class="callout"><span class="k">Watch out</span>${m.caveats.map(esc).join(" ")}</div>` : ""}
    ${m.evaluation.length ? `<div class="callout info"><span class="k">How to check it worked</span>${m.evaluation.map(esc).join("; ")}.</div>` : ""}
    ${m.preview ? `<details class="disc"><summary>What the output looks like</summary>
        <p class="disclaimer">Illustrative of the output format — not generated by this method.</p>
        <p class="why">${esc(m.preview.note)}</p>
        ${previewBody(m.preview)}</details>` : ""}
    <details class="disc"><summary>How this score was reached</summary>${axes(m)}</details>
    ${links ? `<div class="links">${links}</div>` : ""}
  </article>`;
}

function datasetBlock(d) {
  return `<div class="lead-item">
    <h4>${esc(d.name)}</h4>
    <div class="meta-row">
      <span class="badge">${esc(d.n_records)}</span>
      <span class="badge">${esc(d.license)}</span>
      ${d.generated_by ? `<span class="badge">via ${esc(d.generated_by)}</span>` : ""}
    </div>
    <p class="why" style="margin-top:9px"><span class="dim">Access —</span> ${esc(d.access_conditions)}</p>
    ${d.realism_caveats.map(c => `<div class="callout"><span class="k">Caveat</span>${esc(c)}</div>`).join("")}
    ${d.link ? `<div class="links"><a href="${esc(d.link)}" target="_blank" rel="noopener">where to get it</a></div>` : ""}
  </div>`;
}

function animate(scope) {
  requestAnimationFrame(() => {
    scope.querySelectorAll(".ring .val").forEach(c =>
      c.style.strokeDashoffset = c.dataset.off);
    scope.querySelectorAll(".axis .bar i").forEach(b =>
      b.style.width = b.dataset.w + "%");
  });
}

function render(r) {
  const out = [];

  if (r.datasets.length) {
    out.push(`<section class="lead">
      <h3><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 8v13H3V8M1 3h22v5H1zM10 12h4"/></svg>
        You may not need to generate anything</h3>
      <p>These synthetic datasets already exist and match what you described.</p>
      ${r.datasets.map(datasetBlock).join("")}</section>`);
  }

  if (r.no_purpose_match && r.shortlist.length) {
    out.push(`<div class="notice"><b>Nothing in this catalog is intended for what you asked.</b>
      The entries below are the closest on your other constraints, but none is designed for
      that purpose. Treat this as a gap rather than an answer.</div>`);
  }

  if (!r.shortlist.length) {
    out.push(`<div class="notice ${r.covered ? "" : "flat"}">${esc(r.empty_message || "")}</div>`);
  } else {
    out.push(`<p class="section-label">Recommended methods</p>`);
    out.push(r.shortlist.map(card).join(""));
  }

  if (r.excluded.length) {
    out.push(`<details class="ruled"><summary style="cursor:pointer;font-size:13px;color:var(--dim)">
      Why ${r.excluded.length} other method${r.excluded.length === 1 ? "" : "s"} ${r.excluded.length === 1 ? "was" : "were"} ruled out</summary>
      <ul>${r.excluded.map(e => `<li><b>${esc(e.name)}</b><span>${esc(e.reason)}</span></li>`).join("")}</ul>
    </details>`);
  }

  out.push(`<div class="dl-row">
    <button class="dl" id="dlMd">Download report (Markdown)</button>
    <button class="dl" id="dlHtml">Download report (HTML)</button></div>`);

  const el = $("#results");
  el.innerHTML = out.join("");
  lastReport = r;
  animate(el);

  const save = (text, name, type) => {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  };
  $("#dlMd").onclick = () =>
    save(lastReport.report_markdown, "synfinder-report.md", "text/markdown");
  $("#dlHtml").onclick = () =>
    save(lastReport.report_html, "synfinder-report.html", "text/html");
}

/* ---------- dataset browse ---------- */
async function loadDatasets() {
  const q = new URLSearchParams({
    domain: $("#b_domain").value, data_type: $("#b_data_type").value,
  });
  const { datasets } = await (await fetch(API + "api/datasets?" + q)).json();
  $("#datasetResults").innerHTML = datasets.length
    ? `<p class="section-label">${datasets.length} dataset${datasets.length === 1 ? "" : "s"}</p>`
      + `<section class="lead">${datasets.map(datasetBlock).join("")}</section>`
    : `<div class="empty-state"><h3>Nothing here yet</h3>
       <p>No dataset in the registry matches those filters. The registry is young —
       contributing one is a pull request.</p></div>`;
}

boot();
