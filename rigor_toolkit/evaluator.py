"""
rigor_toolkit.evaluator — the one-call orchestration:

    predictions -> episode dedup -> resolution -> baselines -> Verdict

The Evaluator owns nothing domain-specific. You supply:
  resolver(episode) -> Outcome   how ground truth is looked up at the
                                 horizon (return UNRESOLVED if the
                                 horizon hasn't arrived / can't grade;
                                 Outcome(True, None) if resolved but no
                                 label wins, e.g. zero move)
  baselines                      explicitly chosen Baseline objects
  horizon (+ optional group_horizon for correlated streams)
"""

from .baselines import grade_baselines
from .core import UNRESOLVED
from .episodes import collapse_across_groups, collapse_within_series
from .verdict import compute_verdict


def resolve(episodes, resolver):
    """Apply `resolver` to every episode, in place. correct is True only
    for resolved episodes whose outcome label equals the predicted
    label; unresolved episodes never count correct."""
    for e in episodes:
        out = resolver(e)
        if out is None:
            out = UNRESOLVED
        e.resolved = bool(out.resolved)
        e.outcome_label = out.label if out.resolved else None
        e.correct = bool(out.resolved and out.label is not None
                         and e.label == out.label)
    return episodes


class Evaluator:
    def __init__(self, resolver, baselines=(), *, thresholds=None,
                 claim_name="edge", horizon_name="horizon", p0=0.5):
        self.resolver = resolver
        self.baselines = list(baselines)
        self.thresholds = thresholds
        self.claim_name = claim_name
        self.horizon_name = horizon_name
        self.p0 = p0

    def episodes(self, predictions, horizon, *, time=None,
                 group_horizon=None, group_time=None, anchor="start"):
        """Dedup only (no resolution) — exposed for inspection."""
        eps = collapse_within_series(predictions, horizon, time=time,
                                     anchor=anchor)
        if group_horizon is not None:
            eps = collapse_across_groups(eps, group_horizon,
                                         time=group_time, anchor=anchor)
        return eps

    def grade(self, predictions, horizon, *, time=None,
              group_horizon=None, group_time=None, anchor="start"):
        """predictions must be time-ordered within each series."""
        eps = self.episodes(predictions, horizon, time=time,
                            group_horizon=group_horizon,
                            group_time=group_time, anchor=anchor)
        resolve(eps, self.resolver)
        base = grade_baselines(eps, self.baselines)
        v = compute_verdict(eps, base, thresholds=self.thresholds,
                            claim_name=self.claim_name,
                            horizon_name=self.horizon_name, p0=self.p0)
        self.last_episodes = eps       # inspectable, not re-derivable
        return v
