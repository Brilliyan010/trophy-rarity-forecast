"""GTA VI trophy rarity forecast — safety entry (v1, minimal).

Forecasts each PS5 trophy's Exophase earn rate at the case target as five
quantiles. Model: the launch-night page is stale (every read identical, one
players-tracked count) and Exophase refreshes it before the target, so the
rate is diluted by the refresh: the tracked-player count jumps from the
last read's count to the first refresh's count (3,868 players, stated in
RULES.txt), while hardly any new player has earned the trophies yet, so
each rate is scaled by last_players / 3,868. The one trophy at 100% stays
at 100%. Quantiles use a fixed logit spread of 0.25, wide enough to cover
refresh timing uncertainty. Standard library only, deterministic.
"""

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
# Players tracked at Exophase's first refresh of the game's counts
# (RULES.txt: 638 players, unchanged, then 3,868 at the 04:30Z read).
REFRESH_PLAYERS = 3868
SPREAD = 0.25


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


def forecast_case(case):
    if case["levels"] != LEVELS:
        raise ValueError("unexpected levels %r" % (case["levels"],))
    if not case["history"]:
        raise ValueError("case has no history")
    last = case["history"][-1]
    dilution = last["players_tracked"] / REFRESH_PLAYERS
    rows = []
    for i, trophy in enumerate(case["trophies"]):
        rate = last["rates"][i]
        if rate is None:
            rate = 0.0
        if rate >= 100.0:
            rows.append({"id": trophy["id"], "q": [99.99, 100, 100, 100, 100]})
            continue
        median = clamp_rate(rate * dilution)
        lg = logit(median)
        rows.append(
            {
                "id": trophy["id"],
                "q": [round4(inv_logit(lg + z * SPREAD)) for z in Z],
            }
        )
    return {"trophies": rows}


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
