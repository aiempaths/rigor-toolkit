"""
rigor_toolkit.verdict — the single computation point.

Discipline extracted from the origin system's evidence machinery: the
verdict is computed ONCE, into one object, and every consumer — report
renderer, dashboard, narrator, public disclosure — reads THAT object.
Nothing downstream ever re-derives a rate, a p-value, or a threshold.
If a number appears in two places, both places got it from here.

The headline is part of the object (computed, not editorial) so that
even the sentence is shared, not re-phrased per consumer.
"""

from dataclasses import dataclass, field
from typing import Optional

from .power import binom_p_one_sided, power_thresholds


@dataclass(frozen=True)
class Verdict:
    episodes: int                 # independent episodes (the only sample)
    resolved: int
    correct: int
    p_value: Optional[float]      # one-sided binomial vs p0, resolved only
    headline: str                 # computed sentence — quote, don't rewrite
    min_sample: int
    thresholds: dict              # claim strength -> resolved n needed
    baselines: dict = field(default_factory=dict)

    @property
    def hit_rate(self):
        return self.correct / self.resolved if self.resolved else None

    def beats_all_baselines(self):
        """True only if the model strictly beats EVERY baseline column.
        (Lesson from the origin system's cross-domain tests: beating a
        chosen baseline while losing to a better trivial rule is a
        false positive.)"""
        if not self.baselines:
            return None
        return all(self.correct > b["correct"]
                   for b in self.baselines.values())

    def to_dict(self):
        return {
            "episodes": self.episodes, "resolved": self.resolved,
            "correct": self.correct, "p_value": self.p_value,
            "hit_rate": self.hit_rate, "headline": self.headline,
            "min_sample": self.min_sample, "thresholds": self.thresholds,
            "baselines": self.baselines,
            "beats_all_baselines": self.beats_all_baselines(),
        }


def compute_verdict(episodes, baseline_results=None, *, thresholds=None,
                    claim_name="edge", horizon_name="horizon", p0=0.5):
    """Port of the origin _verdict(), generalized: `claim_name` and
    `horizon_name` parameterize the wording (the origin system uses
    "trading-edge" and "hold horizon"), thresholds default to the
    published [5, 37, 67, 153] via power_thresholds()."""
    if thresholds is None:
        thresholds = power_thresholds()
    resolved = [e for e in episodes if e.resolved]
    correct = sum(1 for e in resolved if e.correct)
    p = binom_p_one_sided(correct, len(resolved), p0) if resolved else None
    if not resolved:
        headline = (f"No {claim_name} claim is possible: {len(episodes)} "
                    f"independent episode(s) exist and 0 have resolved at "
                    f"their {horizon_name}.")
    else:
        headline = (f"Resolved episodes: {len(resolved)} — {correct} correct "
                    f"({correct / len(resolved) * 100:.0f}%). One-sided "
                    f"binomial vs coin flip: p = {p:.3f}.")
    return Verdict(episodes=len(episodes), resolved=len(resolved),
                   correct=correct, p_value=p, headline=headline,
                   min_sample=thresholds.get("perfect_record", 5),
                   thresholds=dict(thresholds),
                   baselines=dict(baseline_results or {}))
