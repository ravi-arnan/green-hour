from __future__ import annotations

from greenhour.schema import FieldEntry

import build_dataset


def test_build_is_deterministic():
    assert build_dataset.build(40, seed=7) == build_dataset.build(40, seed=7)


def test_build_produces_requested_count():
    assert len(build_dataset.build(50, seed=7)) == 50


def test_every_record_is_a_valid_field_entry():
    for record in build_dataset.build(120, seed=3):
        entry = FieldEntry.from_dict(record["entry"])
        assert entry.summary
        assert isinstance(record["transcript"], str) and record["transcript"]


def test_dataset_is_mostly_outdoor_but_has_both():
    records = build_dataset.build(200, seed=11)
    outdoor = [r for r in records if r["entry"]["outdoors"]]
    assert 0.6 < len(outdoor) / len(records) < 0.95
    assert len(outdoor) < len(records)


def test_transcripts_are_not_clean_prose():
    # The whole point is that inputs look like ASR output, not typed text.
    records = build_dataset.build(60, seed=5)
    noisy = [r for r in records if r["transcript"].islower() or r["transcript"].count(",") == 0]
    assert len(noisy) / len(records) > 0.5


def test_write_jsonl_round_trips(tmp_path):
    records = build_dataset.build(10, seed=1)
    out = tmp_path / "train.jsonl"
    build_dataset.write_jsonl(out, records)
    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 10
    assert build_dataset.load_real(out) == records
