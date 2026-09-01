"""Skills — deep, reusable how-to knowledge NYX loads at its disposal.

A skill is a markdown file: a playbook, doctrine, or curriculum. Files can be
book-length: ``sync_skills`` splits each on its ``##`` section headings and
stores **one long-term lesson per section** (title-tagged), so depth survives
ingestion and recall surfaces exactly the relevant section — the same memory
machinery that injects lessons into working agents, no extra plumbing.

Two locations are synced by default: the repo's shipped ``skills/`` packs and
the operator's own ``.nyx/skills/``. Re-sync is idempotent (reinforces).
"""
from __future__ import annotations

import re
from pathlib import Path

_H1 = re.compile(r"^#\s+(.*)", re.MULTILINE)
_SECTION_SPLIT = re.compile(r"^##\s+", re.MULTILINE)

# Packaged packs ship with the wheel; the cwd dirs are the operator's own.
PACKAGED_DIR = Path(__file__).resolve().parent / "skill_packs"
CWD_DIRS = ("skills", ".nyx/skills")


def default_dirs() -> list[Path]:
    return [PACKAGED_DIR] + [Path(d) for d in CWD_DIRS]


def _tags_for(*texts: str) -> list[str]:
    tags: list[str] = ["skill"]
    for t in texts:
        tags += re.findall(r"[a-z0-9]{3,}", t.lower())
    seen: set[str] = set()
    return [t for t in tags if not (t in seen or seen.add(t))][:12]


def _ingest_file(memory, path: Path, max_chars: int) -> int:
    body = path.read_text(encoding="utf-8").strip()
    if not body:
        return 0
    doc_title = (_H1.search(body).group(1).strip() if _H1.search(body)
                 else path.stem.replace("-", " ").replace("_", " "))

    sections = _SECTION_SPLIT.split(body)
    count = 0
    # sections[0] is the preamble under the H1; the rest each begin with a title line.
    chunks: list[tuple[str, str]] = []
    if sections[0].strip():
        chunks.append((doc_title, sections[0].strip()))
    for sec in sections[1:]:
        title, _, rest = sec.partition("\n")
        if rest.strip():
            chunks.append((f"{doc_title} — {title.strip()}", rest.strip()))

    for title, text in chunks:
        lesson = memory.remember(
            f"SKILL — {title}: {text[:max_chars]}",
            kind="skill", tags=_tags_for(path.stem, title), source=str(path), weight=2.0,
        )
        lesson.tier = "long_term"
        count += 1
    return count


def sync_skills(memory, skills_dir: str | Path | None = None, max_chars: int = 4000) -> int:
    """Ingest markdown skills (per-section) into long-term memory. Returns count."""
    dirs = [Path(skills_dir)] if skills_dir else default_dirs()
    n = 0
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            n += _ingest_file(memory, path, max_chars)
    memory._flush()
    return n
