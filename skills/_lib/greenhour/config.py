"""Runtime configuration, read from the process environment.

Everything is optional except the journal home: the nudge needs coordinates,
the extractor needs one model backend, and the public export needs GitHub
credentials. Each script checks only what it actually uses and fails with a
clear message rather than a traceback.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _env_float(name: str) -> float | None:
    raw = _env(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


@dataclass(frozen=True)
class Config:
    home: Path
    lat: float | None
    lon: float | None
    tz: str
    # Agent loop / baseline model
    openrouter_api_key: str | None
    agent_model: str
    # ASR (open-weight Whisper, hosted by Groq)
    groq_api_key: str | None
    # Fine-tuned adapter served by Tinker
    tinker_api_key: str | None
    tinker_model_path: str | None
    tinker_base_model: str
    # Optional: publish the public streak snapshot back to the repo
    github_token: str | None
    github_repo: str | None

    @property
    def db_path(self) -> Path:
        return self.home / "journal.db"

    @property
    def public_path(self) -> Path:
        return self.home / "journal.json"

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            env_names = {
                "lat": "GREENHOUR_LAT",
                "lon": "GREENHOUR_LON",
                "groq_api_key": "GROQ_API_KEY",
                "openrouter_api_key": "OPENROUTER_API_KEY",
                "tinker_api_key": "TINKER_API_KEY",
                "tinker_model_path": "TINKER_MODEL_PATH",
                "github_token": "GITHUB_TOKEN",
                "github_repo": "GITHUB_REPO",
            }
            pretty = ", ".join(env_names.get(n, n) for n in missing)
            raise RuntimeError(f"missing required configuration: {pretty}")


def load() -> Config:
    home = Path(_env("GREENHOUR_HOME", str(Path.home() / ".greenhour"))).expanduser()
    return Config(
        home=home,
        lat=_env_float("GREENHOUR_LAT"),
        lon=_env_float("GREENHOUR_LON"),
        tz=_env("GREENHOUR_TZ", "UTC") or "UTC",
        openrouter_api_key=_env("OPENROUTER_API_KEY"),
        agent_model=_env("GREENHOUR_AGENT_MODEL", "qwen/qwen3-4b:free") or "qwen/qwen3-4b:free",
        groq_api_key=_env("GROQ_API_KEY"),
        tinker_api_key=_env("TINKER_API_KEY"),
        tinker_model_path=_env("TINKER_MODEL_PATH"),
        tinker_base_model=_env("TINKER_BASE_MODEL", "Qwen/Qwen3.5-4B") or "Qwen/Qwen3.5-4B",
        github_token=_env("GITHUB_TOKEN"),
        github_repo=_env("GITHUB_REPO"),
    )
