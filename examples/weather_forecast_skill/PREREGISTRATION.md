# Weather Forecast Skill — pre-registration (LOCKED 2026-07-18)

> **AMENDMENT 1 — 2026-07-18, made BEFORE any grading was run.**
> The 10-day horizon is **dropped**; horizons are now **1, 3, 5, 7 days**.
>
> Reason (structural, not result-driven): the data source retains only
> seven days of prior model runs. Probing `temperature_2m_previous_dayN`
> on Open-Meteo returns 100% coverage for N = 1–7 and **0% (all null)**
> for N ≥ 8. No 10-day-lead forecast is retrievable at any location, so
> the horizon cannot be tested rather than having been tested and
> removed. No result of any kind had been computed when this amendment
> was made.
>
> **Consequence, stated honestly:** the demonstration may not reach the
> lead time at which forecast skill actually vanishes. Temperature-
> direction forecasts plausibly retain skill through day 7, so the
> expected "skill dies here" endpoint may be absent from the curve. If
> the forecast beats every baseline at all four horizons, that is the
> result, and the report must say that the decay endpoint was
> unreachable — not imply skill is unlimited.
>
> No other value in this document is amended. Horizons 1, 3, 5, 7 were
> already pre-registered; only the unreachable one is removed, and no
> new horizon is added in its place (adding 2, 4 or 6 opportunistically
> would be fishing for a friendlier curve).

> **AMENDMENT 2 — 2026-07-19, made AFTER the first run. Disclosed as
> post-hoc.** A fifth baseline, **anti-persistence**, is added to the set.
>
> Reason: the first run showed persistence scoring **44.3% at lead 1 —
> below chance.** Day-over-day maximum temperature mean-reverts, so "the
> last change continues" is anti-predictive, and its mirror image is
> therefore the strongest trivial rule available **at 1-day lead**. The
> pre-registered set omitted it.
>
> (Measured after the rerun, correcting the estimate above: anti-
> persistence scores **52.8%** at lead 1 — narrowly the strongest rule
> there, against always-majority's 52.5%. At leads 3, 5 and 7 it scores
> 48.7%, 48.5% and 47.3%, *below* always-majority's ~52%, which is the
> rule to beat at longer leads. The omission therefore mattered
> specifically at short lead; an unqualified "strongest trivial rule"
> would be wrong.)
>
> That omission is exactly the error this toolkit's Wikipedia case study
> exists to warn about — grading against a chosen baseline while a better
> trivial rule goes untested — and it was committed while pre-registering
> the demonstration about catching it. Recorded rather than quietly
> corrected.
>
> **Why this is not fishing:** adding a baseline can only make
> `beats_all_baselines()` harder to satisfy. Fishing means dropping hard
> baselines or adding easy ones; this raises the bar. The result is
> reported after the harder test, and if the model had failed it, the
> failure would have been published.
>
> No other value is amended: same locations, horizons, window, labels,
> episode rule and decision rules.

Question: does a public weather service's own published forecast beat the
trivial rules meteorologists already grade against — and at what lead
time does that skill disappear?

This is a **positive control** for rigor_toolkit. Every published case
study so far is a null: the toolkit has refused three models and
certified none. A referee that has never said "yes" is not demonstrably
a referee. This demonstration grades predictions the toolkit's author
did not produce, in a domain where genuine skill is known to exist at
short range and known to vanish at long range, and asks the toolkit to
say so.

Decision authority: the maintainer. Approval of this document is the gate
for writing any code. Nothing below may change after the first run.

## What is being predicted

**Will the daily maximum temperature on target day T be higher or lower
than on day T−1?** Label: `UP` / `DOWN`. Exactly equal (to the data's
reported precision) resolves as a tie: it stays in the denominator and
credits no rule, model or baseline alike.

Judgment call, stated: day-over-day *direction of change* was chosen
over "above/below climatological normal" because persistence is a
genuinely strong competitor for it (weather is autocorrelated), which is
what makes the test bite. The anomaly framing would hand climatology a
50/50 null by construction and make the comparison less informative.

## Fixed configuration

- **Data source:** Open-Meteo. Archived forecast runs from its historical
  forecast archive; ground truth from its separate reanalysis archive
  endpoint. Free, no API key, no authentication. **Forecasts and actuals
  must come from different endpoints** — Stage 0 verifies this.
- **Locations (5, fixed before any result is seen):** London, Tokyo,
  Denver, Nairobi, Sydney. Chosen on a stated principle — spread across
  continents, hemispheres and climate regimes (maritime, humid
  subtropical, semi-arid continental/mountain, equatorial highland,
  temperate oceanic) — so that no single weather regime drives the
  result, and so same-day cross-city correlation is negligible.
  Not chosen for expected forecast quality.
- **Lead times (horizons):** 1, 3, 5, 7 days (10 removed — see Amendment
  1 at the top). Each horizon is graded **separately** and produces its
  own verdict object.
