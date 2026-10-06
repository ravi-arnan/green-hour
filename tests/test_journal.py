from __future__ import annotations

from datetime import date, datetime, timezone

from greenhour import journal
from greenhour.schema import FieldEntry

TZ = "UTC"


def _entry(outdoors: bool, summary: str = "Walk", **kwargs) -> FieldEntry:
    return FieldEntry(outdoors=outdoors, summary=summary, **kwargs)


def _conn(tmp_path):
    return journal.connect(tmp_path / "nested" / "journal.db")


def test_connect_creates_parent_dirs(tmp_path):
    conn = _conn(tmp_path)
    assert (tmp_path / "nested" / "journal.db").exists()
    assert journal.recent(conn) == []


def test_add_entry_and_recent(tmp_path):
    conn = _conn(tmp_path)
    when = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)
    entry_id = journal.add_entry(
        conn, _entry(True, "River loop.", species=["magpie"]), tz=TZ, when=when
    )
    assert entry_id == 1
    rows = journal.recent(conn)
    assert len(rows) == 1
    assert rows[0]["outdoors"] is True
    assert rows[0]["species"] == ["magpie"]
    assert rows[0]["local_date"] == "2026-10-06"


def test_streak_counts_consecutive_days(tmp_path):
    conn = _conn(tmp_path)
    for day in (4, 5, 6):
        journal.add_entry(
            conn,
            _entry(True),
            tz=TZ,
            when=datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc),
        )
    assert journal.streak(conn, TZ, today=date(2026, 10, 6)) == 3


def test_indoor_entries_do_not_count(tmp_path):
    conn = _conn(tmp_path)
    when = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
    journal.add_entry(conn, _entry(False, "At my desk."), tz=TZ, when=when)
    assert journal.streak(conn, TZ, today=date(2026, 10, 6)) == 0
    # ...but it is still stored, for honesty.
    assert len(journal.recent(conn)) == 1


def test_streak_survives_a_quiet_morning(tmp_path):
    conn = _conn(tmp_path)
    for day in (4, 5):
        journal.add_entry(
            conn,
            _entry(True),
            tz=TZ,
            when=datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc),
        )
    # No walk yet today: the streak should still read 2, not 0.
    assert journal.streak(conn, TZ, today=date(2026, 10, 6)) == 2


def test_streak_breaks_on_a_gap(tmp_path):
    conn = _conn(tmp_path)
    for day in (2, 3, 6):
        journal.add_entry(
            conn,
            _entry(True),
            tz=TZ,
            when=datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc),
        )
    assert journal.streak(conn, TZ, today=date(2026, 10, 6)) == 1


def test_weekly_stats_aggregate(tmp_path):
    conn = _conn(tmp_path)
    journal.add_entry(
        conn,
        _entry(True, species=["magpie", "wren"], notable=["frost"]),
        tz=TZ,
        when=datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc),
    )
    journal.add_entry(
        conn,
        _entry(True, species=["magpie"]),
        tz=TZ,
        when=datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc),
    )
    journal.add_entry(
        conn,
        _entry(False),
        tz=TZ,
        when=datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc),
    )
    stats = journal.weekly_stats(conn, TZ, days=7, today=date(2026, 10, 6))
    assert stats["walks"] == 2
    assert stats["days_out"] == 2
    assert stats["species"][0] == {"name": "magpie", "count": 2}
    assert stats["notable"] == [{"name": "frost", "count": 1}]


def test_export_public_writes_outdoor_entries_only(tmp_path):
    conn = _conn(tmp_path)
    journal.add_entry(
        conn,
        _entry(True, "Out and about.", location="the park"),
        tz=TZ,
        when=datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc),
    )
    journal.add_entry(
        conn,
        _entry(False, "Indoors."),
        tz=TZ,
        when=datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc),
    )
    dest = tmp_path / "public" / "journal.json"
    payload = journal.export_public(conn, dest, TZ)
    assert dest.exists()
    assert payload["streak"] == 1
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["summary"] == "Out and about."
    assert payload["totals"]["days_out"] == 1
