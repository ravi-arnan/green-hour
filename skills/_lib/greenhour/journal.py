"""The journal: a small SQLite store on the persistent disk.

Holds one row per logged walk, plus the derived streak and weekly stats
that the agent reports back and the public page renders. SQLite keeps the
whole thing on the Render disk with no extra service to run or pay for.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .schema import FieldEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    local_date  TEXT NOT NULL,
    outdoors    INTEGER NOT NULL,
    summary     TEXT NOT NULL,
    location    TEXT,
    weather     TEXT,
    mood        TEXT,
    notable     TEXT NOT NULL DEFAULT '[]',
    species     TEXT NOT NULL DEFAULT '[]',
    transcript  TEXT,
    source      TEXT NOT NULL DEFAULT 'voice',
    model       TEXT
);
CREATE INDEX IF NOT EXISTS idx_entries_local_date ON entries(local_date);
"""


def _now(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def add_entry(
    conn: sqlite3.Connection,
    entry: FieldEntry,
    *,
    tz: str = "UTC",
    transcript: str | None = None,
    source: str = "voice",
    model: str | None = None,
    when: datetime | None = None,
) -> int:
    moment = when or _now(tz)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(ZoneInfo(tz))
    cur = conn.execute(
        """
        INSERT INTO entries
            (created_at, local_date, outdoors, summary, location, weather, mood,
             notable, species, transcript, source, model)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            local.astimezone(timezone.utc).isoformat(),
            local.date().isoformat(),
            1 if entry.outdoors else 0,
            entry.summary,
            entry.location,
            entry.weather,
            entry.mood,
            json.dumps(entry.notable, ensure_ascii=False),
            json.dumps(entry.species, ensure_ascii=False),
            transcript,
            source,
            model,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["outdoors"] = bool(d["outdoors"])
    d["notable"] = json.loads(d["notable"] or "[]")
    d["species"] = json.loads(d["species"] or "[]")
    return d


def recent(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM entries ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def outdoor_dates(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT local_date FROM entries WHERE outdoors = 1"
    ).fetchall()
    return {r["local_date"] for r in rows}


def streak(conn: sqlite3.Connection, tz: str, today: date | None = None) -> int:
    """Consecutive days (ending today or yesterday) with at least one walk."""
    days = outdoor_dates(conn)
    if not days:
        return 0
    cursor = today or _now(tz).date()
    # A streak survives until the day is over: if today has no walk yet,
    # count from yesterday so an evening walker doesn't see it reset at midnight.
    if cursor.isoformat() not in days:
        cursor = cursor - timedelta(days=1)
    count = 0
    while cursor.isoformat() in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def _most_common(values: list[str], top: int = 5) -> list[dict]:
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"name": k, "count": c} for k, c in ordered[:top]]


def weekly_stats(
    conn: sqlite3.Connection, tz: str, *, days: int = 7, today: date | None = None
) -> dict:
    end = today or _now(tz).date()
    start = end - timedelta(days=days - 1)
    rows = conn.execute(
        "SELECT * FROM entries WHERE local_date >= ? ORDER BY id ASC",
        (start.isoformat(),),
    ).fetchall()
    entries = [_row_to_dict(r) for r in rows]
    outdoors = [e for e in entries if e["outdoors"]]
    species = [s for e in outdoors for s in e["species"]]
    notable = [n for e in outdoors for n in e["notable"]]
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days_out": len({e["local_date"] for e in outdoors}),
        "walks": len(outdoors),
        "species": _most_common(species),
        "notable": _most_common(notable),
    }


def export_public(conn: sqlite3.Connection, dest: Path, tz: str, *, limit: int = 30) -> dict:
    """Write the JSON the static streak page reads. Returns the payload."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": tz,
        "streak": streak(conn, tz),
        "week": weekly_stats(conn, tz),
        "totals": {
            "walks": len(recent(conn, limit=10**6)),
            "days_out": len(outdoor_dates(conn)),
        },
        "entries": [
            {
                "date": e["local_date"],
                "at": e["created_at"],
                "summary": e["summary"],
                "location": e["location"],
                "species": e["species"],
                "notable": e["notable"],
                "mood": e["mood"],
            }
            for e in recent(conn, limit=limit)
            if e["outdoors"]
        ],
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
