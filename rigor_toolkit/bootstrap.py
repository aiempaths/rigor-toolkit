"""
rigor_toolkit.bootstrap — correlation-corrected effective sample size and
block-bootstrap inference for resolved episodes.

The problem this closes (the "Row-11 fix"): a naive binomial treats every
resolved episode as one independent trial. Two things break that:

  * serial correlation — consecutive episodes on one asset share a market
    regime, so they are not independent even when their holding windows do
    not overlap in time;
  * cross-sectional correlation — a BTC episode and a SOL episode resolving
    the same week move together (joint drawdowns), so they are closer to
    one trial than two.

Counting them as independent inflates the sample size and shrinks the
p-value. This module reports the honest degrees of freedom.

Two numbers, deliberately distinct:

  N_capacity = floor(total live span / H) per stream, summed. The
    theoretical CEILING — the most non-overlapping holds that could fit in
    the calendar. It is not a sample size; it is an upper bound on one.

  N_eff — the correlation-corrected effective sample size, estimated as
    the variance-ratio  N_eff = p(1-p) / Var_block(mean)  where
    Var_block is the variance of the pooled hit rate under a circular block
    bootstrap that resamples whole time-blocks (preserving serial
    correlation) jointly across streams (preserving cross-sectional
    correlation). For genuinely independent trials N_eff -> N; for
    correlated ones N_eff < N, and the ratio N_eff / N is the honest
    "independence discount".

The joint scheme, precisely: all resolved episodes across all streams are
ordered by timestamp into one global sequence; a circular block bootstrap
resamples contiguous blocks of that global sequence. Because episodes
close in time sit adjacent in the global order, they land in the same
blocks and their contemporaneous correlation is preserved in every
resample — no correlation model is assumed, it is carried by the data.

stdlib only (random, statistics, math). No numpy. An effective sample
size an auditor cannot reproduce from the standard library, given the
seed, is not an audit primitive; seeding is explicit and the resampler is
deterministic given (data, block_len, n_boot, seed).
"""

import math
import random
import statistics
from dataclasses import dataclass
from typing import Optional, Sequence

__all__ = [
    "episode_outcomes",
    "block_bootstrap",
    "BootstrapResult",
    "analyze_episodes",
]


# ── extraction from graded rigor_toolkit episodes ─────────────────────────

def episode_outcomes(episodes) -> dict:
    """From graded Episodes, per series: the time-ordered list of
    (ts, correct) among RESOLVED episodes only. An unresolved episode is
    not a trial and is dropped. Series id comes from prediction.series;
    episodes with series=None are pooled under the key None."""
    by_series = {}
    for e in episodes:
        if not getattr(e, "resolved", False):
            continue
        series = getattr(e.prediction, "series", None)
        by_series.setdefault(series, []).append((e.ts, 1 if e.correct else 0))
    for series in by_series:
        by_series[series].sort(key=lambda t: t[0])
    return by_series


# ── the circular block bootstrap ──────────────────────────────────────────

def _auto_block_len(n: int) -> int:
    """Default block length ~ n**(1/3), the standard rate for the block
    bootstrap (Hall/Horowitz/Jing). At least 1, at most n."""
    return max(1, min(n, round(n ** (1.0 / 3.0))))


def _circular_block_means(outcomes, block_len, n_boot, rng):
    """n_boot resampled means of a 0/1 sequence under a circular block
    bootstrap. Wraps around the end so every position is an equally likely
    block start (no edge under-sampling)."""
    n = len(outcomes)
    n_blocks = math.ceil(n / block_len)
    means = []
    for _ in range(n_boot):
        total = 0
        count = 0
        for _b in range(n_blocks):
            start = rng.randrange(n)
            for j in range(block_len):
                total += outcomes[(start + j) % n]
                count += 1
                if count >= n:            # keep resample length == n
                    break
            if count >= n:
                break
        means.append(total / count)
    return means


