"""Speech-to-text via a hosted open-weight Whisper model.

Groq serves ``whisper-large-v3-turbo`` on an OpenAI-compatible endpoint, so
transcription stays an open-weight model without us running inference. The
host is swappable: point ``GREENHOUR_ASR_URL`` at any compatible server.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from .config import Config

DEFAULT_ASR_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_ASR_MODEL = "whisper-large-v3-turbo"


def _endpoint() -> str:
    return os.environ.get("GREENHOUR_ASR_URL", DEFAULT_ASR_URL)


def transcribe_bytes(
    data: bytes,
    filename: str,
    cfg: Config,
    *,
    content_type: str = "audio/ogg",
    language: str | None = None,
) -> str:
    if not cfg.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    form = {"model": os.environ.get("GREENHOUR_ASR_MODEL", DEFAULT_ASR_MODEL)}
    if language:
        form["language"] = language
    response = httpx.post(
        _endpoint(),
        headers={"Authorization": f"Bearer {cfg.groq_api_key}"},
        files={"file": (filename, data, content_type)},
        data=form,
        timeout=120.0,
    )
    response.raise_for_status()
    return (response.json().get("text") or "").strip()


def transcribe_file(path: Path, cfg: Config, **kwargs) -> str:
    suffix = path.suffix.lstrip(".").lower() or "ogg"
    content_type = {
        "ogg": "audio/ogg",
        "oga": "audio/ogg",
        "opus": "audio/ogg",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "flac": "audio/flac",
        "webm": "audio/webm",
    }.get(suffix, "application/octet-stream")
    return transcribe_bytes(
        path.read_bytes(), path.name, cfg, content_type=content_type, **kwargs
    )
