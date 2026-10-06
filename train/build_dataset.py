#!/usr/bin/env python3
"""Build the fine-tuning dataset: messy walk transcripts → FieldEntry JSON.

The point of fine-tuning is that a small open-weight model should match a
much larger model on *this* narrow job. So the dataset is deliberately
narrow and deliberately messy:

  * narrow  -- one task, one output schema, one voice.
  * messy   -- the inputs are what ASR actually produces: lowercase, no
               punctuation, filler words, restarts, dropped words.

Scenarios are composed from parts and then corrupted by a deterministic
noise pass, which is enough to give hundreds of distinct, realistic
examples without hand-writing each one. Real recordings from actual walks
can be appended later: drop lines into ``train/data/real.jsonl`` and they
join the eval split.

    python train/build_dataset.py --n 500
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "_lib"))

from greenhour.schema import FieldEntry  # noqa: E402

FILLERS = ["um", "uh", "like", "you know", "so", "yeah", "okay so", "i mean"]
HEDGES = ["i think", "maybe", "pretty sure", "not sure but", "looks like"]


# --------------------------------------------------------------------------
# Scenario parts
# --------------------------------------------------------------------------

OUTDOOR_PLACES = [
    ("the river loop", "the river loop"),
    ("the park down the road", "the local park"),
    ("the ridge track", "the ridge"),
    ("the beach path", "the beach"),
    ("my back garden", "the garden"),
    ("the canal towpath", "the canal"),
    ("the cemetery walk", "the old cemetery"),
    ("the harbour foreshore", "the harbour"),
]

WEATHERS = [
    "overcast and cool",
    "clear and warm",
    "grey, spitting rain",
    "windy",
    "foggy at first",
    "bright but cold",
    None,
]

MOODS = ["calm", "cheerful", "tired but glad", "restless", "quiet", "wide awake", None]

SPECIES = [
    "magpie", "kookaburra", "cockatoo", "willy wagtail", "galah", "raven",
    "robin", "sparrow", "duck", "heron", "kingfisher", "wren", "currawong",
    "blackbird", "swallow", "ibis", "cormorant", "pelican",
]

NOTABLE = [
    "first jacaranda blooms", "the tide was all the way out", "a fox crossed the path",
    "fresh cut grass smell", "someone had planted new seedlings",
    "the creek was running after last night's rain", "a dog off its lead",
    "frost on the grass", "the light through the trees", "a full moon still up",
    "wildflowers along the fence", "the bridge was closed for repairs",
]

ACTIVITIES = [
    "walking", "running", "cycling slow", "just standing", "stretching",
    "walking the dog", "on the way to the shops", "taking the long way home",
]

OPENERS = [
    "just out on", "i'm on", "walking", "quick one around", "halfway around",
    "coming back along", "took the long way around", "sitting at",
]

CLOSERS = [
    "that's it", "anyway back soon", "feels good", "should do this more",
    "okay logging off", "talk later", "", "", "",
]

INDOOR_PLACES = [
    "at my desk", "in the kitchen", "on the couch", "in the car",
    "in the office", "in bed", "in the shed",
]

INDOOR_ACTIVITIES = [
    "working", "making coffee", "waiting for the kettle", "on a call",
    "reading", "doing emails", "eating lunch",
]


def _sentence(parts: list[str]) -> str:
    return " ".join(p for p in parts if p).strip()


def make_outdoor(rng: random.Random) -> tuple[str, FieldEntry]:
    spoken, label = rng.choice(OUTDOOR_PLACES)
    activity = rng.choice(ACTIVITIES)
    n_species = rng.randint(0, 3)
    species = rng.sample(SPECIES, n_species)
    n_notable = rng.randint(0, 2)
    notable = rng.sample(NOTABLE, n_notable)
    weather = rng.choice(WEATHERS)
    mood = rng.choice(MOODS)
    opener = rng.choice(OPENERS)
    closer = rng.choice(CLOSERS)

    heard = ""
    if species:
        heard = "heard " + " and ".join(species)

    saw = ""
    if notable:
        saw = "and " + notable[0]

    spoken_text = _sentence([opener, spoken, activity, heard, saw, closer])

    summary_bits = [f"{activity.capitalize()} {label}"]
    if species:
        summary_bits.append("with " + ", ".join(species) + " about")
    if notable:
        summary_bits.append(f"noticed {notable[0]}")
    summary = ", ".join(summary_bits) + "."

    entry = FieldEntry(
        outdoors=True,
        summary=summary,
        location=label,
        weather=weather,
        mood=mood,
        notable=notable,
        species=species,
    )
    return spoken_text, entry


def make_indoor(rng: random.Random) -> tuple[str, FieldEntry]:
    place = rng.choice(INDOOR_PLACES)
    activity = rng.choice(INDOOR_ACTIVITIES)
    mood = rng.choice(MOODS)
    opener = rng.choice(["still", "just", "back now and", "okay so"])
    spoken_text = _sentence([opener, place, activity, rng.choice(CLOSERS)])
    summary = f"Still indoors — {activity} {place}."
    entry = FieldEntry(
        outdoors=False,
        summary=summary,
        location=place,
        weather=None,
        mood=mood,
        notable=[],
        species=[],
    )
    return spoken_text, entry


# --------------------------------------------------------------------------
# ASR-style corruption
# --------------------------------------------------------------------------

def noisify(text: str, rng: random.Random) -> str:
    words = text.lower().replace(",", " ").replace(".", " ").split()
    out: list[str] = []
    for word in words:
        if rng.random() < 0.06:
            out.append(rng.choice(FILLERS))
        if rng.random() < 0.03 and out:
            out.append(out[-1])  # ASR stutter/doubling
        if rng.random() < 0.04:
            continue  # dropped word
        out.append(word)
    if rng.random() < 0.15:
        out.insert(0, rng.choice(FILLERS))
    if rng.random() < 0.10:
        out.append(rng.choice(HEDGES))
    noisy = " ".join(out)
    return noisy[:1].upper() + noisy[1:] if noisy and rng.random() < 0.2 else noisy


def build(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    records: list[dict] = []
    seen: set[str] = set()
    attempts = 0
    while len(records) < n and attempts < n * 40:
        attempts += 1
        outdoor = rng.random() < 0.78  # the real world skews outdoor
        spoken, entry = make_outdoor(rng) if outdoor else make_indoor(rng)
        transcript = noisify(spoken, rng)
        if not transcript or transcript in seen:
            continue
        seen.add(transcript)
        records.append({"transcript": transcript, "entry": entry.to_dict()})
    return records


def write_jsonl(path: pathlib.Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_real(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Green Hour dataset.")
    parser.add_argument("--n", type=int, default=500, help="total examples")
    parser.add_argument("--eval-fraction", type=float, default=0.12)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "train" / "data")
    args = parser.parse_args()

    records = build(args.n, args.seed)
    real = load_real(args.out / "real.jsonl")
    records.extend(real)

    rng = random.Random(args.seed + 1)
    rng.shuffle(records)
    n_eval = max(1, int(len(records) * args.eval_fraction))
    eval_records = records[:n_eval]
    train_records = records[n_eval:]

    write_jsonl(args.out / "train.jsonl", train_records)
    write_jsonl(args.out / "eval.jsonl", eval_records)

    outdoor_share = sum(1 for r in records if r["entry"]["outdoors"]) / len(records)
    print(f"wrote {len(train_records)} train / {len(eval_records)} eval to {args.out}")
    print(f"{outdoor_share:.0%} outdoor, {1 - outdoor_share:.0%} indoor "
          f"({len(real)} hand-written examples folded in)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
