"""The structured field entry — the contract between the model and the journal.

A walk's voice note becomes one of these. Keeping the shape in one place
lets the prompt, the validator, and the Tinker training data stay in sync.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

# Embedded in the extraction prompt. Keep in sync with `from_dict`.
JSON_SCHEMA = {
    "type": "object",
    "required": ["outdoors", "summary"],
    "properties": {
        "outdoors": {
            "type": "boolean",
            "description": "True only if the speaker is clearly outside during this walk.",
        },
        "summary": {
            "type": "string",
            "description": "One or two sentences, naturalist voice, about the walk.",
        },
        "location": {"type": ["string", "null"]},
        "weather": {"type": ["string", "null"]},
        "mood": {"type": ["string", "null"]},
        "notable": {"type": "array", "items": {"type": "string"}},
        "species": {"type": "array", "items": {"type": "string"}},
    },
}

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # Models sometimes emit "a, b, c" instead of a list.
        parts = [p.strip() for p in re.split(r"[,\n;]", value)]
        return [p for p in parts if p]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return [str(value).strip()] if str(value).strip() else []


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "outdoors", "outside"}
    return bool(value)


def _as_opt_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


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
            raise ValueError(f"expected an object, got {type(data).__name__}")
        if "outdoors" not in data:
            raise ValueError("missing required field: outdoors")
        summary = _as_opt_str(data.get("summary"))
        if not summary:
            raise ValueError("missing required field: summary")
        return cls(
            outdoors=_as_bool(data.get("outdoors")),
            summary=summary,
            location=_as_opt_str(data.get("location")),
            weather=_as_opt_str(data.get("weather")),
            mood=_as_opt_str(data.get("mood")),
            notable=_as_str_list(data.get("notable")),
            species=_as_str_list(data.get("species")),
        )


def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _first_object(text: str) -> str | None:
    """Return the first balanced {...} block, ignoring braces inside strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
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
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse(text: str) -> FieldEntry:
    """Parse a model response into a FieldEntry.

    Tolerates code fences and leading prose; raises ValueError if no valid
    object can be recovered.
    """
    candidate = _strip_fences(text)
    block = _first_object(candidate)
    if block is None:
        raise ValueError("no JSON object found in model output")
    try:
        data = json.loads(block)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    return FieldEntry.from_dict(data)
