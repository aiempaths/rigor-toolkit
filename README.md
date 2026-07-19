# rigor_toolkit

**Honest grading for timestamped predictions.**

You have a model that predicts something at a point in time — tomorrow's
demand, Sunday's result, next hour's load, the direction of a price. You
want to know whether it actually works. The usual way to find out is to
compute a hit rate, and the usual result is that you fool yourself.

This library is the part that stops you. You bring a stream of
`(timestamp, label)` predictions and a function that looks up what really
happened. It returns **one computed verdict** — and it is built to refuse.

Zero runtime dependencies. Python 3.9+. MIT.

```bash
pip install -e .
python examples/coinflip_smoke.py
```

---

## Track record

Four public case studies: **three refusals and one certification.** The
mix is the point. A grader that only ever says "no" hasn't demonstrated
that it can recognise skill — it might just be a rock with NO written on
it.

| Case study | What was graded | Verdict |
|---|---|---|
| [Weather forecasts](examples/weather_forecast_skill/) | A public met service's own forecasts — 5 cities, 4 continents, 1 year | **Certified** — beats every baseline at every lead |
| Wikipedia pageviews | A pattern matcher on a year of hourly traffic | Refused — scored 71.6%, but seasonal-naive scores 92.5% |
| Prediction markets | The same matcher against settled contract prices | Refused — 48.3% vs the market's own 47.0%, p = 0.688 |
| [Coin flip](examples/coinflip_smoke.py) | A literal seeded coin flip (synthetic control) | Refused — 53.2%, p = 0.135 |

### The certification

[`examples/weather_forecast_skill/`](examples/weather_forecast_skill/)
grades a public weather service's own published forecasts — predictions
this library's author did not produce — asking whether tomorrow's daily
maximum temperature will be higher or lower than today's.

```
  lead   hit rate     RMSE
   1d      82.2%    1.73C  ############################......
   3d      78.6%    1.81C  ###########################.......
   5d      71.0%    2.42C  ########################..........
   7d      61.8%    3.09C  #####################.............
```

The forecast beats **every** trivial rule at every lead — 1,790 resolved
episodes at one-day lead, p ≈ 2e-177 — and its skill decays with lead
time exactly as meteorology says it should. The toolkit certifies it.

Two findings from that demonstration are worth reading, because both are
recorded in its
[pre-registration](examples/weather_forecast_skill/PREREGISTRATION.md)
rather than smoothed away:

- **Persistence scored 44.3% — below chance.** Day-over-day temperature
  mean-reverts, so "yesterday's change continues" is *anti*-predictive,
  which makes its mirror the strongest trivial rule available. The
  original baseline set omitted that mirror — the same trap the Wikipedia
  case study exists to warn about, committed while pre-registering the
  demonstration about avoiding it. Anti-persistence was added post-hoc
  and disclosed as such. Adding a baseline can only raise the bar, and
  the forecast still cleared it.
- **The decay endpoint was unreachable.** The data source retains only
  seven days of prior model runs, so the lead time at which forecast
  skill actually dies lies beyond what could be tested. The report says
  so, rather than implying skill is unlimited.

---

## The three ways hit rates lie

**1. Correlated predictions inflate your sample.** Five hundred signals
that are really forty independent bets is a sample size of forty. The
toolkit collapses overlapping same-direction predictions into *episodes*,
and only the episode count is ever treated as `n`.

**2. Unresolved predictions quietly disappear.** A trade still open, a
forecast whose target date hasn't arrived. Dropping them biases the
record; counting them as wins is worse. Here, unresolved episodes are
never correct, and resolved-but-tied outcomes stay in the denominator
while crediting no one.

**3. The baseline was chosen because it was easy to beat.** This is the
big one, and it gets its own section.

---

## Baseline selection is the load-bearing decision

Nothing is auto-selected. You choose your baselines and you write down
*why* — the rationale travels with the number into the verdict.
`Verdict.beats_all_baselines()` is strict: **lose one column, no claim.**

Two of the refusals above show why the strictness earns its keep.

**The trap.** A pattern-matching model was pointed at a year of hourly
Wikipedia pageview traffic. It scored **71.6%** directional accuracy over
345 resolved episodes, crushing the pre-specified persistence baseline at
27.0%. Graded against that one baseline, it "worked."

But the series has a ~24-hour cycle and the horizon sat near the cycle's
reversal, so the honest nulls were anti-persistence (73.0%) and
seasonal-naive — *"same as this hour yesterday"* — at **92.5%**. The
model had rediscovered the fact that humans sleep. A weaker baseline set
publishes a false positive; the full set publishes "no signal above naive
baselines."

