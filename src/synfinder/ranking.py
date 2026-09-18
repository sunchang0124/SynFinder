"""Hard filters and weighted scoring."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .intake import Intake
from .schema import Method

OPEN_LICENSES = {
    "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0",
    "GPL-3.0", "GPL-2.0", "LGPL-3.0", "MPL-2.0", "CC-BY-4.0", "CC0-1.0",
}


@dataclass
class Exclusion:
    method_id: str
    method_name: str
    reason: str


def _exclusion_reason(method: Method, intake: Intake) -> str | None:
    """The first reason this method cannot serve this intake, or None."""
    if method.is_framework:
        return "is a framework or toolkit, not a generation method in itself"

    if intake.domain not in method.domains and "general" not in method.domains:
        return f"is not established for the {intake.domain} domain"

    if intake.data_type not in method.data_types:
        return f"cannot handle {intake.data_type} data"

    # Only a stated requirement filters. "not_required" is the absence of a
    # constraint, so every method - privacy-preserving or not - stays in.
    if (intake.privacy == "required"
            and not method.formal_dp
            and not method.requires_no_source_data):
        return "specifies no privacy measures"

    if intake.compute == "cpu_fine" and method.compute == "gpu_required":
        return "requires a GPU, which you said is not available"

    missing = set(intake.variable_types) - set(method.variable_types)
    if "free_text" in missing:
        return "cannot generate free text fields"
    if missing:
        return f"cannot generate {', '.join(sorted(missing))} variables"

    if intake.require_open_license and method.license not in OPEN_LICENSES:
        return f"license {method.license} is not an open licence"

    return None


def hard_filter(
    methods: list[Method], intake: Intake
) -> tuple[list[Method], list[Exclusion]]:
    kept: list[Method] = []
    dropped: list[Exclusion] = []
    for method in methods:
        reason = _exclusion_reason(method, intake)
        if reason is None:
            kept.append(method)
        else:
            dropped.append(Exclusion(method.id, method.name, reason))
    return kept, dropped


# --- scoring -------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "purpose": 3.0,
    "preserves": 2.5,
    "expertise": 1.5,
    "maturity": 1.5,
    "scale": 1.0,
    "governance": 1.0,
}

EXPERTISE_RANK = {"low": 0, "medium": 1, "high": 2}
QUALITY_SCORE = {
    "reference_only": 0.3,
    "research_code": 0.6,
    "production_ready": 1.0,
}


@dataclass
class AxisScore:
    axis: str
    score: float
    weight: float
    note: str


@dataclass
class Candidate:
    method: Method
    fit: float
    axes: list[AxisScore]

    def axis(self, name: str) -> AxisScore | None:
        return next((a for a in self.axes if a.axis == name), None)


@dataclass
class Ranking:
    shortlist: list[Candidate]
    excluded: list[Exclusion]
    # True when NOTHING in the catalog is intended for the stated purpose and
    # the shortlist is therefore a set of near-misses, not recommendations.
    no_purpose_match: bool = False


def load_weights(path: Path) -> dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(yaml.safe_load(Path(path).read_text()) or {})
    return weights


def _purpose_axis(method: Method, intake: Intake) -> AxisScore:
    hit = intake.purpose in method.purposes
    note = (
        f"supports your purpose ({intake.purpose.replace('_', ' ')})"
        if hit
        else f"is not typically used for {intake.purpose.replace('_', ' ')}"
    )
    return AxisScore("purpose", 1.0 if hit else 0.0, 0.0, note)


def _preserves_axis(method: Method, intake: Intake) -> AxisScore:
    wanted = set(intake.preserves)
    met = wanted & set(method.preserves)
    score = len(met) / len(wanted)
    if score == 1.0:
        note = "preserves everything you asked for"
    elif met:
        note = (
            f"preserves {', '.join(sorted(m.replace('_', ' ') for m in met))} "
            f"but not {', '.join(sorted(w.replace('_', ' ') for w in wanted - met))}"
        )
    else:
        note = (
            "preserves none of "
            f"{', '.join(sorted(w.replace('_', ' ') for w in wanted))}"
        )
    return AxisScore("preserves", score, 0.0, note)


def _expertise_axis(method: Method, intake: Intake) -> AxisScore:
    gap = EXPERTISE_RANK[method.expertise] - EXPERTISE_RANK[intake.expertise]
    score = 1.0 if gap <= 0 else max(0.0, 1.0 - 0.5 * gap)
    note = (
        "sits within your stated experience level"
        if gap <= 0
        else f"expects {method.expertise} familiarity with synthetic data methods"
    )
    return AxisScore("expertise", score, 0.0, note)


def _scale_axis(method: Method, intake: Intake) -> AxisScore:
    rows = intake.expected_rows
    max_rows, min_rows = method.scale.max_rows, method.scale.min_rows
    if max_rows is not None and rows > max_rows:
        over = rows / max_rows
        score = 0.4 if over <= 2 else 0.1
        note = f"is usually run on at most ~{max_rows:,} rows"
    elif min_rows is not None and rows < min_rows:
        score = 0.4
        note = f"needs roughly {min_rows:,} rows to train well"
    elif max_rows is None and min_rows is None:
        score = 1.0
        note = "has no published size envelope in the catalog yet"
    else:
        score = 1.0
        note = f"handles {rows:,} rows comfortably"
    return AxisScore("scale", score, 0.0, note)


def _maturity_axis(method: Method) -> AxisScore:
    score = QUALITY_SCORE.get(method.maturity.implementation_quality, 0.5)
    if not method.maturity.maintained:
        score *= 0.5
    note = (
        f"implementation is "
        f"{method.maturity.implementation_quality.replace('_', ' ')}"
        + ("" if method.maturity.maintained else " and no longer maintained")
    )
    return AxisScore("maturity", score, 0.0, note)


def _governance_axis(method: Method) -> AxisScore:
    evidence = method.governance.acceptance_evidence
    deployments = method.governance.known_deployments
    if evidence or deployments:
        score = 1.0
        note = "has a track record you can point a review board to"
    else:
        score = 0.2
        note = "has no documented governance or regulatory acceptance yet"
    return AxisScore("governance", score, 0.0, note)


def score_method(
    method: Method, intake: Intake, weights: dict[str, float] | None = None
) -> Candidate:
    weights = weights or DEFAULT_WEIGHTS
    axes: list[AxisScore] = [_purpose_axis(method, intake), _maturity_axis(method)]

    if intake.answered("preserves"):
        axes.append(_preserves_axis(method, intake))
    if intake.answered("expertise"):
        axes.append(_expertise_axis(method, intake))
    if intake.answered("expected_rows"):
        axes.append(_scale_axis(method, intake))
    if intake.needs_governance_evidence:
        axes.append(_governance_axis(method))

    for a in axes:
        a.weight = weights.get(a.axis, 1.0)

    total = sum(a.weight for a in axes)
    fit = sum(a.score * a.weight for a in axes) / total if total else 0.0
    return Candidate(method=method, fit=fit, axes=axes)


def rank(
    methods: list[Method],
    intake: Intake,
    weights: dict[str, float] | None = None,
    top_n: int = 5,
) -> Ranking:
    kept, excluded = hard_filter(methods, intake)
    candidates = [score_method(m, intake, weights) for m in kept]

    # Purpose is the question the user actually asked. A method scoring zero
    # on it must never outrank one that matches, however good its other axes
    # look - that is how Synthea came top for statistical replication while
    # its own caveat said never to use it for that.
    matched = [c for c in candidates
               if (a := c.axis("purpose")) is not None and a.score > 0]
    no_purpose_match = not matched
    candidates = matched or candidates
    # Ties are common: with only the core four answered, every method that
    # supports the stated purpose scores identically. Break on implementation
    # quality, then on whether anyone has actually got this past a review
    # board - an arbitrary order would drop a defensible method off the list.
    candidates.sort(
        key=lambda c: (
            c.fit,
            QUALITY_SCORE.get(c.method.maturity.implementation_quality, 0.0),
            len(c.method.governance.acceptance_evidence)
            + len(c.method.governance.known_deployments),
        ),
        reverse=True,
    )
    return Ranking(
        shortlist=candidates[:top_n],
        excluded=excluded,
        no_purpose_match=no_purpose_match,
    )