@dataclass(frozen=True)
class BootstrapResult:
    n_observed: int              # resolved episodes actually observed (pooled)
    n_capacity: Optional[int]    # floor(span/H) ceiling, or None if unknown
    n_eff: float                 # correlation-corrected effective sample size
    hit_rate: float              # pooled point estimate
    ci_low: float                # percentile CI on the hit rate
    ci_high: float
    block_len: int
    n_boot: int
    independence_discount: float  # n_eff / n_observed in [0, 1]
    p_value: Optional[float]     # one-sided block-bootstrap p vs baseline p0
    baseline_p0: Optional[float]
    capacity_exceeded: bool      # n_observed > n_capacity: episodes overlap
    headline: str

    def to_dict(self) -> dict:
        return {
            "n_observed": self.n_observed, "n_capacity": self.n_capacity,
            "n_eff": self.n_eff, "hit_rate": self.hit_rate,
            "ci_low": self.ci_low, "ci_high": self.ci_high,
            "block_len": self.block_len, "n_boot": self.n_boot,
            "independence_discount": self.independence_discount,
            "p_value": self.p_value, "baseline_p0": self.baseline_p0,
            "capacity_exceeded": self.capacity_exceeded,
            "headline": self.headline,
        }


def block_bootstrap(outcomes: Sequence[int],
                    *,
                    block_len: Optional[int] = None,
                    n_boot: int = 10000,
                    ci: float = 0.90,
                    baseline_p0: Optional[float] = None,
                    n_capacity: Optional[int] = None,
                    seed: int = 0) -> BootstrapResult:
    """Circular block bootstrap of a pooled 0/1 outcome sequence.

    `outcomes` is the pooled, global-time-ordered sequence of episode
    correctness (see analyze_episodes for the multi-stream ordering).

    N_eff = p(1-p) / Var(bootstrap means), clamped to [1, n]. A block that
    is long relative to the correlation length drives Var up and N_eff
    down; independent data leaves Var at the binomial value and N_eff ~ n.

    If `baseline_p0` is given, a one-sided block-bootstrap p-value is
    returned: the resamples are recentered to the null mean p0 and the
    p-value is the fraction of recentered resample means at or above the
    observed rate — a test that inherits the data's correlation instead of
    assuming independence.
    """
    obs = [int(x) for x in outcomes]
    n = len(obs)
    if n == 0:
        raise ValueError("no outcomes to bootstrap")
    L = int(block_len) if block_len else _auto_block_len(n)
    L = max(1, min(L, n))
    rng = random.Random(seed)

    p_hat = sum(obs) / n
    means = _circular_block_means(obs, L, n_boot, rng)

    var_block = statistics.pvariance(means) if n_boot > 1 else 0.0
    binom_var = p_hat * (1.0 - p_hat)
    if var_block <= 0.0:
        # degenerate (all identical outcomes, or p_hat in {0,1}): no spread
        n_eff = float(n) if binom_var == 0.0 else 1.0
    else:
        n_eff = binom_var / var_block
    n_eff = max(1.0, min(float(n), n_eff))

    # Calendar guardrail: you cannot have more independent-equivalent trials
    # than the number of NON-OVERLAPPING holds the calendar admits. If the
    # caller supplied a capacity ceiling below the observed count, the input
    # episodes overlap more than the hold allows (they were not collapsed to
    # the horizon) and the bootstrap, which sees only the 0/1 sequence, will
    # over-count. Cap N_eff at capacity and flag it — the bootstrap defends
    # against correlation, this defends against overlap.
    capacity_exceeded = False
    if n_capacity is not None and n_capacity >= 1:
        if n > n_capacity:
            capacity_exceeded = True
        n_eff = min(n_eff, float(n_capacity))

    s = sorted(means)
    lo_q = (1.0 - ci) / 2.0
    hi_q = 1.0 - lo_q
    ci_low = s[max(0, min(len(s) - 1, int(round(lo_q * (len(s) - 1)))))]
    ci_high = s[max(0, min(len(s) - 1, int(round(hi_q * (len(s) - 1)))))]

    p_value = None
    if baseline_p0 is not None:
        shift = baseline_p0 - p_hat            # recenter resamples to H0
        null_means = [m + shift for m in means]
        ge = sum(1 for m in null_means if m >= p_hat - 1e-12)
        p_value = ge / len(null_means)

    disc = n_eff / n
    hb = (f"{sum(obs)}/{n} correct ({p_hat * 100:.1f}%). Correlation-"
          f"corrected effective sample size N_eff = {n_eff:.1f} of {n} "
          f"observed (independence discount {disc * 100:.0f}%), "
          f"block length {L}.")
    if n_capacity is not None:
        hb += f" Capacity ceiling floor(span/H) = {n_capacity}."
    if capacity_exceeded:
        hb += (" WARNING: observed episodes exceed calendar capacity for "
               "the stated hold — they overlap and were not collapsed to "
               "the horizon; N_eff capped at capacity.")
    if p_value is not None:
        hb += (f" One-sided block-bootstrap p vs baseline "
               f"{baseline_p0:.3f} = {p_value:.4f}.")
    return BootstrapResult(
        n_observed=n, n_capacity=n_capacity, n_eff=n_eff, hit_rate=p_hat,
        ci_low=ci_low, ci_high=ci_high, block_len=L, n_boot=n_boot,
        independence_discount=disc, p_value=p_value,
        baseline_p0=baseline_p0, capacity_exceeded=capacity_exceeded,
        headline=hb)


