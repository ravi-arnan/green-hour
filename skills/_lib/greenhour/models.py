"""Model backends for turning a transcript into a FieldEntry.

Two interchangeable backends:

  * ``tinker``     -- our fine-tuned Qwen adapter, served by Thinking Machines.
  * ``openrouter`` -- any hosted chat model; used as the baseline and as the
                      fallback when the Tinker SDK or adapter is unavailable.

``backend="auto"`` prefers the tuned model and falls back to OpenRouter, so
the product keeps working before the fine-tune exists and keeps working if
Tinker has a bad day. That fallback is the whole point of keeping the two
behind one function.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import httpx

from .config import Config
from .schema import JSON_SCHEMA, FieldEntry, parse

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "You turn a short, messy spoken voice note from a walk into one structured "
    "field-journal entry. Transcribe-level noise, filler words and half "
    "sentences are expected; infer politely and never invent specifics that "
    "were not said. Write the summary in a warm, plain naturalist's voice, "
    "first person, one or two sentences. Set outdoors=true only when the "
    "speaker is plainly outside (weather, birds, being on a trail, etc.); if "
    "they are indoors or it is ambiguous, set it false. Return JSON only."
)


@dataclass
class ExtractResult:
    entry: FieldEntry
    model: str
    raw: str


def _messages(transcript: str) -> list[dict]:
    schema_hint = json.dumps(JSON_SCHEMA, ensure_ascii=False)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Voice note transcript:\n\"\"\"\n{transcript.strip()}\n\"\"\"\n\n"
                f"Return one JSON object matching this schema:\n{schema_hint}"
            ),
        },
    ]


def _extract_openrouter(transcript: str, cfg: Config) -> ExtractResult:
    if not cfg.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    response = httpx.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {cfg.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": cfg.agent_model,
            "messages": _messages(transcript),
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return ExtractResult(entry=parse(content), model=cfg.agent_model, raw=content)


def _tinker_available(cfg: Config) -> bool:
    if not (cfg.tinker_api_key and cfg.tinker_model_path):
        return False
    try:
        import tinker  # noqa: F401
    except ImportError:
        return False
    return True


def _extract_tinker(transcript: str, cfg: Config) -> ExtractResult:
    """Sample from the fine-tuned adapter via the Tinker SDK."""
    import tinker
    from tinker import types

    async def run() -> tuple[str, str]:
        service = tinker.ServiceClient()
        sampling = await service.create_sampling_client_async(
            model_path=cfg.tinker_model_path
        )
        try:
            tokenizer = sampling.get_tokenizer()
        except AttributeError as exc:  # pragma: no cover - SDK version drift
            raise RuntimeError(
                "this tinker SDK has no SamplingClient.get_tokenizer(); "
                "pin tinker>=0.4 or use the openrouter backend"
            ) from exc
        prompt_tokens = tokenizer.apply_chat_template(
            conversation=_messages(transcript),
            add_generation_prompt=True,
            return_dict=False,
        )
        model_input = types.ModelInput.from_ints(prompt_tokens)
        params = types.SamplingParams(max_tokens=512, temperature=0.2)
        result = await sampling.sample_async(
            prompt=model_input, num_samples=1, sampling_params=params
        )
        return tokenizer.decode(result.sequences[0].tokens)

    raw = asyncio.run(run())
    return ExtractResult(entry=parse(raw), model=f"tinker:{cfg.tinker_model_path}", raw=raw)


def extract(transcript: str, cfg: Config, backend: str = "auto") -> ExtractResult:
    """Extract a FieldEntry from a transcript.

    backend: "auto" | "tinker" | "openrouter".
    """
    if backend == "tinker":
        return _extract_tinker(transcript, cfg)
    if backend == "openrouter":
        return _extract_openrouter(transcript, cfg)
    if backend == "auto":
        if _tinker_available(cfg):
            try:
                return _extract_tinker(transcript, cfg)
            except Exception:  # noqa: BLE001 - fall back rather than fail the walk
                pass
        return _extract_openrouter(transcript, cfg)
    raise ValueError(f"unknown backend: {backend!r}")
