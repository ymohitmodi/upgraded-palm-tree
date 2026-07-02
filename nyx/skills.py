"""Skills — reusable how-to knowledge NYX loads at its disposal.

A skill is a markdown file (``.nyx/skills/*.md``): a playbook, checklist, or
procedure. ``sync_skills`` ingests each file into **long-term memory** as a
``skill`` lesson (title + tags from the filename and headings), so the existing
recall machinery injects the relevant skill into whichever agent is working a
related task — same mechanism as lessons and doctrine, no extra plumbing.

Drop in new .md files any time; re-sync is idempotent (reinforces, not dupes).
"""
from __future__ import annotations

import re
from pathlib import Path

_HEADING = re.compile(r"^#{1,3}\s+(.*)", re.MULTILINE)


def sync_skills(memory, skills_dir: str | Path = ".nyx/skills", max_chars: int = 1500) -> int:
    """Load every markdown skill file into long-term memory. Returns count."""
    directory = Path(skills_dir)
    if not directory.exists():
        return 0
    n = 0
    for path in sorted(directory.glob("*.md")):
        body = path.read_text(encoding="utf-8").strip()
        if not body:
            continue
        title = (_HEADING.search(body).group(1) if _HEADING.search(body)
                 else path.stem.replace("-", " ").replace("_", " "))
        tags = ["skill"] + re.findall(r"[a-z0-9]+", path.stem.lower())
        lesson = memory.remember(
            f"SKILL — {title}: {body[:max_chars]}",
            kind="skill", tags=tags, source=str(path), weight=2.0,
        )
        lesson.tier = "long_term"
        n += 1
    memory._flush()
    return n
