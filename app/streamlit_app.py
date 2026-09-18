"""SynFinder — Streamlit front end."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synfinder import llm                                    # noqa: E402
from synfinder.catalog import load_catalog                   # noqa: E402
from synfinder.explain import as_text, explain               # noqa: E402
from synfinder.intake import Intake                          # noqa: E402
from synfinder.ranking import load_weights, rank             # noqa: E402
from synfinder.report import (                               # noqa: E402
    comparison_rows, empty_result_message, render_html, render_markdown,
)

UNSET = "not specified"


def build_intake(answers: dict) -> Intake:
    """Map raw form answers to an Intake, turning sentinels into None."""
    def clean(key):
        value = answers.get(key)
        return None if value in (UNSET, "", None) else value

    return Intake(
        domain=answers["domain"],
        data_type=answers["data_type"],
        purpose=answers["purpose"],
        privacy=answers["privacy"],
        compute=clean("compute"),
        expertise=clean("expertise"),
        expected_rows=clean("expected_rows"),
        variable_types=answers.get("variable_types") or [],
        preserves=answers.get("preserves") or [],
        require_open_license=clean("require_open_license"),
        needs_governance_evidence=clean("needs_governance_evidence"),
    )


def _pretty(value: str) -> str:
    return value.replace("_", " ")


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="SynFinder", page_icon="🧬", layout="wide")
    st.title("SynFinder")
    st.caption(
        "Answer four questions and get synthetic data generation methods that "
        "actually fit your study — with the caveats that will bite you."
    )

    catalog = load_catalog(ROOT / "catalog")
    tax = catalog.taxonomy
    weights = load_weights(ROOT / "catalog" / "weights.yaml")

    with st.form("intake"):
        st.subheader("The essentials")
        c1, c2 = st.columns(2)
        with c1:
            domain = st.selectbox("Research domain", tax["domains"],
                                  format_func=_pretty)
            purpose = st.selectbox("What is the synthetic data for?",
                                   tax["purposes"], format_func=_pretty)
        with c2:
            data_type = st.selectbox("What does your real data look like?",
                                     tax["data_types"], format_func=_pretty)
            privacy = st.selectbox(
                "Privacy requirement",
                ["none", "deidentified_ok", "formal_dp_required"],
                format_func=_pretty)

        with st.expander("Constraints and resources (optional)"):
            compute = st.selectbox("Compute available",
                                   [UNSET] + tax["compute"], format_func=_pretty)
            expertise = st.selectbox("Your experience with these methods",
                                     [UNSET] + tax["expertise"],
                                     format_func=_pretty)
            expected_rows = st.number_input(
                "Roughly how many records? (0 = not specified)",
                min_value=0, value=0, step=1000)
            variable_types = st.multiselect(
                "Variable types you must generate",
                tax["variable_types"], format_func=_pretty)
            require_open_license = st.checkbox("Must have an open licence")

        with st.expander("Fidelity and evaluation (optional)"):
            preserves = st.multiselect(
                "What must the synthetic data preserve?",
                tax["preserves"], format_func=_pretty)

        with st.expander("Governance and acceptance (optional)"):
            needs_governance = st.checkbox(
                "I need evidence of ethics or regulatory acceptance")

        submitted = st.form_submit_button("Find methods", type="primary")

    if not submitted:
        return

    intake = build_intake({
        "domain": domain, "data_type": data_type, "purpose": purpose,
        "privacy": privacy, "compute": compute, "expertise": expertise,
        "expected_rows": expected_rows or None,
        "variable_types": variable_types, "preserves": preserves,
        "require_open_license": require_open_license or None,
        "needs_governance_evidence": needs_governance or None,
    })

    ranking = rank(catalog.generation_methods(), intake, weights, top_n=5)

    covered = catalog.covers(intake.data_type)
    also = catalog.covered_data_types()
    if not ranking.shortlist:
        if covered:
            st.error(empty_result_message(intake, covered, also))
        else:
            st.info(empty_result_message(intake, covered, also), icon="🗺️")
    else:
        st.subheader("Recommended methods")

    for c in ranking.shortlist:
        e = explain(c)
        with st.container(border=True):
            left, right = st.columns([3, 1])
            left.markdown(f"### {c.method.name}")
            right.metric("Fit", f"{c.fit:.0%}")
            st.progress(c.fit)

            narrated = llm.narrate(e, c.method, intake) if llm.available() else None
            st.write(narrated or as_text(e).split("\n", 1)[-1])

            for caveat in e.caveats:
                st.warning(caveat, icon="⚠️")
            if e.evaluation:
                st.info("**How to check it worked:** " + "; ".join(e.evaluation))

            links = c.method.links
            bits = [f"[paper]({links.paper})" if links.paper else "",
                    f"[code]({links.code})" if links.code else "",
                    f"[docs]({links.docs})" if links.docs else ""]
            line = " · ".join(b for b in bits if b)
            if line:
                st.markdown(line)

    if ranking.shortlist:
        st.subheader("Side by side")
        header, rows = comparison_rows(ranking)
        st.dataframe([dict(zip(header, r)) for r in rows], hide_index=True)

    matching = [d for d in catalog.datasets
                if d.domain in (intake.domain, "general")
                and d.data_type == intake.data_type]
    if matching:
        st.subheader("Ready-made synthetic datasets")
        for d in matching:
            st.markdown(
                f"- **{d.name}** ({d.size}, {d.license}) — {d.access_conditions}"
            )

    if ranking.excluded:
        with st.expander(
            f"Why {len(ranking.excluded)} other method(s) were ruled out"
        ):
            for x in ranking.excluded:
                st.markdown(f"- **{x.method_name}** {x.reason}.")

    st.subheader("Take it with you")
    d1, d2 = st.columns(2)
    d1.download_button("Download report (Markdown)",
                       render_markdown(intake, ranking, matching, covered, also),
                       file_name="synfinder-report.md", mime="text/markdown")
    d2.download_button("Download report (HTML)",
                       render_html(intake, ranking, matching, covered, also),
                       file_name="synfinder-report.html", mime="text/html")

    if not llm.available():
        st.caption(
            "Running without an ANTHROPIC_API_KEY — rationales are the "
            "catalog's own wording. Everything above works the same either way."
        )


if __name__ == "__main__":
    main()
