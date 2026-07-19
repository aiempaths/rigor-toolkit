"""
examples/coinflip_smoke.py — "does this work on a model that isn't the
origin system?" smoke test. Pure stdlib: no numpy, no scipy, nothing
imported from any trading code. Runs inside a bare venv with only
rigor_toolkit installed.

Model under test: a literal seeded coin flip on a synthetic random-walk
series. Expected outcome: hit rate ~50%, p-value far from significance,
and the model NOT beating the baseline set — i.e. the toolkit correctly
refuses to certify a model with no information, and demonstrably makes
no assumption about how predictions were produced.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rigor_toolkit import (Baseline, Evaluator, Outcome, Prediction,
                           UNRESOLVED, render_plain)

HOLD = 10
random.seed(7)

# synthetic random-walk "price" series, 4000 bars
series = [100.0]
for _ in range(3999):
    series.append(max(series[-1] + random.gauss(0, 1.0), 1.0))
N = len(series)

# the dumbest possible model: flip a coin every 12th bar
preds = [Prediction(ts=i, label=random.choice(["UP", "DOWN"]))
         for i in range(50, N, 12)]


def resolver(ep):
    i = ep.prediction.ts
    if i + HOLD >= N:
        return UNRESOLVED
    move = series[i + HOLD] - series[i]
    return Outcome(True, "UP" if move > 0 else
                   "DOWN" if move < 0 else None)


baselines = [
    Baseline.constant("UP"),
    Baseline.always_majority(),
    Baseline.persistence(
        lambda e: "UP" if series[e.ts] > series[e.ts - HOLD] else "DOWN"),
]

ev = Evaluator(resolver, baselines)
v = ev.grade(preds, horizon=HOLD)

print(render_plain(v))
print()
rate = v.hit_rate * 100
print(f"coin-flip hit rate: {rate:.1f}% on {v.resolved} resolved episodes "
      f"(p = {v.p_value:.3f})")

# Smoke assertions: a no-information model must not be certified.
ok = (v.resolved > 100
      and 40.0 <= rate <= 60.0
      and (v.p_value >= 0.05 or not v.beats_all_baselines()))
print("PASS — toolkit grades a non-origin model and refuses to certify "
      "an information-free one" if ok else
      "FAIL — smoke expectations violated")
sys.exit(0 if ok else 1)
