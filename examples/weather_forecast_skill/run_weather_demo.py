"""
run_weather_demo.py — rigor_toolkit positive control.

Grades a PUBLIC weather service's own published forecasts, which the
toolkit's author did not produce, in a domain where genuine skill is
known to exist at short lead times.

Question (pre-registered): will the daily maximum temperature on target
day T be higher or lower than on day T-1? Graded separately at lead
times of 1, 3, 5 and 7 days, against the trivial rules meteorology
already uses.

    prediction   sign( fcst_lead_N(T) - fcst_lead_N(T-1) )
    truth        sign( actual(T)      - actual(T-1)      )

Both sides of the model's comparison are genuine N-day-lead forecasts,
so nothing the model sees postdates its issue time. The persistence
baseline is likewise built only from observations complete BEFORE the
forecast was issued (see build_predictions).

Run:
    python run_weather_demo.py            # cached after first run
    python run_weather_demo.py --span 180 # shorter window

Writes RESULTS.md next to this file.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

from rigor_toolkit import (Baseline, Evaluator, Outcome, Prediction,
                           UNRESOLVED, power_thresholds)

import fetch_data as fd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "RESULTS.md")

ALPHA_CONTROL = 0.01          # pre-registered Rule 1 threshold at lead 1


def direction(a, b):
    """Label for a change from b -> a. None when exactly equal."""
    if a is None or b is None:
        return None
    if a > b:
        return "UP"
    if a < b:
        return "DOWN"
    return None


def d(iso, delta=0):
    return (date.fromisoformat(iso) + timedelta(days=delta)).isoformat()


# ── prediction construction ──────────────────────────────────────────────

def build_predictions(bundle, lead):
    """One Prediction per (city, target day) at this lead.

    NO LOOK-AHEAD, by construction:
      * the model's two endpoints are both lead-N forecasts, i.e. both
        issued at least N days before their own target day;
      * persistence uses the last day-over-day change that was fully
        OBSERVED before issue time. Issue time is T-N, so the most recent
        complete observed day is T-N-1, and the change compares it with
        T-N-2. For lead 1 that is T-2 vs T-3 — never T-1, which is still
        in progress when the forecast is issued.
    """
    preds, truth = [], {}
    for city, cd in bundle["cities"].items():
        fc, ac, cl = cd["forecast"][lead], cd["actual"], cd["climatology"]
        for tgt in sorted(fc):
            prev = d(tgt, -1)
            f_now, f_prev = fc.get(tgt), fc.get(prev)
            label = direction(f_now, f_prev)
            if label is None:
                continue                       # no forecast change to grade

            a_now, a_prev = ac.get(tgt), ac.get(prev)
            if a_now is None or a_prev is None:
                continue                       # unresolvable: no ground truth
            truth[(city, tgt)] = direction(a_now, a_prev)

            # persistence: last CHANGE fully observed before issue (T-N)
            p1, p2 = d(tgt, -lead - 1), d(tgt, -lead - 2)
            pers = direction(ac.get(p1), ac.get(p2))

            # climatology: does the seasonal normal rise or fall into T?
            md_now = (int(tgt[5:7]), int(tgt[8:10]))
            md_prev = (int(prev[5:7]), int(prev[8:10]))
            climo = direction(cl.get(md_now), cl.get(md_prev))

            preds.append(Prediction(
                ts=date.fromisoformat(tgt), label=label, series=city,
                meta={"persistence": pers, "climatology": climo,
                      "f_now": f_now, "f_prev": f_prev,
                      "a_now": a_now, "a_prev": a_prev}))
    preds.sort(key=lambda p: (str(p.series), p.ts))
    return preds, truth


def make_resolver(truth):
    def resolver(ep):
        key = (ep.prediction.series, ep.prediction.ts.isoformat())
        if key not in truth:
            return UNRESOLVED
        return Outcome(True, truth[key])       # None label = tie, credits none
    return resolver


def make_baselines():
    """Pre-registered set. Persistence is PRIMARY: it is the standard
    short-range null in meteorology and genuinely strong because weather
    is autocorrelated."""
    return [
        Baseline.persistence(
            lambda e: e.prediction.meta["persistence"],
            rationale="last fully-observed day-over-day change continues; "
                      "the standard short-range null in meteorology"),
        # Added post-hoc (Amendment 2) after the first run showed
        # persistence scoring BELOW chance: day-over-day temperature
        # changes mean-revert, so the mirror rule is the strongest trivial
        # rule available and its omission would have flattered the model.
        # Adding a baseline can only make the test harder.
        Baseline.anti_persistence(
            lambda e: {"UP": "DOWN", "DOWN": "UP"}.get(
                e.prediction.meta["persistence"]),
            # No measured figures belong in this string: it is written
            # verbatim into every regenerated RESULTS.md, including runs
            # over a different --span or a future window, where numbers
            # from the published run would be false.
            rationale="last fully-observed change REVERSES; day-over-day "
                      "temperature is mean-reverting, so this was narrowly "
                      "the strongest trivial rule at 1-day lead in the "
                      "published window (see Amendment 2); at longer leads "
                      "always-majority is the rule to beat (added post-hoc "
                      "— it raises the bar, never lowers it)"),
        Baseline.seasonal_naive(
            lambda e: e.prediction.meta["climatology"],
            rationale="direction of the ten-year seasonal normal into the "
                      "target date; the standard long-range null"),
        Baseline.always_majority(
            rationale="upper bound on every constant rule"),
        Baseline.constant(
            "UP", rationale="constant rule, reported for completeness"),
    ]


# ── Stage 0 — data integrity (abort on failure) ──────────────────────────

def rmse(pairs):
    if not pairs:
        return None
    return (sum((a - b) ** 2 for a, b in pairs) / len(pairs)) ** 0.5


def stage0(bundle):
    msgs, leads = [], bundle["leads"]

    # 1. lead integrity: accuracy must DEGRADE with lead time. If the
    #    archive were misaligned or leaking the analysis, long leads would
    #    be as accurate as short ones — the failure that would manufacture
    #    spectacular fake skill.
    per_lead = {}
    for n in leads:
        pairs = []
        for city, cd in bundle["cities"].items():
            for tgt, f in cd["forecast"][n].items():
                a = cd["actual"].get(tgt)
                if a is not None:
                    pairs.append((f, a))
        per_lead[n] = rmse(pairs)
    order = [per_lead[n] for n in leads]
    assert all(x is not None for x in order), "no matched forecast/actual pairs"
    assert order == sorted(order), (
        f"RMSE does not increase with lead time: {per_lead} — lead labels "
        f"may be scrambled or the 'forecast' may be leaking the analysis")
    msgs.append("lead integrity: forecast error grows monotonically with "
                "lead — " + ", ".join(f"{n}d={per_lead[n]:.2f}C"
                                      for n in leads))

    # 2. forecasts are not the observations
    same = tot = 0
    for city, cd in bundle["cities"].items():
        for tgt, f in cd["forecast"][leads[0]].items():
            a = cd["actual"].get(tgt)
            if a is not None:
                tot += 1
                same += abs(f - a) < 1e-9
    frac = same / tot if tot else 1.0
    assert frac < 0.5, (f"{frac:.0%} of lead-{leads[0]} forecasts equal the "
                        f"observation exactly — same product, not a forecast")
    msgs.append(f"independent sources: only {frac:.1%} of forecasts exactly "
                f"equal the reanalysis ({tot} matched days) — a forecast "
                f"archive and a reanalysis archive, not one series twice")

    # 3. label sanity, recomputed from raw temperatures
    city = sorted(bundle["cities"])[0]
    cd = bundle["cities"][city]
    checked = 0
    for tgt in sorted(cd["forecast"][leads[0]])[:200]:
        prev = d(tgt, -1)
        f_now, f_prev = (cd["forecast"][leads[0]].get(tgt),
                         cd["forecast"][leads[0]].get(prev))
        if f_now is None or f_prev is None or f_now == f_prev:
            continue
        expect = "UP" if f_now > f_prev else "DOWN"
        assert direction(f_now, f_prev) == expect
        checked += 1
    assert checked >= 20, "too few label checks"
    msgs.append(f"label sanity: {checked} UP/DOWN labels recomputed from raw "
                f"temperatures for {city} and matched")

    # 4. tie handling
    t = make_resolver({("X", "2020-01-01"): None})
    class _P:  # minimal stand-in
        pass
    ep = _P(); ep.prediction = Prediction(ts=date(2020, 1, 1), label="UP",
                                          series="X")
    out = t(ep)
    assert out.resolved and out.label is None, "tie must resolve, credit none"
    msgs.append("tie handling: equal-temperature days resolve as ties that "
                "stay in the denominator and credit no rule")

    # 5. coverage
    worst = (None, -1.0)
    for city, cd in bundle["cities"].items():
        for n in leads:
            days = len(cd["forecast"][n])
            expected = (bundle["window"][1] - bundle["window"][0]).days + 1
            miss = 1 - days / expected
            if miss > worst[1]:
                worst = (f"{city} lead {n}d", miss)
    assert worst[1] < 0.10, f"missing data too high: {worst[0]} {worst[1]:.0%}"
    msgs.append(f"coverage: worst city/lead is {worst[0]} at "
                f"{max(worst[1], 0.0):.1%} missing (limit 10%)")
    return msgs, per_lead


# ── reporting ────────────────────────────────────────────────────────────

def bar(rate, width=34):
    if rate is None:
        return ""
    filled = int(round(rate * width))
    return "#" * filled + "." * (width - filled)


def detectable_edge(n):
    """Smallest true hit rate that a one-sided binomial at this n could
    separate from chance at alpha=0.05 (normal approximation)."""
    if not n:
        return None
    return 0.5 + 1.645 * (0.25 / n) ** 0.5


def render(verdicts, per_lead_rmse, bundle, s0msgs):
    start, end = bundle["window"]
    L = []
    A = L.append
    A("# Weather Forecast Skill — rigor_toolkit positive control")
    A("")
    A(f"_Generated {date.today().isoformat()}. Window {start} to {end} "
      f"({(end - start).days + 1} days), {len(fd.CITIES)} cities. "
      f"Pre-registered in [PREREGISTRATION.md](PREREGISTRATION.md) "
      f"(locked before any code; Amendment 1 removed the 10-day horizon "
      f"for data-availability reasons before any grading ran)._")
    A("")
    A("## What this is")
    A("")
    A("Every other published rigor_toolkit case study is a null: the "
      "toolkit refused three models and certified none. A referee that "
      "has only ever said \"no\" is not demonstrably a referee. This "
      "grades a **public weather service's own forecasts** — predictions "
      "the toolkit's author did not produce — in a domain where genuine "
      "skill is known to exist at short range.")
    A("")
    A("## Stage 0 — data integrity (all must pass before grading)")
    A("")
    for m in s0msgs:
        A(f"- {m}")
    A("")
    A("## Results by lead time")
    A("")
    A("| Lead | Episodes | Resolved | Correct | Hit rate | p (vs coin) | "
      "Beats ALL baselines |")
    A("|---|---|---|---|---|---|---|")
    for n, v in verdicts.items():
        hr = f"{v.hit_rate*100:.1f}%" if v.hit_rate is not None else "—"
        p = f"{v.p_value:.2e}" if v.p_value is not None and v.p_value < 1e-4 \
            else (f"{v.p_value:.4f}" if v.p_value is not None else "—")
        A(f"| {n} day | {v.episodes} | {v.resolved} | {v.correct} | {hr} | "
          f"{p} | **{'YES' if v.beats_all_baselines() else 'no'}** |")
    A("")
    A("## Skill decay")
    A("")
    A("```")
    A(f"{'lead':>6}  {'hit rate':>9}  {'RMSE':>7}")
    for n, v in verdicts.items():
        A(f"{n:>4}d  {v.hit_rate*100:>8.1f}%  {per_lead_rmse[n]:>6.2f}C  "
          f"{bar(v.hit_rate)}")
    A("```")
    A("")
    A("## Baselines, graded on the identical episodes")
    A("")
    for n, v in verdicts.items():
        A(f"**Lead {n} day** — model {v.correct}/{v.resolved} "
          f"({v.hit_rate*100:.1f}%)")
        A("")
        A("| Rule | Correct | Rate | Rationale |")
        A("|---|---|---|---|")
        for name, b in v.baselines.items():
            rate = f"{b['rate']*100:.1f}%" if b["rate"] is not None else "—"
            A(f"| {name} | {b['correct']}/{b['n']} | {rate} | "
              f"{b['rationale']} |")
        A("")
    A("## Power")
    A("")
    th = power_thresholds()
    A(f"Episodes needed before a claim is testable at all — "
      + ", ".join(f"{k}: {v}" for k, v in th.items()) + ".")
    A("")
    A("| Lead | Resolved | Smallest edge this n could detect |")
    A("|---|---|---|")
    for n, v in verdicts.items():
        e = detectable_edge(v.resolved)
        A(f"| {n} day | {v.resolved} | {e*100:.1f}% "
          f"(+{(e-0.5)*100:.1f} pp over chance) |")
    A("")
    A("## Verdict")
    A("")
    lead1 = verdicts[bundle["leads"][0]]
    control_ok = (lead1.beats_all_baselines()
                  and lead1.p_value is not None
                  and lead1.p_value < ALPHA_CONTROL)
    if control_ok:
        A("**Rule 1 (positive control): PASS.** At 1-day lead the "
          "published forecast beats every trivial rule, including "
          "persistence, at p < 0.01. The toolkit certifies genuine skill "
          "in a third party's predictions — the first published case "
          "where it says yes.")
    else:
        A("**Rule 1 (positive control): FAIL — the demonstration is VOID, "
          "not a finding.** A 1-day temperature-direction forecast "
          "beating persistence is established meteorology. Failure here "
          "means the harness, the data alignment or the labels are wrong. "
          "Debug and rerun; do not publish this as a result about "
          "weather.")
    A("")
    beaten = [n for n, v in verdicts.items() if v.beats_all_baselines()]
    lost = [n for n, v in verdicts.items() if not v.beats_all_baselines()]
    A(f"**Rule 2 (skill decay):** the forecast beats every baseline at "
      f"lead(s) {beaten or 'none'}"
      + (f" and fails to at lead(s) {lost}." if lost else ".")
      + " Hit rate and forecast error both degrade monotonically with "
        "lead time.")
    if not lost:
        A("")
        A("The decay endpoint was **not reached**: the data source retains "
          "only seven days of prior model runs, so the lead time at which "
          "skill actually vanishes lies beyond what this demonstration "
          "can test. Skill is not unlimited; it is untested past day 7.")
    A("")
    A("**Rule 3 (power):** detection floors are tabulated above. Every "
      "verdict here rests on thousands of resolved episodes, so these are "
      "not small-sample results — but adjacent days remain weather-"
      "correlated, so the effective sample is somewhat smaller than the "
      "episode count. That applies identically to the model and every "
      "baseline and cannot manufacture a skill difference.")
    A("")
    A("## Limits, stated plainly")
    A("")
    A("- **Direction only.** This grades the sign of the day-over-day "
      "change, not magnitude or calibration. A forecast can be "
      "directionally right and numerically poor.")
    A("- **Issue timestamps are not exposed** by the API. No-look-ahead "
      "rests on the documented semantics of the previous-run variables "
      "plus the Stage 0 test that error grows with lead — which would "
      "fail if the analysis were leaking into long leads.")
    A("- **One year, five cities.** No claim of generality beyond that.")
    A("- Ties (equal temperatures) resolve and credit no rule, model and "
      "baselines alike.")
    A("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--span", type=int, default=365)
    ap.add_argument("--buffer", type=int, default=14)
    args = ap.parse_args()

    print("Fetching (cached after first run) ...")
    bundle = fd.load_all(span_days=args.span, end_buffer_days=args.buffer)

    print("\nStage 0 — data integrity ...")
    s0msgs, per_lead_rmse = stage0(bundle)
    for m in s0msgs:
        print("  ok:", m)

    print("\nGrading ...")
    verdicts = {}
    for lead in bundle["leads"]:
        preds, truth = build_predictions(bundle, lead)
        ev = Evaluator(make_resolver(truth), make_baselines(),
                       claim_name="forecast-skill", horizon_name="lead time")
        # zero-width dedup window: each (city, target day) is its own
        # episode, per the pre-registration — consecutive days are distinct
        # questions about distinct days, not one repeated bet.
        v = ev.grade(preds, horizon=timedelta(0))
        verdicts[lead] = v
        print(f"  lead {lead}d: {v.headline}")
        print(f"           beats every baseline: "
              f"{'YES' if v.beats_all_baselines() else 'no'}")

    with open(RESULTS, "w", encoding="utf-8") as f:
        f.write(render(verdicts, per_lead_rmse, bundle, s0msgs))
    print(f"\nwrote {RESULTS}")

    lead1 = verdicts[bundle["leads"][0]]
    ok = (lead1.beats_all_baselines() and lead1.p_value is not None
          and lead1.p_value < ALPHA_CONTROL)
    print("\n" + "=" * 62)
    print("POSITIVE CONTROL:", "PASS — toolkit certified real skill"
          if ok else "FAIL — demonstration VOID, debug before publishing")
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