**The hard null.** The same machinery was pointed at prediction-market
prices, where the market's own current price is the sharpest number
available. The primary baseline was therefore the market-favorite
direction — not a coin flip, not always-up. Result: model 48.3%, market
price 47.0%, in-sample majority 49.7%, over 149 episodes, p = 0.688.
Everything clusters at 50% exactly as martingale prices predict, and the
verdict says so plainly. Against a soft baseline the same numbers could
have been spun as "beats the market."

Hence `Baseline.reference_estimate()` — for domains carrying their own
efficient estimate (market price, bookmaker line, consensus forecast).
Where one exists, it is the primary baseline. If you can rationalize
omitting the strongest trivial rule in your domain, this toolkit cannot
help you. If you include it, the toolkit will refuse to certify what
isn't there.

---

## Usage

```python
from rigor_toolkit import Evaluator, Baseline, Prediction, Outcome, UNRESOLVED

preds = [Prediction(ts=t, label="UP", confidence=0.8), ...]

def resolver(ep):                       # your domain's ground truth
    truth = lookup(ep.prediction.ts, horizon=10)
    if truth is None:
        return UNRESOLVED               # not knowable yet
    return Outcome(True, truth)         # Outcome(True, None) = tie

ev = Evaluator(resolver, baselines=[
    Baseline.persistence(my_last_move_label,
                         rationale="momentum is the obvious null here"),
    Baseline.always_majority(),
])

verdict = ev.grade(preds, horizon=10)
print(verdict.headline)                 # computed sentence — quote it
print(verdict.beats_all_baselines())    # the only question that matters
```

`ts` can be a datetime or a bar index; `horizon` must be addable to it.

**Correlated streams** — several markets on one underlying event, several
stations in one region — get a second dedup layer: set `series` and
`group` on each `Prediction` and pass `group_horizon=` to `grade()`.

**Built-in baselines:** `constant`, `always_majority`, `persistence`,
`anti_persistence`, `seasonal_naive`, `reference_estimate`. All but
`always_majority` take a label function you supply, because only you know
how to read "the last move" or "one season ago" in your domain.

**Power math.** `power_thresholds()` tells you how many resolved episodes
you need before a claim of a given strength is even testable — at the
default α = 0.05 one-sided and 80% power, that's 37 episodes for a 70%
claim, 67 for 65%, and 153 for 60%. Knowing you *cannot yet conclude
anything* is a result.

**Narration.** `render_plain(verdict)` is deterministic and dependency-
free. `LLMNarrator(your_completion_fn)` wraps any callable and degrades to
`None` on failure. Both only phrase what was already computed — neither
can derive a number.

---

## It makes no assumptions about your model

The toolkit never sees your model, only its output stream. This is
verified by grading a literal seeded coin flip on a synthetic random
walk: `examples/coinflip_smoke.py`. Expected outcome — ~50% hit rate, p
far from significance, and the model **not** certified.

That example is the point, not a demo. A grading harness that can't say
"no" to a coin flip can't be trusted to say "yes" to anything.

---

## What it refuses to contain

No prediction model. No auto-selected baselines. No position sizing,
account simulation, price feeds, or publishing mechanics. No narrator that
computes. Those omissions are deliberate — this library grades, and does
nothing else.

---

## Status and honest limits

**v0.1.0.** The API is small and stable, but this has been exercised on
four domains, not hundreds. Expect rough edges at the margins.

**The record is three refusals and one certification** — see Track record
above. The refusals show the strictness works; the certification shows the
machinery can still recognise real skill when it is present. Both halves
were necessary.

**It grades direction, not magnitude.** Labels are categorical. If you
need calibration, Brier scores, or P&L, this is the wrong tool — or
rather, an incomplete one. Directional accuracy and payoff can rank
strategies in opposite orders, and this library measures only the first.

**Episode independence is your judgement, not the toolkit's.** It will
collapse what you tell it to collapse. Deciding whether two predictions
are really one bet is a domain question, and getting it wrong is the
fastest way to inflate a sample.

---

## Provenance

Extracted from the evidence machinery of a live trading research system,
where it was used to grade that system's own predictions and repeatedly
refuse them. The extraction is replay-verified: both cross-domain case
studies were re-graded entirely through this package and reproduced every
published figure exactly (346/345/247 and four baseline counts;
149/149/72 and four baseline counts). Those replay scripts need the origin
repository to regenerate their prediction streams, so they aren't shipped
here; the coin-flip smoke test and the weather demonstration are
standalone and included.

---

## Contact

Telegram: [@agentics](https://t.me/agentics)

## License

MIT — see [LICENSE](LICENSE).
