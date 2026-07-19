# Examples

Two runnable case studies, chosen to demonstrate opposite verdicts.

| Example | What it grades | Verdict | Extra deps |
|---|---|---|---|
| [`coinflip_smoke.py`](coinflip_smoke.py) | A literal seeded coin flip on a synthetic random walk | **Refused** — 53.2%, p = 0.135 | none |
| [`weather_forecast_skill/`](weather_forecast_skill/) | A public weather service's own forecasts, 5 cities, 1 year, real data | **Certified** — beats every baseline at leads 1–7 days | `requests` |

Run them:

```bash
python examples/coinflip_smoke.py

pip install -r examples/weather_forecast_skill/requirements.txt
cd examples/weather_forecast_skill && python run_weather_demo.py
```

Both exit non-zero if their expected outcome does not hold, so they double
as regression tests for the grading machinery.

## Not included

The two replay-verification scripts from the origin trading system
(Wikipedia pageviews, prediction markets) are **not** shipped here: they
re-run that system's model to regenerate its prediction stream, so they
cannot run without the origin repository. Their published figures are
reproduced exactly through this package — see Provenance in the main
[README](../README.md).
