"""
rigor_toolkit — honest grading machinery for timestamped predictions.

Domain-agnostic. Feed it any (timestamp, prediction[, confidence]) stream
plus a resolver that looks up ground truth at a horizon, and explicitly
chosen baselines; get back one computed Verdict that every consumer
reads and none re-derives.

    from rigor_toolkit import Evaluator, Baseline, Prediction, Outcome

    ev = Evaluator(resolver=my_resolver,
                   baselines=[Baseline.persistence(my_prior_move),
                              Baseline.reference_estimate(my_ref)])
    verdict = ev.grade(predictions, horizon=10)
    print(verdict.headline)

See README.md — baseline selection is the load-bearing decision.
"""

from .baselines import Baseline, grade_baselines
from .core import UNRESOLVED, Episode, Outcome, Prediction
from .episodes import collapse_across_groups, collapse_within_series
from .evaluator import Evaluator, resolve
from .narrator import AUDITOR_PROMPT, LLMNarrator, render_plain, stamp
from .power import (binom_p_one_sided, min_perfect_record, n_needed,
                    power_thresholds)
from .verdict import Verdict, compute_verdict

__version__ = "0.1.0"

__all__ = [
    "Prediction", "Episode", "Outcome", "UNRESOLVED",
    "collapse_within_series", "collapse_across_groups",
    "Baseline", "grade_baselines",
    "binom_p_one_sided", "n_needed", "min_perfect_record",
    "power_thresholds",
    "Verdict", "compute_verdict",
    "Evaluator", "resolve",
    "render_plain", "LLMNarrator", "stamp", "AUDITOR_PROMPT",
    "__version__",
]
