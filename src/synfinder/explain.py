"""Turn a score breakdown into prose, using only catalog text."""
from __future__ import annotations

from dataclasses import dataclass, field

from .ranking import Candidate

STRONG = 0.75
WEAK = 0.6


@dataclass
class Explanation:
    headline: str
    why_fits: list[str] = field(default_factory=list)
    weakness: str | None = None
    caveats: list[str] = field(default_factory=list)
    evaluation: list[str] = field(default_factory=list)


def explain(candidate: Candidate, top_k: int = 2) -> Explanation:
    method = candidate.method
    ranked = sorted(candidate.axes, key=lambda a: a.score * a.weight, reverse=True)

    why = [a.note for a in ranked if a.score >= STRONG][:top_k]

    losers = [a for a in candidate.axes if a.score < WEAK]
    losers.sort(key=lambda a: a.score * a.weight)
    weakness = losers[0].note if losers else None

    headline = f"{method.name} — {candidate.fit:.0%} fit"
    return Explanation(
        headline=headline,
        why_fits=why,
        weakness=weakness,
        caveats=list(method.caveats),
        evaluation=list(method.evaluation),
    )


def as_text(explanation: Explanation) -> str:
    parts = [explanation.headline]
    if explanation.why_fits:
        parts.append("Why it fits: " + "; ".join(explanation.why_fits) + ".")
    if explanation.weakness:
        parts.append(f"Where it is weaker: it {explanation.weakness}.")
    if explanation.caveats:
        parts.append("Watch out: " + " ".join(explanation.caveats))
    if explanation.evaluation:
        parts.append(
            "How to check it worked: " + "; ".join(explanation.evaluation) + "."
        )
    return "\n".join(parts)