- **Window:** the most recent 365 complete days available in the archive
  at run time, ending at least 14 days before the run date so every
  target day is resolvable at every horizon. Exact dates recorded in the
  report.
- **Expected sample:** ~365 target days × 5 cities = ~1825 predictions
  per horizon before ties and missing data.
- **Master seed:** 20260718 (used only if any sampling or tie-breaking
  is required; the pipeline is otherwise deterministic).

## Episode structure

Judgment call, stated: each (city, target-date) pair is **one episode**.
Consecutive target days are *not* collapsed, because each is a distinct
question about a distinct day with its own independently observed
outcome — unlike a trading signal repeated across days about the same
open position. Cities are separate `series` and are not collapsed across,
on the stated ground that the chosen locations are far enough apart that
same-day outcomes are effectively independent.

The honest cost of this choice: adjacent days' outcomes remain
autocorrelated (weather persists), so the effective sample is somewhat
smaller than the episode count. This is stated in the report rather than
corrected for, and it applies identically to the model and every
baseline, so it cannot manufacture a skill difference.

## Baselines (all graded on the identical episodes)

1. **Persistence (PRIMARY)** — the day-over-day change observed most
   recently before the forecast was issued continues in the same
   direction. Rationale: the standard short-range null in meteorology,
   and genuinely strong because weather is autocorrelated.
2. **Climatology / seasonal-naive** — the direction implied by the
   climatological normal trend for that calendar date at that location
   (is the seasonal normal rising or falling on that date?). Rationale:
   the standard long-range null; at long lead times, professional
   forecasts converge toward it.
3. **Always-majority (in-sample)** — the majority observed outcome
   direction. Rationale: upper bound on every constant rule.
4. **Constant UP** — reported for completeness.

Per the standing doctrine, the forecast must beat **every** column.

## Decision rules (written before the run)

**Rule 1 — the positive control.** At horizon 1 day, the published
forecast must satisfy `beats_all_baselines() == True` with a one-sided
binomial p < 0.01 against a coin flip.
- If it does: the toolkit has certified genuine skill on a third party's
  predictions. This is the demonstration's purpose.
- **If it does not: the demonstration is VOID, not a finding.** A
  one-day temperature-direction forecast beating persistence is
  established meteorology. Failure here means the harness, the data
  alignment, or the label construction is wrong. The correct response is
  to debug and re-run, and to label the re-run as such — never to
  publish "weather forecasts don't work."

**Rule 2 — skill decay.** Report `beats_all_baselines()` and the hit
rate at each of the five horizons _[four — superseded by Amendment 1]_.
The pre-registered expectation, recorded now so it can be wrong: skill is
present at 1 and 3 days, marginal at 5–7, and absent by 10 _[the 10-day
prediction is now untestable — superseded by Amendment 1; it is left
standing so the original expectation remains on the record]_. **No result
at horizons ≥ 3 voids anything** — whatever the curve does is the
finding, including a flat one.

**Rule 3 — power honesty.** At every horizon, report the resolved
episode count against `power_thresholds()`, and state the smallest true
edge the sample could have detected. A "no skill" verdict at 10 days
_[at any horizon — superseded by Amendment 1]_ must be accompanied by its
detection floor.

## Stage 0 — data integrity (abort on any failure)

These run before any grading, and any failure stops the run:

1. **No look-ahead.** For a sample of records at each horizon, assert the
   forecast's issue timestamp precedes the target day by at least the
   stated lead time. This is the single most important check: a silently
   misaligned archive would manufacture spectacular fake skill.
2. **Independent ground truth.** Assert actuals were retrieved from a
   different endpoint than forecasts, and that the two disagree at least
   somewhat (identical series would mean the "forecast" is the actual).
3. **Label sanity.** Reconstruct UP/DOWN from raw temperatures for a
   handful of hand-checked records and assert agreement.
4. **Tie handling.** Assert equal-temperature days resolve as ties that
   credit no rule and remain in the denominator.
5. **Coverage.** Assert missing-data rate per city per horizon is below
   10%, and report it; abort if any city exceeds it.

## Standing constraints

- The first run is the unbiased one. Any re-run after changing any value
  above is tuning and must be labeled as such — with the sole exception
  of a Stage 0 or Rule 1 failure, which is a bug fix and must be
  disclosed as one.
- No location, horizon, or baseline may be added, dropped, or swapped
  after seeing any result.
- The toolkit is imported read-only and unmodified. If the demonstration
  reveals a genuine toolkit bug, that fix is a separate commit, disclosed,
  and the battery is re-run from scratch.
- Raw fetched data is cached to disk and committed if small enough, so
  the result is reproducible when the upstream archive changes.
- This grades **direction only**, not magnitude or calibration. It says
  nothing about whether the forecast's temperatures are close, only
  whether its sign is right. Stated in the report.
