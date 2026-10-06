#!/opt/hermes/.venv/bin/python
"""Weekly summary, and the public streak snapshot.

    python report.py                 # text summary + JSON
    python report.py --json
    python report.py --export        # also write the public JSON locally
    python report.py --publish       # export, then push it to the repo

--publish needs GITHUB_TOKEN + GITHUB_REPO and updates web/data/journal.json,
which is what the Render static site serves.
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import sys
from datetime import datetime, timezone

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "_lib"))

from greenhour import journal  # noqa: E402
from greenhour import config as ghconfig  # noqa: E402

PUBLIC_PATH = "web/data/journal.json"


def _format(stats: dict, streak_days: int) -> str:
    lines = [f"🌿 Green Hour — {stats['start']} to {stats['end']}"]
    lines.append(f"Out {stats['days_out']} day(s), {stats['walks']} walk(s). Streak: {streak_days}.")
    if stats["species"]:
        top = ", ".join(f"{s['name']}×{s['count']}" for s in stats["species"])
        lines.append(f"Most heard: {top}.")
    if stats["notable"]:
        top = ", ".join(f"{n['name']}" for n in stats["notable"][:3])
        lines.append(f"Noticed: {top}.")
    if stats["walks"] == 0:
        lines.append("Nothing logged this week. The grass is still there.")
    return "\n".join(lines)


def _publish(payload: dict, cfg) -> str:
    cfg.require("github_token", "github_repo")
    url = f"https://api.github.com/repos/{cfg.github_repo}/contents/{PUBLIC_PATH}"
    headers = {
        "Authorization": f"Bearer {cfg.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = {
        "message": "chore: refresh public streak snapshot",
        "content": base64.b64encode(
            (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        ).decode("ascii"),
    }
    existing = httpx.get(url, headers=headers, timeout=30.0)
    if existing.status_code == 200:
        body["sha"] = existing.json()["sha"]
    elif existing.status_code not in (404,):
        existing.raise_for_status()
    response = httpx.put(url, headers=headers, json=body, timeout=30.0)
    response.raise_for_status()
    return response.json()["commit"]["html_url"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly Green Hour summary.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--export", action="store_true", help="write the public JSON locally")
    parser.add_argument("--publish", action="store_true", help="push the snapshot to GitHub")
    args = parser.parse_args()

    cfg = ghconfig.load()
    conn = journal.connect(cfg.db_path)
    stats = journal.weekly_stats(conn, cfg.tz, days=args.days)
    streak_days = journal.streak(conn, cfg.tz)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "week": stats,
        "streak": streak_days,
    }

    if args.export or args.publish:
        snapshot = journal.export_public(conn, cfg.public_path, cfg.tz)
        payload["snapshot_path"] = str(cfg.public_path)
        if args.publish:
            try:
                payload["published"] = _publish(snapshot, cfg)
            except Exception as exc:  # noqa: BLE001
                print(f"error: publish failed: {exc}", file=sys.stderr)
                return 1

    if not args.json:
        print(_format(stats, streak_days))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
