#!/opt/hermes/.venv/bin/python
"""Turn a walk's voice note (or a plain transcript) into a journal entry.

    python log_walk.py --audio /path/to/voice.ogg
    python log_walk.py --transcript "misty loop around the park, heard a kookaburra"
    echo "text" | python log_walk.py --transcript -

Transcribes if needed, extracts a FieldEntry with the tuned model (falling
back to the baseline), stores it, and prints the result plus the streak.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "_lib"))

from greenhour import asr, journal  # noqa: E402
from greenhour import config as ghconfig  # noqa: E402
from greenhour import models  # noqa: E402


def _read_transcript(args: argparse.Namespace) -> str:
    if args.transcript == "-":
        return sys.stdin.read().strip()
    if args.transcript is not None:
        return args.transcript.strip()
    if args.transcript_file is not None:
        return pathlib.Path(args.transcript_file).read_text(encoding="utf-8").strip()
    raise SystemExit("error: pass --audio, --transcript, or --transcript-file")


def _header(entry) -> str:
    bits = [entry.summary]
    if entry.species:
        bits.append("· " + ", ".join(entry.species))
    return " ".join(bits)


def main() -> int:
    parser = argparse.ArgumentParser(description="Log a walk into the journal.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--audio", help="path to a voice note to transcribe")
    source.add_argument("--transcript", help="already-transcribed text, or - for stdin")
    source.add_argument("--transcript-file", help="path to a transcript file")
    parser.add_argument(
        "--backend",
        choices=["auto", "tinker", "openrouter"],
        default="auto",
        help="which model to use (default: tuned model, falling back to baseline)",
    )
    parser.add_argument("--force", action="store_true", help="store even if indoors")
    parser.add_argument("--dry-run", action="store_true", help="do not write to the journal")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()

    cfg = ghconfig.load()

    if args.audio:
        path = pathlib.Path(args.audio)
        if not path.exists():
            print(f"error: no such audio file: {path}", file=sys.stderr)
            return 2
        try:
            transcript = asr.transcribe_file(path, cfg)
        except Exception as exc:  # noqa: BLE001
            print(f"error: transcription failed: {exc}", file=sys.stderr)
            return 1
        origin = "voice"
    else:
        transcript = _read_transcript(args)
        origin = "text"

    if not transcript:
        print("error: empty transcript; nothing to log", file=sys.stderr)
        return 2

    try:
        result = models.extract(transcript, cfg, backend=args.backend)
    except Exception as exc:  # noqa: BLE001
        print(f"error: extraction failed: {exc}", file=sys.stderr)
        return 1

    entry = result.entry
    conn = journal.connect(cfg.db_path)
    entry_id = None
    stored = entry.outdoors or args.force
    if stored and not args.dry_run:
        entry_id = journal.add_entry(
            conn,
            entry,
            tz=cfg.tz,
            transcript=transcript,
            source=origin,
            model=result.model,
        )
    days = journal.streak(conn, cfg.tz)

    if entry.outdoors:
        line = f'Logged walk — "{_header(entry)}". Streak: {days} day(s). 🌿'
    elif args.force:
        line = f'Logged (forced) — "{_header(entry)}".'
    else:
        line = (
            "That one sounded indoors, so it is not counting toward your streak. "
            f'(I heard: "{_header(entry)}")'
        )

    payload = {
        "ok": True,
        "stored": bool(stored and not args.dry_run),
        "entry_id": entry_id,
        "outdoors": entry.outdoors,
        "streak": days,
        "model": result.model,
        "entry": entry.to_dict(),
        "transcript": transcript,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }

    if not args.json:
        print(line)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
