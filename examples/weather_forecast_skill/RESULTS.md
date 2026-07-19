# Weather Forecast Skill — rigor_toolkit positive control

_Generated 2026-07-19. Window 2025-07-06 to 2026-07-05 (365 days), 5 cities. Pre-registered in [PREREGISTRATION.md](PREREGISTRATION.md) (locked before any code; Amendment 1 removed the 10-day horizon for data-availability reasons before any grading ran)._

## What this is

Every other published rigor_toolkit case study is a null: the toolkit refused three models and certified none. A referee that has only ever said "no" is not demonstrably a referee. This grades a **public weather service's own forecasts** — predictions the toolkit's author did not produce — in a domain where genuine skill is known to exist at short range.

## Stage 0 — data integrity (all must pass before grading)

- lead integrity: forecast error grows monotonically with lead — 1d=1.73C, 3d=1.81C, 5d=2.42C, 7d=3.09C
- independent sources: only 3.6% of forecasts exactly equal the reanalysis (1825 matched days) — a forecast archive and a reanalysis archive, not one series twice
- label sanity: 198 UP/DOWN labels recomputed from raw temperatures for Denver and matched
- tie handling: equal-temperature days resolve as ties that stay in the denominator and credit no rule
- coverage: worst city/lead is London lead 1d at 0.0% missing (limit 10%)

## Results by lead time

| Lead | Episodes | Resolved | Correct | Hit rate | p (vs coin) | Beats ALL baselines |
|---|---|---|---|---|---|---|
| 1 day | 1790 | 1790 | 1472 | 82.2% | 2.13e-177 | **YES** |
| 3 day | 1788 | 1788 | 1405 | 78.6% | 4.37e-137 | **YES** |
| 5 day | 1785 | 1785 | 1268 | 71.0% | 5.63e-73 | **YES** |
| 7 day | 1792 | 1792 | 1107 | 61.8% | 8.31e-24 | **YES** |

## Skill decay

```
  lead   hit rate     RMSE
   1d      82.2%    1.73C  ############################......
   3d      78.6%    1.81C  ###########################.......
   5d      71.0%    2.42C  ########################..........
   7d      61.8%    3.09C  #####################.............
```

## Baselines, graded on the identical episodes

**Lead 1 day** — model 1472/1790 (82.2%)

| Rule | Correct | Rate | Rationale |
|---|---|---|---|
| persistence | 793/1790 | 44.3% | last fully-observed day-over-day change continues; the standard short-range null in meteorology |
| anti-persistence | 946/1790 | 52.8% | last fully-observed change REVERSES; day-over-day temperature is mean-reverting, so this is the strongest trivial rule here (added post-hoc, Amendment 2 — it raises the bar, never lowers it) |
| seasonal-naive | 889/1790 | 49.7% | direction of the ten-year seasonal normal into the target date; the standard long-range null |
| always-majority-outcome (in-sample) | 940/1790 | 52.5% | upper bound on every constant rule |
| always-UP | 940/1790 | 52.5% | constant rule, reported for completeness |

**Lead 3 day** — model 1405/1788 (78.6%)

| Rule | Correct | Rate | Rationale |
|---|---|---|---|
| persistence | 867/1788 | 48.5% | last fully-observed day-over-day change continues; the standard short-range null in meteorology |
| anti-persistence | 871/1788 | 48.7% | last fully-observed change REVERSES; day-over-day temperature is mean-reverting, so this is the strongest trivial rule here (added post-hoc, Amendment 2 — it raises the bar, never lowers it) |
| seasonal-naive | 894/1788 | 50.0% | direction of the ten-year seasonal normal into the target date; the standard long-range null |
| always-majority-outcome (in-sample) | 928/1788 | 51.9% | upper bound on every constant rule |
| always-UP | 928/1788 | 51.9% | constant rule, reported for completeness |

**Lead 5 day** — model 1268/1785 (71.0%)

| Rule | Correct | Rate | Rationale |
|---|---|---|---|
| persistence | 870/1785 | 48.7% | last fully-observed day-over-day change continues; the standard short-range null in meteorology |
| anti-persistence | 865/1785 | 48.5% | last fully-observed change REVERSES; day-over-day temperature is mean-reverting, so this is the strongest trivial rule here (added post-hoc, Amendment 2 — it raises the bar, never lowers it) |
| seasonal-naive | 888/1785 | 49.7% | direction of the ten-year seasonal normal into the target date; the standard long-range null |
| always-majority-outcome (in-sample) | 932/1785 | 52.2% | upper bound on every constant rule |
| always-UP | 932/1785 | 52.2% | constant rule, reported for completeness |

**Lead 7 day** — model 1107/1792 (61.8%)

| Rule | Correct | Rate | Rationale |
|---|---|---|---|
| persistence | 895/1792 | 49.9% | last fully-observed day-over-day change continues; the standard short-range null in meteorology |
| anti-persistence | 847/1792 | 47.3% | last fully-observed change REVERSES; day-over-day temperature is mean-reverting, so this is the strongest trivial rule here (added post-hoc, Amendment 2 — it raises the bar, never lowers it) |
| seasonal-naive | 894/1792 | 49.9% | direction of the ten-year seasonal normal into the target date; the standard long-range null |
| always-majority-outcome (in-sample) | 935/1792 | 52.2% | upper bound on every constant rule |
| always-UP | 935/1792 | 52.2% | constant rule, reported for completeness |

## Power

Episodes needed before a claim is testable at all — perfect_record: 5, 70pct: 37, 65pct: 67, 60pct: 153.

| Lead | Resolved | Smallest edge this n could detect |
|---|---|---|
| 1 day | 1790 | 51.9% (+1.9 pp over chance) |
| 3 day | 1788 | 51.9% (+1.9 pp over chance) |
| 5 day | 1785 | 51.9% (+1.9 pp over chance) |
| 7 day | 1792 | 51.9% (+1.9 pp over chance) |

## Verdict

**Rule 1 (positive control): PASS.** At 1-day lead the published forecast beats every trivial rule, including persistence, at p < 0.01. The toolkit certifies genuine skill in a third party's predictions — the first published case where it says yes.

**Rule 2 (skill decay):** the forecast beats every baseline at lead(s) [1, 3, 5, 7]. Hit rate and forecast error both degrade monotonically with lead time.

The decay endpoint was **not reached**: the data source retains only seven days of prior model runs, so the lead time at which skill actually vanishes lies beyond what this demonstration can test. Skill is not unlimited; it is untested past day 7.

**Rule 3 (power):** detection floors are tabulated above. Every verdict here rests on thousands of resolved episodes, so these are not small-sample results — but adjacent days remain weather-correlated, so the effective sample is somewhat smaller than the episode count. That applies identically to the model and every baseline and cannot manufacture a skill difference.

## Limits, stated plainly

- **Direction only.** This grades the sign of the day-over-day change, not magnitude or calibration. A forecast can be directionally right and numerically poor.
- **Issue timestamps are not exposed** by the API. No-look-ahead rests on the documented semantics of the previous-run variables plus the Stage 0 test that error grows with lead — which would fail if the analysis were leaking into long leads.
- **One year, five cities.** No claim of generality beyond that.
- Ties (equal temperatures) resolve and credit no rule, model and baselines alike.
