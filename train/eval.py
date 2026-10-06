#!/usr/bin/env python3
"""Base versus tuned: does the fine-tune actually earn its keep?

Runs the held-out eval set through two backends and reports the numbers the
DEV post cites. Three axes matter:

  * quality    -- schema-valid rate, outdoors accuracy, species/notable F1
  * latency    -- wall-clock per example
  * cost model -- output tokens per example (a small tuned model emits short
                  JSON; a big prompted model pads and re-explains)

    uv run --no-project --python 3.12 --with-requirements train/requirements.txt \\
        train/eval.py

Writes train/data/eval_results.json and prints a markdown table.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DEFAULT_BASE_MODEL,
    FieldEntry,
    env,
    extract_openrouter,
    extract_tinker,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_records(path: pathlib.Path, limit: int = 0) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    if limit:
        records = records[:limit]
    if not records:
        raise SystemExit(f"no eval records in {path}; run build_dataset.py first")
    return records


def f1(predicted: list[str], expected: list[str]) -> float:
    pred = {p.lower() for p in predicted}
    exp = {e.lower() for e in expected}
    if not pred and not exp:
        return 1.0
    if not pred or not exp:
        return 0.0
    tp = len(pred & exp)
    precision, recall = tp / len(pred), tp / len(exp)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def run_backend(name: str, records: list[dict], predict) -> dict:
    """predict: transcript -> (raw_text, FieldEntry); raises on failure."""
    valid = outdoor_correct = outdoor_total = 0
    species_scores: list[float] = []
    notable_scores: list[float] = []
    latencies: list[float] = []
    output_tokens: list[int] = []
    failures: list[dict] = []

    for record in records:
        expected = FieldEntry.from_dict(record["entry"])
        start = time.perf_counter()
        try:
            raw, entry = predict(record["transcript"])
        except Exception as exc:  # noqa: BLE001
            latencies.append((time.perf_counter() - start) * 1000)
            failures.append({"transcript": record["transcript"], "error": str(exc)})
            continue

        latencies.append((time.perf_counter() - start) * 1000)
        output_tokens.append(len(raw.split()))
        valid += 1
        outdoor_total += 1
        if entry.outdoors == expected.outdoors:
            outdoor_correct += 1
        if expected.outdoors:
            species_scores.append(f1(entry.species, expected.species))
            notable_scores.append(f1(entry.notable, expected.notable))

    n = len(records)
    return {
        "backend": name,
        "examples": n,
        "schema_valid_rate": valid / n,
        "outdoors_accuracy": (outdoor_correct / outdoor_total) if outdoor_total else 0.0,
        "species_f1": statistics.fmean(species_scores) if species_scores else 0.0,
        "notable_f1": statistics.fmean(notable_scores) if notable_scores else 0.0,
        "latency_ms_mean": statistics.fmean(latencies) if latencies else 0.0,
        "output_tokens_mean": statistics.fmean(output_tokens) if output_tokens else 0.0,
        "failures": failures[:10],
    }


def markdown_table(results: list[dict]) -> str:
    header = (
        "| backend | schema-valid | outdoors acc | species F1 | notable F1 | "
        "latency (ms) | out tokens |\n"
        "|---|---|---|---|---|---|---|"
    )
    rows = [
        "| {backend} | {schema_valid_rate:.0%} | {outdoors_accuracy:.0%} | "
        "{species_f1:.2f} | {notable_f1:.2f} | {latency_ms_mean:.0f} | "
        "{output_tokens_mean:.0f} |".format(**r)
        for r in results
    ]
    return "\n".join([header, *rows])


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Green Hour extractors.")
    parser.add_argument(
        "--data", type=pathlib.Path, default=ROOT / "train" / "data" / "eval.jsonl"
    )
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--json-out", type=pathlib.Path, default=ROOT / "train" / "data" / "eval_results.json")
    args = parser.parse_args()

    api_key = env("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required for the baseline")
    model_path = env("TINKER_MODEL_PATH")
    if not model_path:
        raise SystemExit("TINKER_MODEL_PATH is required (printed by train_tinker.py)")
    base_model = env("GREENHOUR_BASE_MODEL", DEFAULT_BASE_MODEL)

    records = load_records(args.data, args.limit)
    results = [
        run_backend(
            f"base ({base_model})",
            records,
            lambda t: extract_openrouter(t, api_key, base_model),
        ),
        run_backend("tuned (tinker)", records, lambda t: extract_tinker(t, model_path)),
    ]

    print(markdown_table(results))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
