"""The nudge: pick the best outdoor window today from open weather data.

Uses Open-Meteo, which is free, keyless and open. The scoring is deliberately
simple and readable — this is the part a reader of the post should be able to
audit in ten seconds, and the part a closed weather API would hide behind a
paywall and a black-box "comfort index".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes, trimmed to the ones worth naming.
_WMO = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
}


def describe_code(code: int | None) -> str:
    if code is None:
        return "unknown"
    return _WMO.get(int(code), f"weather code {code}")


@dataclass
class Window:
    start: datetime
    end: datetime
    temp_c: float
    precip_prob: int
    wind_kmh: float
    code: int
    score: float

    @property
    def label(self) -> str:
        return f"{self.start:%H:%M}–{self.end:%H:%M}"


def _score(temp_c: float, precip: float, wind: float) -> float:
    """Higher is better. Comfort around 21 °C, dry, not windy."""
    return -3.0 * precip - 2.0 * abs(temp_c - 21.0) - 1.5 * max(0.0, wind - 20.0)


def fetch_hourly(lat: float, lon: float, tz: str, *, days: int = 2) -> dict:
    response = httpx.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,is_day",
            "daily": "sunrise,sunset",
            "timezone": tz,
            "forecast_days": days,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def best_window(
    lat: float,
    lon: float,
    tz: str,
    *,
    now: datetime | None = None,
    horizon_hours: int = 8,
    payload: dict | None = None,
) -> Window | None:
    """Best daylight hour in the next `horizon_hours`. None if none qualifies."""
    data = payload if payload is not None else fetch_hourly(lat, lon, tz)
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return None

    tzinfo = ZoneInfo(tz)
    current = now.astimezone(tzinfo) if now else datetime.now(tzinfo)
    horizon = current + timedelta(hours=horizon_hours)

    best: Window | None = None
    for i, iso in enumerate(times):
        try:
            slot = datetime.fromisoformat(iso).replace(tzinfo=tzinfo)
        except ValueError:
            continue
        if slot < current.replace(minute=0, second=0, microsecond=0):
            continue
        if slot > horizon:
            break
        if not (hourly.get("is_day") or [1])[i]:
            continue

        precip = float((hourly.get("precipitation_probability") or [0])[i] or 0)
        if precip >= 70:
            continue
        temp = float((hourly.get("temperature_2m") or [0])[i] or 0)
        wind = float((hourly.get("wind_speed_10m") or [0])[i] or 0)
        code = int((hourly.get("weather_code") or [0])[i] or 0)
        score = _score(temp, precip, wind)
        if best is None or score > best.score:
            best = Window(
                start=slot,
                end=slot + timedelta(hours=1),
                temp_c=temp,
                precip_prob=int(precip),
                wind_kmh=wind,
                code=code,
                score=score,
            )
    return best


def nudge_message(window: Window, *, name: str | None = None) -> str:
    """One line. The whole point is that it is short enough to act on."""
    who = f"{name}, " if name else ""
    return (
        f"🌿 {who}{window.temp_c:.0f} °C, {describe_code(window.code)}, "
        f"{window.precip_prob}% rain — clearest window is {window.label}. "
        f"Go find some grass."
    )


def no_window_message(*, reason: str = "nothing dry in the next stretch") -> str:
    return f"🌧️ No good window today ({reason}). Read a book instead — the grass will wait."
