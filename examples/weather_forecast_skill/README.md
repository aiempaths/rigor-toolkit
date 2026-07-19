# Weather forecast skill — the positive control

The other rigor_toolkit case studies are refusals. This one is the
certification, and it exists because a grader that has only ever said
"no" hasn't demonstrated that it can recognise skill when skill is real.

It grades **a public weather service's own forecasts** — predictions this
library's author did not produce — asking a question meteorologists
already grade themselves on: will tomorrow's daily maximum temperature be
higher or lower than today's?

## Result

One year, five cities on four continents, four lead times.

```
  lead   hit rate     RMSE     beats every baseline?
   1d      82.2%    1.73C      YES
   3d      78.6%    1.81C      YES
   5d      71.0%    2.42C      YES
   7d      61.8%    3.09C      YES
```

1,790 resolved episodes at one-day lead, p ≈ 2e-177 against a coin flip,
and it beats persistence, anti-persistence, climatology, in-sample
majority and always-UP. Skill decays with lead exactly as meteorology
says it should.

Full numbers and every baseline column: [RESULTS.md](RESULTS.md).
The rules, fixed in advance: [PREREGISTRATION.md](PREREGISTRATION.md).

## Run it

```bash
pip install requests          # only extra dependency; the toolkit needs none
python run_weather_demo.py
```

First run fetches from Open-Meteo (free, no API key) and caches to
`data/`. Later runs are offline and reproduce the published numbers even
after the upstream archive rolls forward.

```bash
python run_weather_demo.py --span 60      # quicker, smaller window
```

Exit code is 0 only if the positive control passes.

## How it works

| | |
|---|---|
| **Forecasts** | `historical-forecast-api`, hourly `temperature_2m_previous_dayN` — what the model run *N days earlier* predicted. Aggregated to a daily max over the location's local day. |
| **Ground truth** | `archive-api` (ERA5 reanalysis) — a **different endpoint and a different product**, so forecasts and truth cannot be the same numbers. |
| **Climatology** | Ten complete years (2015–2024) of ERA5 daily maxima, averaged by day-of-year and smoothed ±7 days. The window ends before the test window opens. |

**Prediction** is `sign(forecast_lead_N(T) − forecast_lead_N(T−1))`; both
endpoints are genuine N-day-lead forecasts, so nothing the model sees
postdates its own issue time.

**Persistence** uses the last day-over-day change *fully observed before
the forecast was issued* — for lead N that is day T−N−1 versus T−N−2,
never a day still in progress at issue.

Each `(city, target day)` is one episode; consecutive days are distinct
questions about distinct days, so the dedup window is zero-width.

## Stage 0 aborts the run unless

- forecast error grows **monotonically with lead** (1.73 → 3.09 °C) — the
  test that would fail if lead labels were scrambled or the analysis were
  leaking into long leads
- forecasts and reanalysis are demonstrably different series (only 3.6%
  of values coincide exactly)
- UP/DOWN labels recompute correctly from raw temperatures
- ties resolve, stay in the denominator, and credit no rule
- no city/lead exceeds 10% missing data

## Two honest findings

**Persistence scored 44.3% — below chance.** Day-over-day temperature
mean-reverts, so its mirror is the strongest trivial rule here, and the
pre-registered baseline set had left that mirror out. That is exactly the
Wikipedia trap this toolkit was built to catch, committed while
pre-registering the demonstration about catching it. Anti-persistence was
added post-hoc, disclosed as Amendment 2, and the forecast still beat it.
Adding a baseline can only raise the bar.

**The decay endpoint was never reached.** The archive retains just seven
days of prior runs, so the lead time at which forecast skill actually
vanishes is beyond what this can test. Skill isn't unlimited — it's
untested past day 7, and the report says so.
