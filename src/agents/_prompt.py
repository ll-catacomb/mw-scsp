"""Minimal loader for src/prompts/*.md files used by the agent layer.

Each prompt file has YAML frontmatter, then `# System` and `# User` sections.
Placeholders are written as `{{ name }}`. Missing placeholders are left as-is
(so misuse is visible in the prompt rather than failing silently).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_SYSTEM_RE = re.compile(r"^# System\s*\n(.*?)(?=^# User\s*\n|\Z)", re.MULTILINE | re.DOTALL)
_USER_RE = re.compile(r"^# User\s*\n(.*?)\Z", re.MULTILINE | re.DOTALL)


def load_prompt(name: str, **vars: Any) -> tuple[Path, str, str]:
    """Return (path, system, user) with `{{ var }}` substituted from kwargs."""
    path = PROMPTS_DIR / name
    text = path.read_text(encoding="utf-8")
    text = _FRONTMATTER_RE.sub("", text, count=1)

    sys_match = _SYSTEM_RE.search(text)
    usr_match = _USER_RE.search(text)
    if not sys_match or not usr_match:
        raise ValueError(f"Prompt {name!r} is missing # System or # User section")

    def _sub(s: str) -> str:
        return _VAR_RE.sub(lambda m: str(vars.get(m.group(1), m.group(0))), s)

    return path, _sub(sys_match.group(1).strip()), _sub(usr_match.group(1).strip())
