from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from greenhour import weather

TZ = "UTC"


def _payload(hours: list[dict]) -> dict:
    keys = ["time", "temperature_2m", "precipitation_probability", "weather_code",
            "wind_speed_10m", "is_day"]
    return {"hourly": {k: [h[k] for h in hours] for k in keys}}


def _hour(day: datetime, temp=20.0, precip=0, code=1, wind=5.0, is_day=1) -> dict:
    return {
        "time": day.strftime("%Y-%m-%dT%H:%M"),
        "temperature_2m": temp,
        "precipitation_probability": precip,
        "weather_code": code,
        "wind_speed_10m": wind,
        "is_day": is_day,
    }


def test_describe_code():
    assert weather.describe_code(0) == "clear"
    assert weather.describe_code(61) == "light rain"
    assert weather.describe_code(9999) == "weather code 9999"


def test_picks_the_most_comfortable_hour():
    now = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo(TZ))
    hours = [
        _hour(now + timedelta(hours=0), temp=8, precip=60, wind=30),   # cold, wet, windy
        _hour(now + timedelta(hours=2), temp=21, precip=0, wind=4),    # perfect
        _hour(now + timedelta(hours=4), temp=30, precip=0, wind=4),    # too hot
    ]
    window = weather.best_window(0, 0, TZ, now=now, payload=_payload(hours))
    assert window is not None
    assert window.start.hour == 12
    assert window.temp_c == 21


def test_skips_rainy_and_night_hours():
    now = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo(TZ))
    hours = [
        _hour(now + timedelta(hours=1), precip=90),               # too wet
        _hour(now + timedelta(hours=2), is_day=0, precip=0),      # night
    ]
    assert weather.best_window(0, 0, TZ, now=now, payload=_payload(hours)) is None


def test_respects_the_horizon():
    now = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo(TZ))
    hours = [
        _hour(now + timedelta(hours=1), temp=30),    # within horizon, poor
        _hour(now + timedelta(hours=9), temp=21),    # perfect but beyond horizon
    ]
    window = weather.best_window(0, 0, TZ, now=now, horizon_hours=4, payload=_payload(hours))
    assert window is not None
    assert window.start.hour == 11


def test_handles_empty_payload():
    assert weather.best_window(0, 0, TZ, payload={"hourly": {}}) is None


def test_messages_are_one_line():
    window = weather.Window(
        start=datetime(2026, 10, 6, 16, 0, tzinfo=ZoneInfo(TZ)),
        end=datetime(2026, 10, 6, 17, 0, tzinfo=ZoneInfo(TZ)),
        temp_c=19.4, precip_prob=10, wind_kmh=8.0, code=2, score=0.0,
    )
    message = weather.nudge_message(window)
    assert "\n" not in message
    assert "16:00–17:00" in message
    assert "19 °C" in message
    assert "partly cloudy" in message
