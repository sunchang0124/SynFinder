const $ = (s, r = document) => r.querySelector(s);

// Behind a proxy the app may live under a path prefix. Resolve every API
// call against the page's own directory rather than the server root.
const API = new URL(".", location.href).href;

// Two backends, one renderer. Served by FastAPI the calls go over HTTP; on
// static hosting boot.js runs the same Python package in the browser. The
// ranking logic therefore exists in exactly one place either way.
const backend = {
  async taxonomy() {
    if (window.SYNFINDER_STATIC) return (await window.synReady).taxonomy();
    return (await fetch(API + "api/taxonomy")).json();
  },
  async recommend(body) {
    if (window.SYNFINDER_STATIC) return (await window.synReady).recommend(body);
    const res = await fetch(API + "api/recommend", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  async methods(q, family) {
    if (window.SYNFINDER_STATIC) return (await window.synReady).methods(q, family);
    const params = new URLSearchParams({ q, family });
    return (await fetch(API + "api/methods?" + params)).json();
  },
  async datasets(domain, dataType) {
    if (window.SYNFINDER_STATIC) {
      return (await window.synReady).datasets(domain, dataType);
    }
    const q = new URLSearchParams({ domain, data_type: dataType });
    return (await fetch(API + "api/datasets?" + q)).json();
  },
  async validate(answers) {
    if (window.SYNFINDER_STATIC) return (await window.synReady).validate(answers);
    const res = await fetch(API + "api/validate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
// Words that should stay upper-case rather than being title-cased.
const LANG = {
  python: "Python", r: "R", julia: "Julia", cpp: "C/C++", java: "Java",
  javascript: "JavaScript", multiple: "Multiple languages", other: "Other",
};
const ACRONYM = {
  gan: "GAN", vae: "VAE", llm: "LLM", dp: "DP", cpu: "CPU",
  gpu: "GPU", ml: "ML", ok: "OK", csv: "CSV", ehr: "EHR", id: "ID",
};
// A few taxonomy terms read badly when merely capitalised.
const LABEL = {
  cpu_fine: "CPU is fine",
  gpu_recommended: "GPU recommended",
  gpu_required: "GPU required",
  not_required: "Not required — show me everything",
  required: "Required — the method must specify privacy measures",
  tabular_cross_sectional: "Tabular, one row per subject",
  tabular_longitudinal: "Tabular, repeated measures",
  coded_event_sequences: "Coded event sequences (EHR visits)",
  ml_augmentation: "Machine learning augmentation",
  single_cell_omics: "Single-cell omics",
  genomic: "Genomic (genotypes / variants)",
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
const VIEWS = ["find", "browse", "submit", "search"];
document.querySelectorAll(".tab").forEach(t => {
  t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("is-active", x === t));
    VIEWS.forEach(v => $("#view-" + v).classList.toggle("hidden", t.dataset.view !== v));
    if (t.dataset.view === "browse") loadDatasets();
    if (t.dataset.view === "search") loadMethods();
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
  TAX = await backend.taxonomy();
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
  fill("#s_family", TAX.families);
  chips("#s_domains", TAX.domains);
  chips("#s_data_types", TAX.data_types);
  chips("#s_variable_types", TAX.variable_types);
  fill("#s_compute", TAX.compute);
  chips("#s_purposes", TAX.purposes);
  chips("#s_preserves", TAX.preserves);
  fill("#s_expertise", TAX.expertise);
  fill("#s_quality", TAX.implementation_quality);
  fill("#s_preview_format", TAX.preview_formats);
  $("#b_domain").onchange = $("#b_data_type").onchange = loadDatasets;
  fill("#m_family", ["any", ...TAX.families]);
  $("#m_family").onchange = loadMethods;
  let pending;
  $("#m_query").oninput = () => { clearTimeout(pending); pending = setTimeout(loadMethods, 150); };
  const c = TAX.counts;
  $("#catalogCount").textContent =
    `${c.methods} methods · ${c.frameworks} frameworks · ${c.datasets} datasets`;
  $("#buildId").textContent = "build __BUILD__";
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
    render(await backend.recommend(body));
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
function bullets(heading, items, variant) {
  if (!items.length) return "";
  const body = items.length === 1
    ? `<p>${esc(items[0])}</p>`
    : `<ul>${items.map(i => `<li>${esc(i)}</li>`).join("")}</ul>`;
  return `<div class="callout${variant}"><span class="k">${esc(heading)}</span>${body}</div>`;
}

function badges(m) {
  const b = [];
  b.push(`<span class="badge">${esc(pretty(m.family))}</span>`);
  if (m.formal_dp) b.push(`<span class="badge dp">formal DP</span>`);
  if (m.compute === "gpu_required") b.push(`<span class="badge gpu">GPU required</span>`);
  else if (m.compute === "gpu_recommended") b.push(`<span class="badge">GPU recommended</span>`);
  else b.push(`<span class="badge">runs on CPU</span>`);
  b.push(`<span class="badge">${esc(m.expertise)} expertise</span>`);
  if (m.language) b.push(`<span class="badge lang">${esc(LANG[m.language] || m.language)}</span>`);
  if (m.last_pushed) {
    // The repository's last push, in months, because it orders the list.
    const months = (Date.now() - new Date(m.last_pushed)) / (30.44 * 864e5);
    const cls = months > 36 ? "badge stale" : months > 24 ? "badge warnish" : "badge";
    const when = new Date(m.last_pushed).toLocaleDateString("en-GB", { month: "short", year: "numeric" });
    b.push(`<span class="${cls}" title="${esc(m.maintenance || "")}">updated ${esc(when)}</span>`);
  } else if (m.last_updated) {
    const age = new Date().getFullYear() - m.last_updated;
    const cls = age >= 3 ? "badge stale" : age >= 2 ? "badge warnish" : "badge";
    b.push(`<span class="${cls}">updated ${m.last_updated}</span>`);
  }
  if (!m.maintained) b.push(`<span class="badge stale">unmaintained</span>`);
  b.push(`<span class="badge ${m.verified.startsWith("Not") ? "stale" : "ok"}">${esc(m.verified)}</span>`);
  b.push(`<span class="badge">${esc(m.license)}</span>`);
  return `<div class="badges">${b.join("")}</div>`;
}

function card(m, i) {
  const links = Object.entries(m.links)
    .filter(([, v]) => v)
    .map(([k, v]) => `<a href="${esc(v)}" target="_blank" rel="noopener">${k}</a>`).join("");
  return `<article class="card" style="animation-delay:${i * 60}ms">
    <div class="card-top">
      <div class="card-title"><h3>${esc(m.name)}</h3>${badges(m)}</div>
    </div>
    ${m.why_fits.length ? `<p class="why"><span class="dim">Why it fits —</span> ${esc(m.why_fits.join("; "))}.</p>` : ""}
    ${m.narration ? `<p class="why"><span class="dim">In plain words —</span> ${esc(m.narration)} <span class="dim">Rewritten from the catalog text by an AI model; it cannot add claims.</span></p>` : ""}
    ${m.weakness ? `<p class="why"><span class="dim">Weaker on —</span> it ${esc(m.weakness)}.</p>` : ""}
    ${bullets("Watch out", m.caveats, "")}
    ${bullets("How to check it worked", m.evaluation, " info")}
    ${m.preview ? `<details class="disc"><summary>What the output looks like</summary>
        <p class="disclaimer">Illustrative of the output format — not generated by this method.</p>
        <p class="why">${esc(m.preview.note)}</p>
        ${previewBody(m.preview)}</details>` : ""}
    ${links ? `<div class="links">${links}</div>` : ""}
  </article>`;
}

function datasetBlock(d) {
  return `<div class="lead-item">
    <h4>${esc(d.name)}</h4>
    <div class="meta-row">
      <span class="badge">${esc(d.n_records)}</span>
      <span class="badge">${esc(d.license)}</span>
      <span class="badge ${d.verified.startsWith("Not") ? "stale" : "ok"}">${esc(d.verified)}</span>
      ${d.generated_by ? `<span class="badge">via ${esc(d.generated_by)}</span>` : ""}
    </div>
    <p class="why" style="margin-top:9px"><span class="dim">Access —</span> ${esc(d.access_conditions)}</p>
    ${d.realism_caveats.map(c => `<div class="callout"><span class="k">Caveat</span>${esc(c)}</div>`).join("")}
    ${d.link ? `<div class="links"><a href="${esc(d.link)}" target="_blank" rel="noopener">where to get it</a></div>` : ""}
  </div>`;
}

function render(r) {
  const out = [];

  if (r.no_purpose_match && r.shortlist.length) {
    out.push(`<div class="notice"><b>Nothing in this catalog is intended for what you asked.</b>
      The entries below are the closest on your other constraints, but none is designed for
      that purpose. Treat this as a gap rather than an answer.</div>`);
  }

  if (!r.shortlist.length) {
    out.push(`<div class="notice ${r.covered ? "" : "flat"}">${esc(r.empty_message || "")}</div>`);
  } else {
    out.push(`<p class="section-label">Recommended methods</p>
      <p class="order-note">Ordered by purpose first, then by how well each entry meets your optional answers, then by how recently its code was updated (within 6, 12, 24 or 36 months), then by name. Each card says why in words. Everything excluded is listed at the bottom with its reason.</p>`);
    out.push(r.shortlist.map(card).join(""));
  }

  if (r.also_ranked && r.also_ranked.length) {
    out.push(`<details class="ruled more-ranked"><summary>Show ${r.also_ranked.length} more ranked method${r.also_ranked.length === 1 ? "" : "s"}</summary>
      <div class="more-list">${r.also_ranked.map((m, i) => card(m, 0)).join("")}</div></details>`);
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

/* ---------- submission helpers ---------- */
const ISSUE_BASE = "https://github.com/sunchang0124/SynFinder/issues/new";
const MAX_ISSUE_URL = 7500;

// One item per non-blank line; the textarea fields use this.
function collectLines(text) {
  return String(text || "").split("\n").map(s => s.trim()).filter(Boolean);
}

// A prefilled GitHub issue. Field ids match .github/ISSUE_TEMPLATE/new_method.yml;
// the YAML goes into entry_yaml so a maintainer can save it as the catalog file.
// GitHub rejects very long URLs, so the YAML is cut with a note; the page also
// offers the full text through "Copy YAML".
function issueUrl(answers, yamlText) {
  const params = {
    template: "new_method.yml",
    title: `[method] ${answers.name || ""}`,
    name: answers.name || "",
    domains: (answers.domains || []).join(","),
    data_types: (answers.data_types || []).join(","),
    compute: answers.compute || "",
    expertise: answers.expertise || "",
    formal_dp: answers.formal_dp ? "yes - state the mechanism below" : "no",
    caveats: (answers.caveats || []).join("\n"),
    preview: answers.preview_body || "",
    links: [answers.paper, answers.code].filter(Boolean).join(" "),
  };
  const build = (yaml, p = params) => ISSUE_BASE + "?" +
    Object.entries({ ...p, entry_yaml: yaml })
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
  // Cut text to `keep` UTF-16 units without splitting a surrogate pair.
  const cut = (text, keep) => {
    if (keep > 0 && keep < text.length) {
      const c = text.charCodeAt(keep - 1);
      if (c >= 0xD800 && c <= 0xDBFF) keep -= 1;
    }
    return text.slice(0, Math.max(keep, 0));
  };
  let url = build(yamlText);
  if (url.length > MAX_ISSUE_URL) {
    // The YAML already carries the preview and caveats; cap the copies first.
    const capped = { ...params };
    for (const k of ["preview", "caveats"]) {
      capped[k] = capped[k].length > 300
        ? cut(capped[k], 300) + "\n... truncated (see entry_yaml below)" : capped[k];
    }
    params.preview = capped.preview; params.caveats = capped.caveats;
    url = build(yamlText);
    let keep = yamlText.length;
    while (url.length > MAX_ISSUE_URL && keep > 0) {
      keep = Math.floor(keep * 0.8);
      url = build(cut(yamlText, keep) + "\n# ... truncated for the URL; paste the full YAML from the app\n");
    }
  }
  return url;
}

/* ---------- submission ---------- */
function collectSubmission() {
  const v = id => $("#" + id).value.trim();
  return {
    id: v("s_id"), name: v("s_name"), family: v("s_family"),
    domains: chosen("#s_domains"), data_types: chosen("#s_data_types"),
    variable_types: chosen("#s_variable_types"),
    formal_dp: v("s_formal_dp") === "yes",
    dp_mechanism: v("s_formal_dp") === "yes" ? (v("s_dp_mechanism") || null) : null,
    compute: v("s_compute"), license: v("s_license"),
    purposes: chosen("#s_purposes"), preserves: chosen("#s_preserves"),
    expertise: v("s_expertise"), maintained: $("#s_maintained").checked,
    implementation_quality: v("s_quality"),
    caveats: collectLines(v("s_caveats")), evaluation: collectLines(v("s_evaluation")),
    preview_format: v("s_preview_format"), preview_note: v("s_preview_note"),
    preview_body: v("s_preview_body"),
    paper: v("s_paper") || null, code: v("s_code") || null,
    author: $("#s_author").checked,
  };
}

$("#submitForm").onsubmit = async e => {
  e.preventDefault();
  const answers = collectSubmission();
  const el = $("#submitResults");
  let result;
  try { result = await backend.validate(answers); }
  catch (err) { el.innerHTML = `<div class="notice"><b>Validation failed to run.</b><br>${esc(err.message)}</div>`; return; }
  if (result.errors.length) {
    el.innerHTML = `<div class="notice"><b>Not valid yet.</b><ul>${result.errors.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    return;
  }
  let url;
  try { url = issueUrl(answers, result.yaml); }
  catch (err) { el.innerHTML = `<div class="notice"><b>Could not prepare the GitHub issue.</b><br>${esc(err.message)}</div>`; return; }
  el.innerHTML = `<p class="section-label">Valid entry</p>
    <div class="card">
      <p class="why">This is the catalog file a maintainer will review.${answers.author ? " You declared authorship; thank you." : ""}</p>
      <pre id="yamlOut">${esc(result.yaml)}</pre>
      <div class="dl-row">
        <button class="dl" id="openIssue">Open a prefilled GitHub issue</button>
        <button class="dl" id="copyYaml">Copy YAML</button>
      </div>
      <p class="why dim">Prefer a pull request? Save the YAML as <code>catalog/methods/${esc(answers.id)}.yaml</code>, run <code>pytest</code>, and open the PR.</p>
    </div>`;
  $("#openIssue").onclick = () => window.open(url, "_blank", "noopener");
  $("#copyYaml").onclick = async () => {
    try { await navigator.clipboard.writeText(result.yaml); $("#copyYaml").textContent = "Copied"; }
    catch (err) { $("#copyYaml").textContent = "Select the text above and copy"; }
  };
};

/* ---------- catalog search ---------- */
function methodCard(m) {
  const links = Object.entries(m.links || {})
    .filter(([, v]) => v)
    .map(([k, v]) => `<a href="${esc(v)}" target="_blank" rel="noopener">${k}</a>`).join("");
  const tag = v => `<span class="badge">${esc(pretty(v))}</span>`;
  return `<div class="lead-item">
    <h4>${esc(m.name)}${m.is_framework ? ' <span class="badge">toolkit</span>' : ""}</h4>
    <div class="meta-row">
      <span class="badge">${esc(pretty(m.family))}</span>
      ${m.license ? `<span class="badge">${esc(m.license)}</span>` : ""}
      ${m.formal_dp ? '<span class="badge ok">formal DP</span>' : ""}
      ${m.requires_no_source_data ? '<span class="badge ok">no real data needed</span>' : ""}
      ${m.maintained === false ? '<span class="badge stale">not maintained</span>' : ""}
      <span class="badge ${String(m.verified).startsWith("Not") ? "stale" : "ok"}">${esc(m.verified)}</span>
    </div>
    ${m.data_types.length ? `<p class="why"><span class="dim">Data —</span> ${m.data_types.map(tag).join(" ")}</p>` : ""}
    ${m.purposes.length ? `<p class="why"><span class="dim">For —</span> ${m.purposes.map(tag).join(" ")}</p>` : ""}
    ${(m.caveats || []).map(c => `<div class="callout"><span class="k">Caveat</span>${esc(c)}</div>`).join("")}
    ${links ? `<div class="links">${links}</div>` : ""}
  </div>`;
}

async function loadMethods() {
  const { methods } = await backend.methods($("#m_query").value, $("#m_family").value);
  $("#methodResults").innerHTML = methods.length
    ? `<p class="section-label">${methods.length} entr${methods.length === 1 ? "y" : "ies"}</p>`
      + `<section class="lead">${methods.map(methodCard).join("")}</section>`
    : `<div class="empty-state"><h3>No entry matches</h3>
       <p>Nothing in the catalog is called that. Names, aliases, ids and families are
       searched. If the method exists, the Submit tab is the way to add it.</p></div>`;
}

/* ---------- dataset browse ---------- */
async function loadDatasets() {
  const { datasets } = await backend.datasets(
    $("#b_domain").value, $("#b_data_type").value);
  $("#datasetResults").innerHTML = datasets.length
    ? `<p class="section-label">${datasets.length} dataset${datasets.length === 1 ? "" : "s"}</p>`
      + `<section class="lead">${datasets.map(datasetBlock).join("")}</section>`
    : `<div class="empty-state"><h3>Nothing here yet</h3>
       <p>No dataset in the registry matches those filters. The registry is young —
       contributing one is a pull request.</p></div>`;
}

if (window.SYNFINDER_STATIC) {
  window.synReady.then(boot).catch(e => {
    document.getElementById("results").innerHTML =
      `<div class="notice"><b>The engine failed to start.</b><br>${esc(String(e))}</div>`;
  });
} else {
  boot();
}
