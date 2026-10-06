#!/opt/hermes/.venv/bin/python
"""Compute the best outdoor window today and print a one-line nudge.

Reads coordinates from GREENHOUR_LAT / GREENHOUR_LON and the timezone from
GREENHOUR_TZ. The nudge text is printed for the agent to relay to the user;
this script does not send messages itself.

    python nudge.py                 # human line + JSON on stdout
    python nudge.py --horizon 4     # only look 4 hours ahead
    python nudge.py --json          # machine-readable only
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "_lib"))

from greenhour import config as ghconfig  # noqa: E402
from greenhour import weather  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Best outdoor window today.")
    parser.add_argument("--horizon", type=int, default=8, help="hours ahead to search")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()

    cfg = ghconfig.load()
    try:
        cfg.require("lat", "lon")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        window = weather.best_window(
            cfg.lat, cfg.lon, cfg.tz, horizon_hours=args.horizon
        )
    except Exception as exc:  # noqa: BLE001 - network/weather failure is not fatal
        print(f"error: could not fetch forecast: {exc}", file=sys.stderr)
        return 1

    if window is None:
        message = weather.no_window_message()
        payload = {"ok": False, "message": message}
    else:
        message = weather.nudge_message(window)
        payload = {
            "ok": True,
            "message": message,
            "window": {
                "start": window.start.isoformat(),
                "end": window.end.isoformat(),
                "label": window.label,
                "temp_c": window.temp_c,
                "precip_prob": window.precip_prob,
                "wind_kmh": window.wind_kmh,
                "conditions": weather.describe_code(window.code),
            },
        }

    if not args.json:
        print(message)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
