"""
rigor_toolkit.multi_test — family-wise and false-discovery-rate correction
for a pre-registration family.

The problem this closes: if an identity registers N strategies and reports
only the one that scored well, a nominal p = 0.02 is a near-certainty under
the null, not evidence. The family size N is the multiple-comparison
correction, and in the attestation protocol N is the number of *staked*
commitments under the identity in the window — abandoned commitments
included, because abandonment is a choice correlated with poor early
results and must not be free.

Two corrections, both standard, both computed from the family:

  Bonferroni (controls family-wise error): p_adj = min(1, N * p). Every
  registered commitment counts in N. Conservative and assumption-free.

  Benjamini-Hochberg (controls false-discovery rate): the step-up q-value.
  Less conservative than Bonferroni IN GENERAL — but see the honesty note
  below, because it buys the cherry-picker nothing.

── The honest result the design must not paper over ──────────────────────

BH only rewards you for DISCLOSING the rest of the family. For the single
smallest p-value in a family of size m, the BH q-value is

    q_(1) = min(1, m * p_(1) / 1) = min(1, m * p_(1))

which is EXACTLY the Bonferroni value. BH's leniency lives entirely in the
2nd, 3rd, … ranked hypotheses. So an identity that runs m strategies and
reveals only the single winner gets no FDR relief over Bonferroni — the
correction for a cherry-picked top result is the full m·p either way.

The relief is real only if the identity reveals the other evaluated
p-values, and even then it accrues to the lower-ranked ones. This is a
feature: the math rewards full disclosure and refuses to reward
selective disclosure. multi_test therefore reports true BH q-values when
the evaluated family is supplied, and falls back to the Bonferroni bound
(with an explicit note) when only the winner is known.

stdlib only — no numpy, no scipy. A p-value an auditor cannot reproduce
from the standard library is not an audit primitive.
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence

__all__ = [
    "bonferroni",
    "benjamini_hochberg",
    "MultiTestResult",
    "attestation_adjustment",
]


def bonferroni(p: float, family_size: int) -> float:
    """Family-wise-error-controlled adjusted p-value: min(1, m * p).

    `family_size` (m) is every registered commitment in the family, not
    only the evaluated ones. m < 1 is meaningless; m == 0 is treated as a
    family of one (no correction) so a lone honest registration is not
    punished for existing."""
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be in [0, 1], got {p}")
    m = max(1, int(family_size))
    return min(1.0, m * p)


def benjamini_hochberg(pvalues: Sequence[float],
                       family_size: Optional[int] = None) -> list:
    """Benjamini-Hochberg step-up q-values for a set of p-values.

    Returns q-values in the SAME ORDER as the input. Standard procedure:
    sort ascending, q_(i) = min over j >= i of (m/j) * p_(j), clamped to
    [0, 1] and made monotone non-decreasing in rank.

    `family_size` (m): the denominator. Defaults to len(pvalues) — the
    ordinary BH over a fully evaluated family. Pass a larger m to account
    for registered-but-unevaluated (abandoned) commitments: the missing
    p-values are treated as 1.0 (no evidence, the least significant
    possible), which is the conservative and correct handling — an
    abandoned commitment provides no evidence of an effect, and its slot
    in the family still costs the survivors a comparison. Padding with 1.0
    never changes the q-value of the winner (rank 1), so a cherry-picker
    gains nothing by abandoning quietly."""
    vals = [float(p) for p in pvalues]
    for p in vals:
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"p must be in [0, 1], got {p}")
    k = len(vals)
    if k == 0:
        return []
    m = k if family_size is None else max(k, int(family_size))
    # pad abandoned slots with p = 1.0 (no evidence)
    padded = vals + [1.0] * (m - k)

    order = sorted(range(m), key=lambda i: padded[i])
    q_sorted = [0.0] * m
    running = 1.0
    # step up from the largest p to the smallest, taking the running min
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        q = (m / rank) * padded[i]
        running = min(running, q)
        q_sorted[i] = min(1.0, running)
    # return only the q-values for the real (non-padded) inputs, in order
    return q_sorted[:k]


@dataclass(frozen=True)
class MultiTestResult:
    """One computed object; every consumer (badge, report, API) reads this
    and none re-derives a number. Mirrors verdict.Verdict's discipline: the
    headline sentence is part of the object, not re-phrased per consumer."""
    nominal_p: float
    family_size: int          # staked commitments in the window (incl. abandoned)
    n_evaluated: int          # commitments with a computed p-value
    bonferroni_p: float
    fdr_p: float              # BH q-value of this result within its family
    fdr_is_bound: bool        # True => BH could not beat Bonferroni (winner-only)
    headline: str
    method_note: str

    def clears(self, alpha: float = 0.05) -> bool:
        """True only if BOTH corrections clear alpha. The stricter of the
        two governs — a badge that passed one correction and failed the
        other would be exactly the selective reporting this module exists
        to prevent."""
        return self.bonferroni_p < alpha and self.fdr_p < alpha

    def to_dict(self) -> dict:
        return {
            "nominal_p": self.nominal_p,
            "family_size": self.family_size,
            "n_evaluated": self.n_evaluated,
            "bonferroni_p": self.bonferroni_p,
            "fdr_p": self.fdr_p,
            "fdr_is_bound": self.fdr_is_bound,
            "headline": self.headline,
            "clears_0.05": self.clears(0.05),
        }


def attestation_adjustment(nominal_p: float,
                           family_size: int,
                           evaluated_pvalues: Optional[Sequence[float]] = None,
                           *,
                           alpha: float = 0.05) -> MultiTestResult:
    """The attestation use case: correct one result's p-value for the family
    it was selected from.

    nominal_p         the winner's unadjusted one-sided p-value
    family_size       staked commitments under the identity in the window,
                      abandoned ones included (the anti-Sybil denominator)
    evaluated_pvalues if the identity discloses the p-values of ALL
                      evaluated commitments (winner included), true BH
                      q-values are computed and the winner gets any FDR
                      relief it has earned. If None, only the Bonferroni
                      bound is claimable and fdr_is_bound is set — because
                      BH cannot beat Bonferroni for a single undisclosed
                      winner (see module docstring).

    Returns a MultiTestResult whose headline is the computed sentence.
    """
    m = max(1, int(family_size))
    bonf = bonferroni(nominal_p, m)

    if evaluated_pvalues is None:
        n_eval = 1
        fdr = bonf
        fdr_is_bound = True
        note = ("Only the winning result was disclosed. BH FDR cannot "
                "improve on Bonferroni for a single cherry-picked result "
                "(q of the smallest p in a family of m is m·p, identical to "
                "Bonferroni); FDR relief requires disclosing the full "
                "evaluated family. Reported FDR p is the Bonferroni bound.")
    else:
        evaluated = [float(p) for p in evaluated_pvalues]
        n_eval = len(evaluated)
        if n_eval == 0:
            raise ValueError("evaluated_pvalues is empty; pass None instead")
        if nominal_p - min(evaluated) > 1e-12:
            raise ValueError(
                "nominal_p is not the smallest disclosed p-value; the "
                "reported winner must be the family minimum, else a better "
                "result in the family is being hidden")
        # winner's q-value within the disclosed family, family size = m
        # (padding abandoned-but-unevaluated slots with p = 1.0). The
        # winner is the minimum, so its q is the smallest q too.
        qs = benjamini_hochberg(evaluated, family_size=m)
        widx = min(range(n_eval), key=lambda i: evaluated[i])
        fdr = qs[widx]
        fdr_is_bound = False
        note = (f"{n_eval} of {m} commitments disclosed with p-values; BH "
                f"q-value computed over the disclosed family (unevaluated "
                f"slots padded to p=1.0).")

    clears = bonf < alpha and fdr < alpha
    headline = (
        f"Nominal one-sided p = {nominal_p:.4f} over a family of {m} staked "
        f"commitment(s): Bonferroni-adjusted p = {bonf:.4f}, "
        f"BH-FDR-adjusted p = {fdr:.4f}. "
        + ("Clears" if clears else "Does not clear")
        + f" alpha = {alpha}."
    )
    return MultiTestResult(
        nominal_p=float(nominal_p), family_size=m, n_evaluated=n_eval,
        bonferroni_p=bonf, fdr_p=fdr, fdr_is_bound=fdr_is_bound,
        headline=headline, method_note=note,
    )


# ── correctness self-test: exactly known answers ──────────────────────────

def selftest(verbose: bool = False) -> list:
    """Assert against hand-verifiable answers. Raises on any failure."""
    passed = []

    def ok(msg):
        passed.append(msg)
        if verbose:
            print(f"  [ok] {msg}")

    # 1. Bonferroni basics, including the design's own badge example.
    assert abs(bonferroni(0.012, 42) - 0.504) < 1e-12, "0.012 x 42 != 0.504"
    assert bonferroni(0.02, 50) == 1.0, "0.02 x 50 must clamp to 1.0"
    assert bonferroni(0.01, 1) == 0.01, "family of 1 must not adjust"
    assert bonferroni(0.01, 0) == 0.01, "family of 0 treated as 1"
    ok("Bonferroni: 0.012x42=0.504 (badge example), clamps at 1, m<=1 noop")

    # 2. BH known answer: p = [.01,.02,.03,.04,.05], m=5 -> all q = 0.05.
    q = benjamini_hochberg([0.01, 0.02, 0.03, 0.04, 0.05])
    assert all(abs(x - 0.05) < 1e-12 for x in q), f"uniform-ramp BH {q}"
    ok("BH: [.01..05]/5 -> all q = 0.05 (textbook)")

    # 3. BH ordering + a second known answer: p=[0.001, 0.5], m=2.
    q = benjamini_hochberg([0.001, 0.5])
    assert abs(q[0] - 0.002) < 1e-12 and abs(q[1] - 0.5) < 1e-12, f"{q}"
    ok("BH: [0.001, 0.5] -> [0.002, 0.5]")

    # 4. Monotonicity: q-values must be non-decreasing in p-rank.
    ps = [0.001, 0.008, 0.039, 0.041, 0.9]
    q = benjamini_hochberg(ps)
    sq = [q[i] for i in sorted(range(len(ps)), key=lambda i: ps[i])]
    assert all(sq[i] <= sq[i + 1] + 1e-12 for i in range(len(sq) - 1)), sq
    ok("BH: q-values monotone non-decreasing in rank")

    # 5. THE honesty invariant: BH q of the single smallest p in a family
    #    of m equals Bonferroni. Cherry-picking forfeits FDR relief.
    for p, m in [(0.01, 10), (0.012, 42), (0.004, 100)]:
        q_winner = benjamini_hochberg([p], family_size=m)[0]
        assert abs(q_winner - bonferroni(p, m)) < 1e-12, \
            f"winner-only BH {q_winner} != Bonferroni {bonferroni(p, m)}"
    ok("BH q of a lone winner in family m == Bonferroni (no free lunch)")

    # 6. Padding abandoned slots never helps the winner.
    q_full = benjamini_hochberg([0.001, 0.01, 0.02], family_size=3)
    q_pad = benjamini_hochberg([0.001, 0.01, 0.02], family_size=20)
    assert q_pad[0] >= q_full[0] - 1e-12, "padding must not reduce winner q"
    ok("BH: enlarging the family (abandoned slots) never lowers winner q")

    # 7. attestation_adjustment winner-only path == Bonferroni bound.
    r = attestation_adjustment(0.012, 42)
    assert abs(r.bonferroni_p - 0.504) < 1e-12 and r.fdr_is_bound and \
        abs(r.fdr_p - 0.504) < 1e-12 and not r.clears(0.05), r.headline
    ok("attestation (winner-only): 0.012/42 -> 0.504 both, does not clear")

    # 8. attestation with full disclosure: a genuinely strong winner in a
    #    small family clears; disclosing the family is what earns it.
    r2 = attestation_adjustment(0.0001, 3,
                                evaluated_pvalues=[0.0001, 0.4, 0.7])
    assert not r2.fdr_is_bound and abs(r2.bonferroni_p - 0.0003) < 1e-12 and \
        r2.clears(0.05), r2.headline
    ok("attestation (disclosed family): strong winner clears after BH")

    # 9. A winner that is not the smallest disclosed p is rejected.
    try:
        attestation_adjustment(0.3, 5, evaluated_pvalues=[0.01, 0.3])
        raise AssertionError("should have rejected non-minimal winner")
    except ValueError:
        pass
    ok("attestation: winner must be the smallest disclosed p-value")

    return passed


if __name__ == "__main__":
    for _ in selftest(verbose=True):
        pass
    print(f"\nall {len(selftest())} multi_test self-tests passed")
