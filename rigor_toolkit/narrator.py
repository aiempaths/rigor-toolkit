"""
rigor_toolkit.narrator — plain-language verdict narration, numbers-in
prose-out, never the other way.

Pattern extracted from the origin system's narrator agents, with the
same hard rules enforced by construction:

  - Input is the already-computed Verdict (or its dict). The narrator
    PHRASES numbers; it never computes, estimates, or extrapolates one.
  - Missing values are serialized as "not available" and the prompt
    forbids guessing them.
  - Failure degrades to None — a narrator can never raise into, or
    write into, the pipeline that called it. Callers own all writes.

Two implementations:

  render_plain(verdict)  — deterministic template, zero dependencies,
                           always available. Quotes the computed
                           headline verbatim and lists the baseline
                           table; adds no judgment the numbers don't
                           carry.
  LLMNarrator(complete)  — wraps ANY text-completion callable you
                           supply (`complete(prompt) -> str`). The
                           toolkit does not import or assume any LLM
                           client; bounding the call (timeouts) is the
                           callable's job.
"""

import json
from datetime import datetime

_COMMON_RULES = (
    "\n\nHard rules: use ONLY the numbers and facts in the DATA block. "
    "Do not compute, estimate, extrapolate, or invent any figure. If a "
    "value you need is missing or marked 'not available', write 'not "
    "available' for it instead of guessing. Respond with plain prose "
    "only — no JSON, no markdown headers, no bullet lists unless asked."
)

AUDITOR_PROMPT = (
    "You will be given precomputed statistics: resolved episode count, "
    "power thresholds, baseline comparison, and (if present) a binomial "
    "p-value vs the 50% baseline. Write a short, clinical explanation of "
    "what these numbers mean for whether a claim of predictive skill is "
    "currently justified. Use only the numbers provided — do not compute "
    "or estimate any statistic yourself. If resolved episodes are below "
    "the stated power threshold, state plainly that no claim is possible "
    "and why, citing the exact provided numbers. If the model does not "
    "beat every baseline, state that plainly. Cold, precise, no hedging "
    "language, no marketing language."
)


def _clean(payload):
    """None -> 'not available', recursively, so absence is explicit."""
    if payload is None:
        return "not available"
    if isinstance(payload, dict):
        return {k: _clean(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_clean(v) for v in payload]
    return payload


def stamp(text, narrator_name):
    """Standard block callers embed when writing narration to disk."""
    ts = datetime.now().isoformat(timespec="seconds")
    return (f"_{narrator_name} narration, generated {ts}. The computed "
            f"numbers nearby are the source of truth; this text only "
            f"describes them._\n\n{text}")


def render_plain(verdict):
    """Deterministic narration: quotes computed values only."""
    v = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict)
    lines = [v["headline"]]
    if v["resolved"]:
        if v["resolved"] < v["min_sample"]:
            lines.append(
                f"The resolved sample ({v['resolved']}) is below the "
                f"absolute minimum ({v['min_sample']}); no claim is "
                f"defensible regardless of the record so far.")
        elif v["p_value"] is not None and v["p_value"] >= 0.05:
            lines.append("Not statistically distinguishable from chance.")
        for name, b in v["baselines"].items():
            lines.append(
                f"Baseline '{name}': {b['correct']}/{b['n']} on the same "
                f"episodes.")
        if v["baselines"]:
            if v["beats_all_baselines"]:
                lines.append(
                    "The model exceeds every listed baseline; whether the "
                    "margin means anything is bounded by the sample-size "
                    "thresholds below.")
            else:
                lines.append(
                    "The model does NOT beat every listed baseline; no "
                    "claim above naive baselines is demonstrated.")
    need = ", ".join(f"{k}: {n}" for k, n in v["thresholds"].items())
    lines.append(f"Resolved episodes needed per claim strength — {need}.")
    return "\n".join(lines)


class LLMNarrator:
    """Bounded, narrator-only wrapper around a user-supplied completion
    callable. Returns str or None; never raises."""

    def __init__(self, complete, prompt=AUDITOR_PROMPT, name="Narrator"):
        self.complete = complete
        self.prompt = prompt
        self.name = name

    def narrate(self, verdict):
        v = (verdict.to_dict() if hasattr(verdict, "to_dict")
             else dict(verdict))
        data = json.dumps(_clean(v), indent=2, default=str)
        full = (self.prompt + _COMMON_RULES +
                "\n\nDATA (the only numbers you may use):\n" + data)
        try:
            text = (self.complete(full) or "").strip()
            return text or None
        except Exception:
            return None
