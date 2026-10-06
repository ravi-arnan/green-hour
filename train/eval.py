#!/usr/bin/env python3
"""Base versus tuned: does the fine-tune actually earn its keep?

Runs the held-out eval set through two backends and reports the numbers the
DEV post cites. Three axes matter:

  * quality    -- schema-valid rate, outdoors accuracy, species/notable F1
  * latency    -- wall-clock per example
  * cost model -- output tokens per example (a small tuned model emits short
                  JSON; a big prompted model pads and re-explains)

    uv run --with-requirements train/requirements.txt train/eval.py
    ... train/eval.py --base tinker-base   # apples-to-apples, both on Tinker

Writes train/data/eval_results.json and prints a markdown table.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "_lib"))

from greenhour import models  # noqa: E402
from greenhour import config as ghconfig  # noqa: E402
from greenhour.schema import FieldEntry, parse  # noqa: E402


def load_records(path: pathlib.Path, limit: int = 0) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
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
    precision = tp / len(pred)
    recall = tp / len(exp)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def run_backend(name: str, records: list[dict], cfg, backend: str) -> dict:
    valid = 0
    outdoor_correct = 0
    outdoor_total = 0
    species_scores: list[float] = []
    notable_scores: list[float] = []
    latencies: list[float] = []
    output_tokens: list[int] = []
    failures: list[dict] = []

    for record in records:
        expected = FieldEntry.from_dict(record["entry"])
        start = time.perf_counter()
        try:
            result = models.extract(record["transcript"], cfg, backend=backend)
            entry = result.entry
            raw = result.raw
            valid += 1
        except Exception as exc:  # noqa: BLE001
            latencies.append((time.perf_counter() - start) * 1000)
            failures.append({"transcript": record["transcript"], "error": str(exc)})
            continue
        latencies.append((time.perf_counter() - start) * 1000)
        output_tokens.append(len(raw.split()))

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
    parser.add_argument("--data", type=pathlib.Path, default=ROOT / "train" / "data" / "eval.jsonl")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--base", choices=["openrouter", "tinker-base"], default="openrouter")
    parser.add_argument("--tuned", choices=["tinker"], default="tinker")
    parser.add_argument("--json-out", type=pathlib.Path, default=ROOT / "train" / "data" / "eval_results.json")
    args = parser.parse_args()

    cfg = ghconfig.load()
    records = load_records(args.data, args.limit)

    results = []
    base_backend = "openrouter" if args.base == "openrouter" else "tinker"
    base_cfg = cfg
    if args.base == "tinker-base":
        base_cfg = dataclasses.replace(
            cfg, tinker_model_path=f"base:{cfg.tinker_base_model}"
        )
    results.append(run_backend(f"base ({args.base})", records, base_cfg, base_backend))
    results.append(run_backend("tuned (tinker)", records, cfg, args.tuned))

    table = markdown_table(results)
    print(table)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
