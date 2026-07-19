"""
rigor_toolkit.core — the three data shapes everything else operates on.

A Prediction is anything with a time, a predicted label, and optionally a
confidence, a series id (independent stream, e.g. one market/one asset)
and a group id (correlation group, e.g. all strikes of one event).

An Outcome is what a resolver returns for an episode:
    Outcome(resolved=False)           -> horizon not reached / ungradable
    Outcome(True, "UP")               -> resolved, ground-truth label "UP"
    Outcome(True, None)               -> resolved but matches NO prediction
                                         (e.g. zero price move) — counts in
                                         the sample, credits no rule.

An Episode is a deduplicated prediction plus its resolution state. Every
downstream number (baselines, verdict, power) is computed from episodes,
never from raw predictions — the episode count is the sample size.
"""

from dataclasses import dataclass, field
from typing import Any, NamedTuple, Optional


@dataclass
class Prediction:
    ts: Any                              # sortable; datetime or bar index
    label: Any                           # predicted outcome label
    confidence: Optional[float] = None
    series: Any = None                   # independent stream id
    group: Any = None                    # correlation group id
    meta: dict = field(default_factory=dict)


class Outcome(NamedTuple):
    resolved: bool
    label: Any = None


UNRESOLVED = Outcome(False, None)


@dataclass
class Episode:
    prediction: Prediction
    n_merged: int = 0                    # extra predictions collapsed in
    resolved: bool = False
    outcome_label: Any = None
    correct: bool = False

    @property
    def ts(self):
        return self.prediction.ts

    @property
    def label(self):
        return self.prediction.label
