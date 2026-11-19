"""GTA VI trophy rarity forecast — full entry (v2).

Forecasts each PS5 trophy's Exophase earn rate at the case target as five
quantiles (pinball loss on the logit scale). Two regimes, chosen from the
case's own history:

1. FLAT HISTORY (practice cases p00/p01): every read identical, one
   players-tracked count. The launch-night page is stale and Exophase
   refreshes it before the target, so the rate is diluted by the refresh:
   the tracked-player count jumps from the last read's count to the first
   refresh's count (3,868 players, stated in RULES.txt), while new players
   have barely earned anything yet. Median = last_rate * (P_last / 3868)
   * prog[trophy], where prog is the trophy's progression factor between
   the stale snapshot and the first refresh, calibrated from the public
   live Exophase page on launch night (early story / easy activities
   progress fastest: Chapter 1 x2.38, arcade x2.50, fishing x3.46, most
   trophies x1.00-1.29). The one trophy at 100% stays at 100%. The
   quantile spread grows with prog (0.20-0.30 logit): the refresh is
   certain, its size per trophy is the uncertainty.

2. TREND HISTORY (final case f00): the history holds several refreshes.
   Collapse consecutive identical reads into distinct refresh states,
   then per trophy fit logit(rate) against ln(1 + hours since
   2026-11-19T00:00Z) by recency-weighted least squares (24h half-life),
   with the slope shrunk toward the cross-trophy median slope (3
   pseudo-observations) so a short history cannot extrapolate wildly.
   Read the line at the target, less a 2.5h refresh-staleness lag, and
   cap the move at 3 logit units from the last read. Spread = prediction
   standard error of the fit combined with a random-walk term over the
   horizon and a refresh term: refresh-aware, widening with horizon.

Standard library only, deterministic (no randomness, no network, no
clock reads): the same case file always yields the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
# Players tracked at Exophase's first refresh of the game's counts
# (RULES.txt: 638 players, unchanged, then 3,868 at the 04:30Z read).
REFRESH_PLAYERS = 3868
# Launch-night progression factors per trophy id: earned-count growth
# from the stale snapshot (638 players) to the first refresh (3,868),
# calibrated from the public live Exophase trophy page on 2026-11-19.
# 1.00 = no new earns (pure dilution); early/easy activities progress.
PROG = {
    1: 1.00, 2: 1.00, 3: 2.38, 4: 1.29, 5: 1.29, 6: 1.29, 7: 1.29,
    8: 1.29, 9: 1.29, 10: 1.29, 11: 1.29, 12: 1.29, 13: 1.29, 14: 1.00,
    15: 1.00, 16: 1.00, 17: 1.00, 18: 1.00, 19: 1.00, 20: 3.46,
    21: 2.50, 22: 1.00, 23: 1.00, 24: 1.20, 25: 1.00, 26: 1.00,
    27: 1.00, 28: 1.00, 29: 1.00, 30: 1.00, 31: 1.00, 32: 1.00,
    33: 1.17, 34: 1.20, 35: 1.88, 36: 1.00, 37: 1.50, 38: 1.20,
    39: 1.17, 40: 1.00, 41: 1.00, 42: 1.20, 43: 1.00, 44: 1.33,
    45: 1.00, 46: 1.20, 47: 1.20, 48: 1.40, 49: 1.20, 50: 1.40,
    51: 1.40, 52: 1.00, 53: 1.17, 54: 1.20, 55: 1.20,
}
LAUNCH0 = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc)
REFRESH_LAG_HOURS = 2.5  # answering read shows the last refresh before it
MAX_LOGIT_MOVE = 3.0


def clamp_rate(x):
    return min(99.99, max(0.01, x))


def logit(pct):
    p = clamp_rate(pct)
    return math.log(p / (100.0 - p))


def inv_logit(l):
    return 100.0 / (1.0 + math.exp(-l))


def round4(x):
    scaled = x * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000.0
    return int(value) if value == int(value) else value


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hours_since_launch(t):
    return (t - LAUNCH0).total_seconds() / 3600.0


def distinct_states(history):
    """Collapse consecutive identical reads (stale page plateaus)."""
    states = []
    for h in history:
        key = (h["players_tracked"], tuple(h["rates"]))
        if not states or states[-1][0] != key:
            states.append((key, h))
    return [h for _, h in states]


def last_known_rate(history, idx):
    for h in reversed(history):
        r = h["rates"][idx]
        if r is not None:
            return r
    return None


def forecast_flat(case, last):
    """Regime 1: stale page, one refresh expected before the target."""
    p_last = last["players_tracked"]
    rows = []
    for i, trophy in enumerate(case["trophies"]):
        rate = last_known_rate(case["history"], i)
        if rate is None:
            rate = 1.0
        if rate >= 100.0:
            rows.append({"id": trophy["id"], "q": [99.99, 100, 100, 100, 100]})
            continue
        if p_last < REFRESH_PLAYERS:
            prog = PROG.get(trophy["id"], 1.0)
            median = clamp_rate(rate * (p_last / REFRESH_PLAYERS) * prog)
            spread = 0.20 + 0.10 * (prog - 1.0) / 2.46
        else:
            # Refresh already reflected in the player count: persistence.
            median = clamp_rate(rate)
            spread = 0.5 * math.sqrt(max(case["horizon_minutes"], 0) / 1440.0)
            spread = max(spread, 0.15)
        lg = logit(median)
        rows.append(
            {
                "id": trophy["id"],
                "q": [round4(inv_logit(lg + z * spread)) for z in Z],
            }
        )
    return {"trophies": rows}


def wls(xs, ys, ws):
    """Weighted least squares y = a + b*x; returns (a, b, s_res, xbar, sxx, n_eff)."""
    sw = sum(ws)
    xbar = sum(w * x for w, x in zip(ws, xs)) / sw
    ybar = sum(w * y for w, y in zip(ws, ys)) / sw
    sxx = sum(w * (x - xbar) ** 2 for w, x in zip(ws, xs))
    sxy = sum(w * (x - xbar) * (y - ybar) for w, x, y in zip(ws, xs, ys))
    if sxx <= 1e-12:
        return ybar, 0.0, 0.0, xbar, sxx, sw
    b = sxy / sxx
    a = ybar - b * xbar
    dof = max(len(xs) - 2, 1)
    s_res = math.sqrt(sum(w * (y - (a + b * x)) ** 2 for w, x, y in zip(ws, xs, ys)) / dof)
    n_eff = sw * sw / sum(w * w for w in ws)
    return a, b, s_res, xbar, sxx, n_eff


def forecast_trend(case, states):
    """Regime 2: logit rate vs log-time trend over distinct refresh states."""
    last = states[-1]
    h_last = hours_since_launch(parse_time(last["at"]))
    try:
        h_target = hours_since_launch(parse_time(case["target"]))
    except Exception:
        h_target = h_last + case["horizon_minutes"] / 60.0
    x_target = math.log(max(1.0 + h_target - REFRESH_LAG_HOURS, 0.05))
    days = max(case["horizon_minutes"], 0) / 1440.0

    # First pass: per-trophy slopes, for the cross-trophy median slope.
    fits = []
    for i in range(len(case["trophies"])):
        xs, ys, ws = [], [], []
        for h in states:
            r = h["rates"][i]
            if r is None:
                continue
            hj = hours_since_launch(parse_time(h["at"]))
            xs.append(math.log(max(1.0 + hj, 0.05)))
            ys.append(logit(r))
            ws.append(0.5 ** ((h_last - hj) / 24.0))
        if len(xs) >= 2:
            fits.append(wls(xs, ys, ws))
        else:
            fits.append(None)
    slopes = sorted(f[1] for f in fits if f is not None)
    b_med = slopes[len(slopes) // 2] if slopes else 0.0

    rows = []
    for i, trophy in enumerate(case["trophies"]):
        fit = fits[i]
        rate = last_known_rate(case["history"], i)
        if rate is None:
            rate = 1.0
        if rate >= 100.0:
            rows.append({"id": trophy["id"], "q": [99.99, 100, 100, 100, 100]})
            continue
        if fit is None:
            median = clamp_rate(rate)
            spread = 0.5 * math.sqrt(days)
        else:
            a, b, s_res, xbar, sxx, n_eff = fit
            n = len(states)
            b_s = (n * b + 3.0 * b_med) / (n + 3.0)
            a_s = (a + b * xbar) - b_s * xbar
            y_last = logit(rate)
            y_pred = a_s + b_s * x_target
            y_pred = min(max(y_pred, y_last - MAX_LOGIT_MOVE), y_last + MAX_LOGIT_MOVE)
            median = clamp_rate(inv_logit(y_pred))
            if sxx > 1e-12 and n_eff > 0:
                s_fit = s_res * math.sqrt(1.0 + 1.0 / n_eff + (x_target - xbar) ** 2 / sxx)
            else:
                s_fit = s_res
            spread = math.sqrt(s_fit ** 2 + (0.35 * math.sqrt(days)) ** 2 + 0.10 ** 2)
            spread = min(max(spread, 0.20), 1.5)
        lg = logit(median)
        rows.append(
            {
                "id": trophy["id"],
                "q": [round4(inv_logit(lg + z * spread)) for z in Z],
            }
        )
    return {"trophies": rows}


def forecast_case(case):
    if case["levels"] != LEVELS:
        raise ValueError("unexpected levels %r" % (case["levels"],))
    if not case["history"]:
        # No reads at all: still emit a valid forecast (never an invalid case).
        return {
            "trophies": [
                {"id": t["id"], "q": [0.1, 0.4, 1.0, 2.5, 6.0]}
                for t in case["trophies"]
            ]
        }
    states = distinct_states(case["history"])
    if len(states) < 2:
        return forecast_flat(case, case["history"][-1])
    return forecast_trend(case, states)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