def analyze_episodes(episodes,
                     *,
                     hold=None,
                     block_len: Optional[int] = None,
                     n_boot: int = 10000,
                     baseline_p0: Optional[float] = None,
                     seed: int = 0) -> BootstrapResult:
    """End-to-end: graded Episodes -> pooled global-time sequence ->
    correlation-corrected N_eff and N_capacity.

    The pooled sequence is every resolved episode across every stream,
    ordered by timestamp, so a circular block bootstrap over it preserves
    BOTH serial correlation (adjacent same-stream episodes) and
    cross-sectional correlation (different-stream episodes that resolve at
    nearby timestamps land in the same block).

    `hold` (H): if given and timestamps are numeric/subtractable, the
    capacity ceiling floor(total span / H) is computed PER STREAM and
    summed. If omitted, n_capacity is None.
    """
    by_series = episode_outcomes(episodes)
    if not by_series:
        raise ValueError("no resolved episodes to analyze")

    pooled = []
    for series, seq in by_series.items():
        pooled.extend(seq)
    pooled.sort(key=lambda t: t[0])
    outcomes = [c for _ts, c in pooled]

    n_capacity = None
    if hold is not None:
        cap = 0
        ok = True
        for series, seq in by_series.items():
            if len(seq) < 1:
                continue
            try:
                span = seq[-1][0] - seq[0][0]
                cap += int(span // hold) + 1        # inclusive of the first
            except TypeError:
                ok = False
                break
        n_capacity = cap if ok else None

    return block_bootstrap(
        outcomes, block_len=block_len, n_boot=n_boot,
        baseline_p0=baseline_p0, n_capacity=n_capacity, seed=seed)


# ── correctness self-test: known-behavior cases ───────────────────────────

def selftest(verbose: bool = False) -> list:
    """Assert the estimator behaves correctly on data with a KNOWN
    dependence structure. Uses fixed seeds so the assertions are stable."""
    passed = []

    def ok(msg):
        passed.append(msg)
        if verbose:
            print(f"  [ok] {msg}")

    rng = random.Random(12345)

    # 1. iid data -> N_eff ~ N (independence discount near 1).
    iid = [1 if rng.random() < 0.5 else 0 for _ in range(400)]
    r = block_bootstrap(iid, n_boot=4000, seed=1)
    assert 0.75 <= r.independence_discount <= 1.0, \
        f"iid discount {r.independence_discount}"
    ok(f"iid data: N_eff/N = {r.independence_discount:.2f} (~1, near-"
       f"independent)")

    # 2. Strongly serially correlated: 20 blocks of 10 identical values.
    #    ~20 independent units in 200 observations -> heavy discount.
    blocks = []
    for _ in range(20):
        v = 1 if rng.random() < 0.5 else 0
        blocks.extend([v] * 10)
    r2 = block_bootstrap(blocks, block_len=10, n_boot=4000, seed=2)
    assert r2.n_eff < 60, f"correlated N_eff too high: {r2.n_eff}"
    assert r2.independence_discount < 0.30, \
        f"correlated discount too high: {r2.independence_discount}"
    ok(f"block-correlated data (200 obs, ~20 true units): N_eff = "
       f"{r2.n_eff:.0f}, discount {r2.independence_discount * 100:.0f}%")

    # 3. Determinism given the seed.
    a = block_bootstrap(blocks, block_len=10, n_boot=2000, seed=7)
    b = block_bootstrap(blocks, block_len=10, n_boot=2000, seed=7)
    assert a.n_eff == b.n_eff and a.ci_low == b.ci_low, "not deterministic"
    ok("deterministic given (data, block_len, n_boot, seed)")

    # 4. Cross-stream redundancy via analyze_episodes: two IDENTICAL streams
    #    at the SAME timestamps must NOT count as 2x independent trials.
    #    Build minimal fake graded episodes.
    class _P:
        def __init__(self, ts, series):
            self.ts = ts
            self.series = series

    class _E:
        def __init__(self, ts, series, correct):
            self.prediction = _P(ts, series)
            self.ts = ts
            self.resolved = True
            self.correct = correct

    base = [1 if rng.random() < 0.5 else 0 for _ in range(150)]
    # BTC and SOL: identical outcomes at identical timestamps (perfectly
    # correlated, perfectly redundant)
    eps_redundant = []
    for i, c in enumerate(base):
        eps_redundant.append(_E(i, "BTC", c))
        eps_redundant.append(_E(i, "SOL", c))
    rr = analyze_episodes(eps_redundant, n_boot=4000, seed=3)
    assert rr.n_observed == 300, rr.n_observed
    # 300 pooled observations, but only ~150 independent units -> N_eff
    # must be far below 300 and near 150, not near 300.
    assert rr.n_eff < 220, f"redundant streams N_eff too high: {rr.n_eff}"
    ok(f"identical BTC=SOL streams: 300 pooled obs -> N_eff = {rr.n_eff:.0f} "
       f"(redundancy caught, not counted as 300)")

    # 5. Two INDEPENDENT streams -> N_eff close to the full pooled N.
    eps_indep = []
    for i in range(150):
        eps_indep.append(_E(i, "BTC", 1 if rng.random() < 0.5 else 0))
        eps_indep.append(_E(i, "SOL", 1 if rng.random() < 0.5 else 0))
    ri = analyze_episodes(eps_indep, n_boot=4000, seed=4)
    assert ri.independence_discount > 0.75, \
        f"independent streams discounted too hard: {ri.independence_discount}"
    ok(f"independent BTC/SOL streams: N_eff/N = "
       f"{ri.independence_discount:.2f} (~1, no false discount)")

    # 6. Capacity ceiling from hold on numeric timestamps.
    rc = analyze_episodes(eps_indep, hold=10, n_boot=1000, seed=5)
    assert rc.n_capacity is not None and rc.n_capacity > 0
    ok(f"capacity ceiling floor(span/H) computed: N_capacity = "
       f"{rc.n_capacity}")

    # 7. Block-bootstrap p-value present and sane when baseline given.
    strong = [1] * 90 + [0] * 10                # 90% vs coin flip
    rng.shuffle(strong)
    rp = block_bootstrap(strong, n_boot=4000, baseline_p0=0.5, seed=6)
    assert rp.p_value is not None and rp.p_value < 0.05, rp.p_value
    ok(f"block-bootstrap p vs 0.5 for a 90% record: p = {rp.p_value:.4f}")

    # 8. Capacity guardrail: episodes that overlap the hold get flagged and
    #    N_eff capped at capacity. Feed 60 episodes/stream spaced 1 apart
    #    with hold=10 -> only 7 non-overlapping holds fit per stream.
    eps_overlap = [_E(i, "BTC", 1 if rng.random() < 0.5 else 0)
                   for i in range(60)]
    ro = analyze_episodes(eps_overlap, hold=10, n_boot=2000, seed=8)
    assert ro.capacity_exceeded, "overlap not flagged"
    assert ro.n_eff <= ro.n_capacity + 1e-9, \
        f"N_eff {ro.n_eff} exceeds capacity {ro.n_capacity}"
    ok(f"overlap guardrail: 60 episodes at hold=10 flagged, N_eff "
       f"{ro.n_eff:.0f} capped at capacity {ro.n_capacity}")

    # 9. Properly non-overlapping episodes (spaced == hold) do NOT trip the
    #    flag and are not spuriously capped.
    eps_clean = [_E(i * 10, "BTC", 1 if rng.random() < 0.5 else 0)
                 for i in range(60)]
    rcl = analyze_episodes(eps_clean, hold=10, n_boot=2000, seed=9)
    assert not rcl.capacity_exceeded, "clean episodes wrongly flagged"
    ok(f"non-overlapping episodes (spacing=hold): not flagged, "
       f"capacity {rcl.n_capacity} >= observed {rcl.n_observed}")

    return passed


if __name__ == "__main__":
    for _ in selftest(verbose=True):
        pass
    print(f"\nall {len(selftest())} bootstrap self-tests passed")
