"""
lead_availability_probe.py — evidence for Amendment 1.

Amendment 1 of the pre-registration drops the 10-day horizon on the
grounds that the data source does not retain forecasts that far back.
That is a factual claim about Open-Meteo, and this probe is how it was
established (2026-07-18) and how a reader can re-establish it.

For a fixed city and date range it requests `temperature_2m_previous_dayN`
for N = 1..11 and reports how many hourly values come back non-null.
Expected at the time of writing: 100% coverage for N <= 7 and 0% for
N >= 8 — so no 10-day-lead forecast exists to grade, at any location.

    python lead_availability_probe.py            # live API
    python lead_availability_probe.py --saved    # archived response only

The archived response (`previous_day8_null_London.json`) is committed
alongside this script so the claim stays checkable offline if Open-Meteo
ever extends its retention.
"""

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.join(HERE, "previous_day8_null_London.json")

URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
LAT, LON = 51.5074, -0.1278          # London
START, END = "2026-06-01", "2026-06-05"


def summarize(values):
    n = len(values)
    ok = sum(1 for v in values if v is not None)
    return n, ok, (100.0 * ok / n if n else 0.0)


def probe_live():
    import requests                                  # example-only dep
    print(f"Probing {URL}\n  London, {START}..{END}\n")
    print(f"  {'lead':>6}  {'hourly values':>14}  {'non-null':>9}")
    for lead in range(1, 12):
        var = f"temperature_2m_previous_day{lead}"
        r = requests.get(URL, params={
            "latitude": LAT, "longitude": LON,
            "start_date": START, "end_date": END,
            "hourly": var, "timezone": "auto"}, timeout=60)
        if r.status_code != 200:
            print(f"  {lead:>4}d   HTTP {r.status_code}")
            continue
        n, ok, pct = summarize(r.json()["hourly"][var])
        flag = "" if ok else "   <-- no data at this lead"
        print(f"  {lead:>4}d  {n:>14}  {ok:>5} ({pct:3.0f}%){flag}")


def probe_saved():
    with open(SAVED, encoding="utf-8") as f:
        data = json.load(f)
    print(f"Archived response: {os.path.basename(SAVED)}")
    print(f"  captured: {data['_probe_meta']['captured']}")
    print(f"  request:  {data['_probe_meta']['request']}\n")
    for var, values in data["hourly"].items():
        if var == "time":
            continue
        n, ok, pct = summarize(values)
        print(f"  {var}: {ok}/{n} non-null ({pct:.0f}%)")
    lead8 = data["hourly"]["temperature_2m_previous_day8"]
    assert all(v is None for v in lead8), "expected all-null at lead 8"
    print("\n  CONFIRMED: every lead-8 value is null — an 8-day-ahead "
          "forecast\n  is not retrievable, so the pre-registered 10-day "
          "horizon was\n  unavailable rather than dropped for convenience.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--saved", action="store_true",
                    help="read the archived response instead of the API")
    args = ap.parse_args()
    probe_saved() if args.saved else probe_live()
