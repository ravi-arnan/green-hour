#!/opt/hermes/.venv/bin/python
"""Idempotent patcher for Hermes' config.yaml.

Adds, the first time it runs against a given config.yaml:

  1. mcp_servers.render -- the Render MCP server, authenticated from the
     RENDER_MCP_API_KEY env var. Hermes substitutes ${VAR} lazily at
     gateway startup, so the key can be rotated in Render's Environment
     tab without a rebuild.

  2. skills.external_dirs -- our three skill locations, in precedence
     order:
       /opt/render-tools/skills-local    (Green Hour's own skills)
       /opt/render-tools/skills-render   (render-on-hermes overlay)
       /opt/render-tools/skills-upstream (pinned render-oss/skills)
     Earlier entries win on name collisions. Keeping them out of
     /opt/data/skills avoids colliding with the upstream skills_sync flow.

INSERT-only by design: if a key already exists (even pointing somewhere
else), it is left alone. Re-running on every boot is safe, and edits made
from the dashboard are never clobbered.

Uses PyYAML, which ships with Hermes' venv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

GREENHOUR_SKILL_DIRS = (
    "/opt/render-tools/skills-local",
    "/opt/render-tools/skills-render",
    "/opt/render-tools/skills-upstream",
)
RENDER_MCP_URL = "https://mcp.render.com/mcp"
RENDER_MCP_AUTH = "Bearer ${RENDER_MCP_API_KEY}"


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[greenhour] cannot read {path}: {exc}", file=sys.stderr)
        return {}
    if not raw.strip():
        return {}
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(
            f"[greenhour] {path} is not valid YAML ({exc}); refusing to patch",
            file=sys.stderr,
        )
        sys.exit(0)
    return data if isinstance(data, dict) else {}


def ensure_render_mcp(config: dict) -> bool:
    """Insert mcp_servers.render if missing. Returns True if changed."""
    mcp_servers = config.get("mcp_servers")
    if mcp_servers is None:
        config["mcp_servers"] = {
            "render": {
                "url": RENDER_MCP_URL,
                "headers": {"Authorization": RENDER_MCP_AUTH},
            }
        }
        return True
    if not isinstance(mcp_servers, dict):
        print(
            "[greenhour] mcp_servers is not a mapping; skipping render entry",
            file=sys.stderr,
        )
        return False
    if "render" in mcp_servers:
        return False
    mcp_servers["render"] = {
        "url": RENDER_MCP_URL,
        "headers": {"Authorization": RENDER_MCP_AUTH},
    }
    return True


def ensure_external_skill_dirs(config: dict) -> list[str]:
    """Append our skill dirs to skills.external_dirs if missing."""
    skills = config.setdefault("skills", {})
    if not isinstance(skills, dict):
        print(
            "[greenhour] skills is not a mapping; skipping external_dirs",
            file=sys.stderr,
        )
        return []
    existing = skills.get("external_dirs")
    if existing is None:
        skills["external_dirs"] = list(GREENHOUR_SKILL_DIRS)
        return list(GREENHOUR_SKILL_DIRS)
    if not isinstance(existing, list):
        print(
            "[greenhour] skills.external_dirs is not a list; skipping",
            file=sys.stderr,
        )
        return []
    added: list[str] = []
    for path in GREENHOUR_SKILL_DIRS:
        if path not in existing:
            existing.append(path)
            added.append(path)
    return added


def save_config(path: Path, config: dict) -> None:
    text = yaml.safe_dump(
        config,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    tmp = path.with_suffix(path.suffix + ".greenhour.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch-config.py <path/to/config.yaml>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    config = load_config(path)
    changed_mcp = ensure_render_mcp(config)
    added_dirs = ensure_external_skill_dirs(config)
    if changed_mcp or added_dirs:
        save_config(path, config)
        parts = []
        if changed_mcp:
            parts.append("mcp_servers.render")
        for dir_path in added_dirs:
            parts.append(f"skills.external_dirs += {dir_path}")
        print(f"[greenhour] patched {path}: {', '.join(parts)}")
    else:
        print(f"[greenhour] {path} already patched; nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
