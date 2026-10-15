"""Check every catalog link and fetch the sources a purpose review needs.

    .venv/bin/python tools/review/fetch_sources.py            # all entries
    .venv/bin/python tools/review/fetch_sources.py ctgan tvae # a few

Writes review/sources/<id>.json (git-ignored) and review/links.md.
Network only; no judgement lives here.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from synfinder.catalog import load_catalog  # noqa: E402
from synfinder.repometa import github_slug  # noqa: E402

OUT = ROOT / "review" / "sources"
UA = "synfinder-review (research catalog; contact via GitHub sunchang0124/SynFinder)"
PDF_CHARS = 80_000


def token() -> str | None:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True,
                              text=True).stdout.strip() or None
    except OSError:
        return None


def get(url: str, headers: dict | None = None, timeout: int = 40,
        binary: bool = False):
    """(status, final_url, body) — body is text unless binary."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return r.status, r.geturl(), (data if binary else data.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.geturl() if hasattr(e, "geturl") else url, ""
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, url, str(e)


def strip_tags(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def meta_tag(page: str, name: str) -> str | None:
    m = re.search(r'<meta[^>]+(?:name|property)="%s"[^>]+content="([^"]*)"' % re.escape(name), page, re.I)
    if not m:
        m = re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:name|property)="%s"' % re.escape(name), page, re.I)
    return html.unescape(m.group(1)).strip() if m else None


def pdf_text(data: bytes, tag: str) -> str:
    tmp = OUT / f".{tag}.pdf"
    tmp.write_bytes(data)
    try:
        r = subprocess.run(["pdftotext", "-l", "20", "-layout", str(tmp), "-"],
                           capture_output=True, text=True, timeout=120)
        text = re.sub(r"[ \t]+", " ", r.stdout)
        return text[:PDF_CHARS]
    except (OSError, subprocess.SubprocessError):
        return ""
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------- papers
def crossref(doi: str) -> dict:
    st, _, body = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    if st != 200:
        return {"status": st}
    msg = json.loads(body).get("message", {})
    year = None
    for k in ("published-print", "published-online", "issued", "created"):
        parts = msg.get(k, {}).get("date-parts", [[None]])
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break
    return {
        "status": 200,
        "title": (msg.get("title") or [None])[0],
        "container": (msg.get("container-title") or [None])[0],
        "year": year,
        "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in msg.get("author", [])][:6],
        "abstract": strip_tags(msg.get("abstract", "")) or None,
    }


def arxiv(aid: str) -> dict:
    st, _, body = get(f"https://export.arxiv.org/api/query?id_list={aid}")
    if st != 200:
        return {"status": st}
    title = re.search(r"<entry>.*?<title>(.*?)</title>", body, re.S)
    summ = re.search(r"<summary>(.*?)</summary>", body, re.S)
    year = re.search(r"<published>(\d{4})", body)
    authors = re.findall(r"<name>(.*?)</name>", body)
    return {"status": 200,
            "title": re.sub(r"\s+", " ", html.unescape(title.group(1))).strip() if title else None,
            "abstract": re.sub(r"\s+", " ", html.unescape(summ.group(1))).strip() if summ else None,
            "year": int(year.group(1)) if year else None, "authors": authors[:6],
            "pdf": f"https://arxiv.org/pdf/{aid}"}


def openreview(forum: str) -> dict:
    st, _, body = get(f"https://api2.openreview.net/notes?forum={forum}")
    notes = json.loads(body).get("notes", []) if st == 200 else []
    for n in notes:
        c = n.get("content", {})
        if "title" in c:
            val = lambda k: (c.get(k) or {}).get("value") if isinstance(c.get(k), dict) else c.get(k)
            return {"status": 200, "title": val("title"), "abstract": val("abstract"),
                    "authors": (val("authors") or [])[:6],
                    "year": datetime.fromtimestamp(n.get("cdate", 0) / 1000).year if n.get("cdate") else None,
                    "pdf": f"https://openreview.net/pdf?id={forum}"}
    return {"status": st or 404}


def semantic_scholar(key: str) -> dict:
    st, _, body = get("https://api.semanticscholar.org/graph/v1/paper/"
                      f"{urllib.parse.quote(key)}?fields=title,abstract,year,openAccessPdf,tldr")
    if st != 200:
        return {"status": st}
    d = json.loads(body)
    return {"status": 200, "title": d.get("title"), "abstract": d.get("abstract"),
            "year": d.get("year"), "tldr": (d.get("tldr") or {}).get("text"),
            "pdf": (d.get("openAccessPdf") or {}).get("url")}


