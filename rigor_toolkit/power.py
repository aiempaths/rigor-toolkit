"""
rigor_toolkit.power — exact binomial p and sample-size-for-claim math.

binom_p_one_sided and n_needed are ports of the identical functions in
the origin system's evidence machinery (verified against its published
thresholds: 70% -> 37, 65% -> 67, 60% -> 153 at alpha=0.05 one-sided,
power=0.80). power_thresholds() generalizes the hardcoded [5, 37, 67,
153] list: claim strengths, alpha and power are parameters.
"""

import math
from statistics import NormalDist


def binom_p_one_sided(k, n, p0=0.5):
    """Exact one-sided P(X >= k | n, p0)."""
    if p0 == 0.5:
        return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n
    return sum(math.comb(n, i) * p0 ** i * (1 - p0) ** (n - i)
               for i in range(k, n + 1))


def n_needed(p1, alpha=0.05, power=0.80, p0=0.5):
    """Resolved episodes needed to detect a true hit rate p1 against the
    null p0 at one-sided `alpha` with the given power (normal
    approximation, same formula the origin system uses)."""
    za = NormalDist().inv_cdf(1 - alpha)
    zb = NormalDist().inv_cdf(power)
    return math.ceil(
        ((za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))) ** 2)
        / (p1 - p0) ** 2)


def min_perfect_record(alpha=0.05, p0=0.5):
    """Smallest n where an unbroken record is significant at `alpha`
    (n consecutive hits under p0 has probability p0**n)."""
    return math.ceil(math.log(alpha) / math.log(p0))


def power_thresholds(claims=(0.70, 0.65, 0.60), alpha=0.05, power=0.80,
                     p0=0.5):
    """{'perfect_record': n_min, '70pct': ..., ...} — episodes needed
    before each claim strength is even testable. Defaults reproduce the
    origin system's published [5, 37, 67, 153]."""
    out = {"perfect_record": min_perfect_record(alpha, p0)}
    for c in claims:
        out[f"{round(c * 100):d}pct"] = n_needed(c, alpha, power, p0)
    return out
