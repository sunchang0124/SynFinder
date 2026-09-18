"""Optional LLM narration. Every function degrades to None.

The catalog decides; this only rewrites the decision into prose. Nothing
here may introduce a fact that is not already in the Explanation.
"""
from __future__ import annotations

import os

from .explain import Explanation, as_text
from .intake import Intake
from .schema import Method

MODEL = "claude-opus-5"

SYSTEM = (
    "You rewrite a structured recommendation into two or three fluent "
    "sentences for a health researcher. Use only the facts given to you. "
    "Do not introduce any method, claim, number or citation that is not in "
    "the input. Keep every caveat."
)


def available() -> bool:
    """True when a narration call could plausibly succeed.

    Only environment credentials are detected; an `ant auth login` profile
    is not, so the app simply falls back to template text in that case.
    """
    if not (os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def build_prompt(explanation: Explanation, method: Method, intake: Intake) -> str:
    return (
        f"Researcher's situation: {intake.domain} study, {intake.data_type} "
        f"data, purpose is {intake.purpose}, privacy requirement is "
        f"{intake.privacy}.\n\n"
        f"Recommended method: {method.name}.\n\n"
        f"Structured recommendation to rewrite:\n{as_text(explanation)}\n\n"
        "Rewrite this for the researcher. Do not introduce anything new."
    )


def _call(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        # Thinking is on by default on Opus 5 and its tokens count against
        # max_tokens, so leave headroom even though the prose is short.
        max_tokens=2000,
        output_config={"effort": "low"},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()


def narrate(
    explanation: Explanation, method: Method, intake: Intake
) -> str | None:
    """Fluent prose, or None if narration is unavailable or fails.

    Deliberately broad: a narration failure must never break a page that
    works perfectly well with the template text.
    """
    if not available():
        return None
    try:
        return _call(build_prompt(explanation, method, intake)) or None
    except Exception:
        return None