def paper_record(url: str) -> dict:
    rec: dict = {"url": url}
    st, final, page = get(url)
    rec["http_status"], rec["final_url"] = st, final
    u = url.lower()
    doi = None
    if "doi.org/" in u:
        doi = url.split("doi.org/", 1)[1]
        rec["doi"] = doi
        m = re.match(r"10\.48550/arxiv\.(.+)", doi, re.I)
        if m:
            rec["source"] = "arxiv"
            rec.update(arxiv(m.group(1)))
            rec["s2"] = semantic_scholar(f"arXiv:{m.group(1)}")
        else:
            rec["source"] = "crossref"
            rec.update(crossref(doi))
            rec["s2"] = semantic_scholar(f"DOI:{doi}")
    elif "openreview.net" in u:
        rec["source"] = "openreview"
        rec.update(openreview(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["id"][0]))
    elif "proceedings.mlr.press" in u or "papers.nips.cc" in u:
        rec["source"] = "html"
        rec["title"] = meta_tag(page, "citation_title") or strip_tags(
            re.search(r"<title>(.*?)</title>", page, re.S).group(1) if re.search(r"<title>", page) else "")
        rec["abstract"] = meta_tag(page, "citation_abstract") or meta_tag(page, "description")
        rec["year"] = (meta_tag(page, "citation_publication_date") or "")[:4] or None
        pdf = meta_tag(page, "citation_pdf_url")
        if not pdf:
            m = re.search(r'href="([^"]+\.pdf)"', page)
            pdf = urllib.parse.urljoin(final, m.group(1)) if m else None
        rec["pdf"] = pdf
        if "papers.nips.cc" in u and not rec["abstract"]:
            m = re.search(r"<h4>Abstract</h4>\s*<p>(.*?)</p>", page, re.S)
            rec["abstract"] = strip_tags(m.group(1)) if m else None
    else:
        rec["source"] = "html"
        rec["title"] = meta_tag(page, "citation_title") or meta_tag(page, "og:title")
        rec["abstract"] = meta_tag(page, "citation_abstract") or meta_tag(page, "description")
    # full text
    pdf_url = rec.get("pdf") or (rec.get("s2") or {}).get("pdf")
    rec["pdf_url"] = pdf_url
    if pdf_url:
        st2, _, data = get(pdf_url, binary=True, timeout=90)
        if st2 == 200 and data[:4] == b"%PDF":
            rec["fulltext"] = pdf_text(data, re.sub(r"\W", "_", pdf_url)[-40:])
        else:
            rec["pdf_status"] = st2
    return rec


# ---------------------------------------------------------------- code / docs
def github_record(url: str, tok: str | None) -> dict:
    slug = github_slug(url)
    rec = {"url": url, "slug": slug}
    hdr = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {tok}"} if tok else {})}
    st, _, body = get(f"https://api.github.com/repos/{slug}", hdr)
    rec["api_status"] = st
    if st == 200:
        d = json.loads(body)
        rec.update({"full_name": d.get("full_name"), "renamed": d.get("full_name", "").lower() != slug.lower(),
                    "archived": d.get("archived"), "description": d.get("description"),
                    "homepage": d.get("homepage"), "stars": d.get("stargazers_count"),
                    "pushed_at": d.get("pushed_at"), "license": (d.get("license") or {}).get("spdx_id"),
                    "default_branch": d.get("default_branch")})
        st2, _, readme = get(f"https://api.github.com/repos/{slug}/readme",
                             {**hdr, "Accept": "application/vnd.github.raw+json"})
        rec["readme_status"] = st2
        rec["readme"] = readme[:PDF_CHARS] if st2 == 200 else None
        # a sub-path link (tree/blob) must also resolve
        if re.search(r"github\.com/[^/]+/[^/]+/(tree|blob)/", url):
            st3, _, _ = get(url)
            rec["path_status"] = st3
    return rec


def page_record(url: str) -> dict:
    st, final, page = get(url)
    rec = {"url": url, "http_status": st, "final_url": final}
    if st == 200:
        t = re.search(r"<title>(.*?)</title>", page, re.S)
        rec["title"] = strip_tags(t.group(1)) if t else None
        rec["text"] = strip_tags(page)[:20_000]
    return rec


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cat = load_catalog(ROOT / "catalog")
    only = set(sys.argv[1:])
    tok = token()
    entries = [e for e in cat.methods + cat.datasets if not only or e.id in only]
    rows = []
    for i, e in enumerate(entries, 1):
        rec = {"id": e.id, "name": e.name, "kind": "dataset" if e in cat.datasets else "method",
               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "links": {"paper": e.links.paper, "code": e.links.code, "docs": e.links.docs},
               "purposes_current": list(e.purposes)}
        if e.links.paper:
            rec["paper"] = paper_record(e.links.paper)
        if e.links.code:
            rec["code"] = github_record(e.links.code, tok) if github_slug(e.links.code) else page_record(e.links.code)
        if e.links.docs:
            rec["docs"] = github_record(e.links.docs, tok) if github_slug(e.links.docs) else page_record(e.links.docs)
        (OUT / f"{e.id}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        p, c = rec.get("paper", {}), rec.get("code", {})
        rows.append((e.id, e.name,
                     f"{p.get('http_status', '-')}/{p.get('status', '-')}" if p else "none",
                     (p.get("title") or "?")[:90] if p else "",
                     str(p.get("year") or "") if p else "",
                     "yes" if p and p.get("fulltext") else ("abs" if p and p.get("abstract") else "no") if p else "",
                     (f"{c.get('api_status', c.get('http_status', '-'))}"
                      + (" RENAMED→" + c["full_name"] if c.get("renamed") else "")
                      + (" ARCHIVED" if c.get("archived") else "")
                      + (f" path:{c['path_status']}" if c.get("path_status") not in (None, 200) else "")) if c else "none",
                     (c.get("description") or "")[:70] if c else ""))
        print(f"[{i}/{len(entries)}] {e.id}: paper {rows[-1][2]} ({rows[-1][5]}) · code {rows[-1][6]}", flush=True)
        time.sleep(0.6)
    md = ["# Link check", "", f"Fetched {datetime.now(timezone.utc).date()}. Paper title and repo description are what the link resolves to; compare with the name.", "",
          "| id | name | paper http/meta | title | year | text | code | repo description |", "|---|---|---|---|---|---|---|---|"]
    md += ["| " + " | ".join(str(x).replace("|", "/") for x in r) + " |" for r in rows]
    (ROOT / "review" / "links.md").write_text("\n".join(md) + "\n")
    print("wrote review/links.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
