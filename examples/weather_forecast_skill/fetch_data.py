"""
fetch_data.py — Open-Meteo data acquisition for the forecast-skill demo.

Three separate things are fetched, deliberately from TWO different
endpoints so that forecasts and ground truth cannot be the same numbers:

  FORECASTS   historical-forecast-api, hourly `temperature_2m_previous_dayN`
              -> the value predicted for that hour by the model run N days
              earlier. Aggregated to a daily maximum over the location's
              LOCAL calendar day (timezone=auto).

  ACTUALS     archive-api (ERA5 reanalysis), daily `temperature_2m_max`.
              A different endpoint and a different product: reanalysis,
              not forecast.

  CLIMATOLOGY archive-api, ten complete years (2015-2024) of daily maxima,
              averaged by day-of-year and smoothed +/-7 days, giving the
              seasonal normal used by the climatology baseline. The
              climatology window ends before the test window begins, so
              no test-period observation informs its own baseline.

Everything is cached as raw JSON under ./data/ — the demo is reproducible
after the upstream archive rolls forward, and reruns cost no requests.

Only dependency: requests (for its current CA bundle; the toolkit itself
needs nothing).
"""

import json
import os
import time
from collections import defaultdict
from datetime import date, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data")

FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Pre-registered: 5 locations spanning continents, hemispheres and climate
# regimes. Fixed before any result was seen; not chosen for forecast quality.
CITIES = {
    "London":  (51.5074,  -0.1278),   # temperate maritime
    "Tokyo":   (35.6762, 139.6503),   # humid subtropical
    "Denver":  (39.7392,-104.9903),   # semi-arid continental / mountain
    "Nairobi": (-1.2921,  36.8219),   # equatorial highland
    "Sydney":  (-33.8688, 151.2093),  # temperate oceanic, S hemisphere
}

LEADS = (1, 3, 5, 7)          # pre-registered (10 dropped, see Amendment 1)
CLIMO_YEARS = ("2015-01-01", "2024-12-31")
TIMEOUT = 90
RETRIES = 3


def _get(url, params, cache_key):
    """GET with disk cache and bounded retries. Cached responses are
    returned verbatim so a rerun reproduces the published numbers."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, cache_key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    last = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                return data
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:                      # network, timeout, json
            last = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {cache_key}: {last}")


def test_window(end_buffer_days=14, span_days=365):
    """Most recent `span_days` complete days, ending `end_buffer_days`
    before today so every target day is resolvable at every lead."""
    end = date.today() - timedelta(days=end_buffer_days)
    start = end - timedelta(days=span_days - 1)
    return start, end


def fetch_forecast_daily_max(city, start, end, leads=LEADS):
    """{lead: {date_iso: forecast daily max}} — hourly previous-run values
    aggregated to the local-calendar-day maximum."""
    lat, lon = CITIES[city]
    vars_ = ",".join(f"temperature_2m_previous_day{n}" for n in leads)
    data = _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "hourly": vars_, "timezone": "auto",
    }, f"forecast_{city}_{start}_{end}")

    hourly = data["hourly"]
    times = hourly["time"]
    out = {}
    for n in leads:
        key = f"temperature_2m_previous_day{n}"
        buckets = defaultdict(list)
        for i, ts in enumerate(times):
            v = hourly[key][i]
            if v is not None:
                buckets[ts[:10]].append(v)          # ts is local time
        # a partial day cannot yield a trustworthy daily maximum
        out[n] = {d: max(vs) for d, vs in buckets.items() if len(vs) >= 20}
    return out


def fetch_actual_daily_max(city, start, end):
    """{date_iso: observed daily max} from ERA5 reanalysis."""
    lat, lon = CITIES[city]
    data = _get(ARCHIVE_URL, {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "temperature_2m_max", "timezone": "auto",
    }, f"actual_{city}_{start}_{end}")
    daily = data["daily"]
    return {d: v for d, v in zip(daily["time"], daily["temperature_2m_max"])
            if v is not None}


def fetch_climatology(city, years=CLIMO_YEARS, smooth=7):
    """{(month, day): seasonal normal daily max}, from ten complete years
    that END BEFORE the test window opens."""
    lat, lon = CITIES[city]
    data = _get(ARCHIVE_URL, {
        "latitude": lat, "longitude": lon,
        "start_date": years[0], "end_date": years[1],
        "daily": "temperature_2m_max", "timezone": "auto",
    }, f"climo_{city}_{years[0]}_{years[1]}")

    daily = data["daily"]
    by_md = defaultdict(list)
    for d, v in zip(daily["time"], daily["temperature_2m_max"]):
        if v is not None:
            by_md[(int(d[5:7]), int(d[8:10]))].append(v)
    raw = {md: sum(vs) / len(vs) for md, vs in by_md.items()}

    # smooth over a +/-`smooth`-day window on the day-of-year circle so the
    # normal is a seasonal trend, not ten years of single-date noise
    ordered = sorted(raw)                          # (month, day) ascending
    idx = {md: i for i, md in enumerate(ordered)}
    n = len(ordered)
    out = {}
    for md, i in idx.items():
        vals = [raw[ordered[(i + k) % n]]
                for k in range(-smooth, smooth + 1)]
        out[md] = sum(vals) / len(vals)
    return out


def load_all(leads=LEADS, span_days=365, end_buffer_days=14):
    """Fetch everything for every city. Returns a dict the demo consumes.

    Actuals are fetched with a lead-sized head start: the persistence
    baseline needs observations from strictly BEFORE each forecast's issue
    time, which is up to max(leads)+2 days before the target day.
    """
    start, end = test_window(end_buffer_days, span_days)
    pad = max(leads) + 3
    a_start = start - timedelta(days=pad)

    bundle = {"window": (start, end), "actual_start": a_start,
              "leads": tuple(leads), "cities": {}}
    for city in CITIES:
        print(f"  [{city}] forecasts...", end="", flush=True)
        fc = fetch_forecast_daily_max(city, start, end, leads)
        print(" actuals...", end="", flush=True)
        ac = fetch_actual_daily_max(city, a_start, end)
        print(" climatology...", end="", flush=True)
        cl = fetch_climatology(city)
        bundle["cities"][city] = {"forecast": fc, "actual": ac,
                                  "climatology": cl}
        print(f" ok ({len(ac)} observed days)")
    return bundle
