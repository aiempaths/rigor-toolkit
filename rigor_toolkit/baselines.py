"""
rigor_toolkit.baselines — the pluggable, named baseline registry.

Baseline selection is the load-bearing design decision of this toolkit
(see README: the Wikipedia trap and the Kalshi null result). Baselines
are therefore SELECTED AND JUSTIFIED EXPLICITLY by the user — nothing is
auto-picked. Every constructor takes a `rationale` so the justification
travels with the number into the verdict object.

A baseline is a named function from an Episode to a predicted label
(or None to abstain — an abstaining baseline can never be credited on
that episode). The toolkit cannot know how to read "the last move" or
"the same window one season ago" in your domain, so the label functions
are yours; the registry's job is naming, discipline, and the verdict
table.

The one special case is always_majority(): its prediction is the
in-sample majority OUTCOME, so it is computed by the grader from
resolved episodes, not from a user function. It is an upper bound on
every constant rule — if your model does not beat it, no signal above
naive baselines is demonstrated.

reference_estimate() exists for domains that carry their own efficient
estimate (a prediction market's current price, a bookmaker's line, a
consensus forecast). In such domains it is the PRIMARY baseline: if the
model cannot beat the domain's own best number, the honest verdict is
that it extracts nothing that number does not already contain.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Baseline:
    name: str
    fn: Optional[Callable[[Any], Any]] = None   # Episode -> label | None
    rationale: str = ""
    kind: str = "fn"                            # "fn" | "majority"

    # ── named constructors ────────────────────────────────────────────
    @classmethod
    def constant(cls, label, rationale=""):
        """Always predict `label` (e.g. always-UP)."""
        return cls(name=f"always-{label}", fn=lambda e: label,
                   rationale=rationale or f"constant rule: always {label}")

    @classmethod
    def always_majority(cls, rationale=""):
        """In-sample majority outcome — upper bound on constant rules.
        Computed by the grader from resolved outcomes; no user fn."""
        return cls(name="always-majority-outcome (in-sample)", fn=None,
                   kind="majority",
                   rationale=rationale or "upper bound on constant rules")

    @classmethod
    def persistence(cls, fn, rationale=""):
        """The last observed move/state continues. `fn(episode)` must
        return the label implied by continuation in your domain."""
        return cls(name="persistence", fn=fn,
                   rationale=rationale or "last observed move continues")

    @classmethod
    def anti_persistence(cls, fn, rationale=""):
        """The last observed move reverses. On cyclical series at a
        horizon near the half-cycle this is often the strongest trivial
        rule — grade against it or get false positives."""
        return cls(name="anti-persistence", fn=fn,
                   rationale=rationale or "last observed move reverses")

    @classmethod
    def seasonal_naive(cls, fn, rationale=""):
        """Same direction as one seasonal period ago. `fn` may return
        None (abstain) when the seasonal lookback is unavailable."""
        return cls(name="seasonal-naive", fn=fn,
                   rationale=rationale or "repeat the move one season ago")

    @classmethod
    def reference_estimate(cls, fn, name="reference-estimate (PRIMARY)",
                           rationale=""):
        """The domain's own efficient estimate persists (e.g. prediction-
        market price > 50c implies the market-favorite direction)."""
        return cls(name=name, fn=fn,
                   rationale=rationale or
                   "the domain's own current best estimate, unmodified")


def grade_baselines(episodes, baselines):
    """Grade every baseline on the SAME resolved episodes the model is
    graded on. Returns {name: {"correct", "n", "rate", "rationale",
    ["label"]}}. Episodes whose outcome label is None (resolved,
    zero-move) credit no rule but stay in n — identical to the model's
    own grading."""
    graded = [e for e in episodes if e.resolved]
    n = len(graded)
    results = {}
    for b in baselines:
        entry = {"n": n, "rationale": b.rationale}
        if b.kind == "majority":
            counts = {}
            for e in graded:
                if e.outcome_label is not None:
                    counts[e.outcome_label] = counts.get(e.outcome_label, 0) + 1
            if counts:
                label = max(counts, key=counts.get)
                entry["label"] = label
                entry["correct"] = counts[label]
            else:
                entry["label"] = None
                entry["correct"] = 0
        else:
            entry["correct"] = sum(
                1 for e in graded
                if e.outcome_label is not None
                and b.fn(e) == e.outcome_label)
        entry["rate"] = entry["correct"] / n if n else None
        results[b.name] = entry
    return results
