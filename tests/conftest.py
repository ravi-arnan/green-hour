"""Test bootstrap: make the skill library and the trainer importable."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for path in (ROOT / "skills" / "_lib", ROOT / "train"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
