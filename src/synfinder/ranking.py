"""Hard filters and shortlist ordering.

Survivors are ordered in strict tiers, never by a number:
  1. supports the stated purpose;
  2. how well it meets the optional answers the user gave (preserved
     structure, expertise, expected rows, governance evidence);
  3. how recently its repository was pushed, in half-year to three-year
     buckets (see repometa.maintenance_bucket);
  4. name.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .intake import Intake
from .repometa import maintenance_bucket
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

# Axes that only count when the user answered the matching question.
OPTIONAL_AXES = ("preserves", "expertise", "scale", "governance")

EXPERTISE_RANK = {"low": 0, "medium": 1, "high": 2}
@dataclass
class AxisScore:
    axis: str
    score: float
    note: str
    # False when the catalog records nothing on this axis for this method.
    # Scored UNKNOWN_SCORE, rendered "?", and never used in an explanation.
    known: bool = True


# What an axis scores when nobody has checked it. Neutral: neither the 1.0
# that silently rewarded missing evidence before v3, nor a penalty for a gap
# that is the catalog's fault rather than the method's.
UNKNOWN_SCORE = 0.5


@dataclass
class Candidate:
    method: Method
    axes: list[AxisScore]
    # Sum of the optional axes' scores: the second ordering tier.
    optional_fit: float = 0.0
    # Recency bucket of the last repository push (0 = freshest): third tier.
    maintenance: int = 0
    maintenance_note: str = ""

    def axis(self, name: str) -> AxisScore | None:
        return next((a for a in self.axes if a.axis == name), None)


@dataclass
class Ranking:
    shortlist: list[Candidate]
    excluded: list[Exclusion]
    # True when NOTHING in the catalog is intended for the stated purpose and
    # the shortlist is therefore a set of near-misses, not recommendations.
    no_purpose_match: bool = False


def _purpose_axis(method: Method, intake: Intake) -> AxisScore:
    hit = intake.purpose in method.purposes
    note = (
        f"supports your purpose ({intake.purpose.replace('_', ' ')})"
        if hit
        else f"is not typically used for {intake.purpose.replace('_', ' ')}"
    )
    return AxisScore("purpose", 1.0 if hit else 0.0, note)


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
    return AxisScore("preserves", score, note)


def _expertise_axis(method: Method, intake: Intake) -> AxisScore:
    gap = EXPERTISE_RANK[method.expertise] - EXPERTISE_RANK[intake.expertise]
    score = 1.0 if gap <= 0 else max(0.0, 1.0 - 0.5 * gap)
    note = (
        "sits within your stated experience level"
        if gap <= 0
        else f"expects {method.expertise} familiarity with synthetic data methods"
    )
    return AxisScore("expertise", score, note)


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
        return AxisScore("scale", UNKNOWN_SCORE,
                         "has no published size envelope; unverified for your size",
                         known=False)
    else:
        score = 1.0
        note = f"handles {rows:,} rows comfortably"
    return AxisScore("scale", score, note)


MAINTENANCE_SCORE = [1.0, 0.8, 0.6, 0.4, 0.2]


def _maintenance_axis(method: Method, today: date) -> tuple[AxisScore, int]:
    bucket, note = maintenance_bucket(method.maturity.last_pushed, today)
    if bucket >= len(MAINTENANCE_SCORE):
        return AxisScore("maintenance", UNKNOWN_SCORE, note, known=False), bucket
    return AxisScore("maintenance", MAINTENANCE_SCORE[bucket], note), bucket


def _governance_axis(method: Method) -> AxisScore:
    evidence = method.governance.acceptance_evidence
    deployments = method.governance.known_deployments
    if evidence or deployments:
        return AxisScore("governance", 1.0,
                         "has a track record you can point a review board to")
    if method.governance_checked():
        return AxisScore("governance", 0.2,
                         "has no documented governance or regulatory acceptance")
    return AxisScore("governance", UNKNOWN_SCORE,
                     "has not had its governance record checked yet", known=False)


def score_method(method: Method, intake: Intake, today: date | None = None) -> Candidate:
    today = today or date.today()
    maint, bucket = _maintenance_axis(method, today)
    axes: list[AxisScore] = [_purpose_axis(method, intake), maint]

    if intake.answered("preserves"):
        axes.append(_preserves_axis(method, intake))
    if intake.answered("expertise"):
        axes.append(_expertise_axis(method, intake))
    if intake.answered("expected_rows"):
        axes.append(_scale_axis(method, intake))
    if intake.needs_governance_evidence:
        axes.append(_governance_axis(method))

    optional = sum(a.score for a in axes if a.axis in OPTIONAL_AXES)
    return Candidate(method=method, axes=axes, optional_fit=optional,
                     maintenance=bucket, maintenance_note=maint.note)


def rank(
    methods: list[Method],
    intake: Intake,
    top_n: int = 5,
    today: date | None = None,
) -> Ranking:
    kept, excluded = hard_filter(methods, intake)
    candidates = [score_method(m, intake, today) for m in kept]

    # Purpose is the question the user actually asked. A method scoring zero
    # on it must never outrank one that matches, however good its other axes
    # look - that is how Synthea came top for statistical replication while
    # its own caveat said never to use it for that.
    matched = [c for c in candidates
               if (a := c.axis("purpose")) is not None and a.score > 0]
    no_purpose_match = not matched
    candidates = matched or candidates
    # Then the optional answers, then recency of the repository, then name.
    # Buckets rather than exact dates, so that the last tier is the name and
    # not whoever happened to push most recently.
    candidates.sort(key=lambda c: (-c.optional_fit, c.maintenance,
                                   c.method.name.casefold()))
    return Ranking(
        shortlist=candidates[:top_n],
        excluded=excluded,
        no_purpose_match=no_purpose_match,
    )
