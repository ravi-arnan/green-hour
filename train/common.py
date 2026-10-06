"""Shared prompt, parsing and model I/O for the Green Hour fine-tune.

Deliberately self-contained: this directory has no dependency on the Worker
runtime, so the training pipeline can be run and reviewed on its own.

Keep SYSTEM_PROMPT and JSON_SCHEMA in sync with worker/src/extract.ts.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_BASE_MODEL = "qwen/qwen3-4b:free"

SYSTEM_PROMPT = (
    "You turn a short, messy spoken voice note from a walk into one structured "
    "field-journal entry. Transcription noise, filler words and half sentences "
    "are expected; infer politely and never invent specifics that were not said. "
    "Write the summary in a warm, plain naturalist's voice, first person, one or "
    "two sentences. Set outdoors=true only when the speaker is plainly outside "
    "(weather, birds, being on a trail, etc.); if they are indoors or it is "
    "ambiguous, set it false. Return JSON only."
)

JSON_SCHEMA = {
    "type": "object",
    "required": ["outdoors", "summary"],
    "properties": {
        "outdoors": {"type": "boolean"},
        "summary": {"type": "string"},
        "location": {"type": ["string", "null"]},
        "weather": {"type": ["string", "null"]},
        "mood": {"type": ["string", "null"]},
        "notable": {"type": "array", "items": {"type": "string"}},
        "species": {"type": "array", "items": {"type": "string"}},
    },
}

_THINK_RE = re.compile(r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>", re.I)
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


@dataclass
class FieldEntry:
    outdoors: bool
    summary: str
    location: str | None = None
    weather: str | None = None
    mood: str | None = None
    notable: list[str] = field(default_factory=list)
    species: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FieldEntry":
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        if "outdoors" not in data:
            raise ValueError("missing required field: outdoors")
        summary = str(data.get("summary") or "").strip()
        if not summary:
            raise ValueError("missing required field: summary")
        return cls(
            outdoors=_as_bool(data.get("outdoors")),
            summary=summary,
            location=_opt_str(data.get("location")),
            weather=_opt_str(data.get("weather")),
            mood=_opt_str(data.get("mood")),
            notable=_str_list(data.get("notable")),
            species=_str_list(data.get("species")),
        )


def _str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in re.split(r"[,\n;]", value) if p.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    return [s] if s else []


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "outdoors", "outside"}
    return bool(value)


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _top_level_objects(text: str) -> list[str]:
    """Every balanced {...} block, ignoring braces inside strings."""
    out: list[str] = []
    depth = 0
    start = -1
    in_string = escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                out.append(text[start : i + 1])
                start = -1
    return out


def parse(text: str) -> FieldEntry:
    """Parse a model response, tolerating reasoning blocks, fences and prose."""
    cleaned = _THINK_RE.sub("", text)
    cleaned = re.sub(r"^[\s\S]*?</think(?:ing)?>", "", cleaned, flags=re.I)
    fence = _FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1)

    candidates = _top_level_objects(cleaned)
    if not candidates:
        raise ValueError("no JSON object found in model output")
    last_error: Exception | None = None
    for candidate in reversed(candidates):
        try:
            return FieldEntry.from_dict(json.loads(candidate))
        except Exception as exc:  # noqa: BLE001 - try the next candidate
            last_error = exc
    raise ValueError(f"no usable field entry in model output: {last_error}")


def build_messages(transcript: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f'Voice note transcript:\n"""\n{transcript.strip()}\n"""\n\n'
                f"Return one JSON object matching this schema:\n{json.dumps(JSON_SCHEMA)}"
            ),
        },
    ]


# ------------------------------------------------------------------ backends

def extract_openrouter(transcript: str, api_key: str, model: str) -> tuple[str, FieldEntry]:
    """Baseline: sample from a hosted model. Returns (raw_text, entry)."""
    import httpx

    response = httpx.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": build_messages(transcript),
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"]
    return raw, parse(raw)


def extract_tinker(transcript: str, model_path: str) -> tuple[str, FieldEntry]:
    """Tuned: sample from the LoRA adapter saved by train_tinker.py."""
    import asyncio

    import tinker
    from tinker import types

    async def run() -> str:
        service = tinker.ServiceClient()
        sampling = await service.create_sampling_client_async(model_path=model_path)
        tokenizer = sampling.get_tokenizer()
        prompt_tokens = tokenizer.apply_chat_template(
            conversation=build_messages(transcript),
            add_generation_prompt=True,
            return_dict=False,
        )
        result = await sampling.sample_async(
            prompt=types.ModelInput.from_ints(prompt_tokens),
            num_samples=1,
            sampling_params=types.SamplingParams(max_tokens=400, temperature=0.2),
        )
        return tokenizer.decode(result.sequences[0].tokens)

    raw = asyncio.run(run())
    return raw, parse(raw)


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default
