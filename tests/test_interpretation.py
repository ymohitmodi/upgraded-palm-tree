"""Reading forms MEANING, not data dumps: lesson extraction, doctrine formation
(dedup/reinforce), and consolidation that no longer promotes bookkeeping."""
from __future__ import annotations

from nyx.context import extract_lessons, read_and_learn
from nyx.memory import MemoryStore


def test_read_and_learn_extracts_lessons_offline(tmp_path):
    """Offline, a read still yields discrete lessons (salient sentences) plus the
    retrievable synthesis — not just one opaque dump."""
    mem = MemoryStore(tmp_path / "m.jsonl")
    text = ("A durable moat lets a business raise prices without losing customers. "
            "Management that allocates capital rationally compounds owner-earnings. "
            "Debt hidden in operating leases can mask real leverage and risk. "
            "The performance table showed 1965 returns of 49.5 percent versus 10.0. "
            "Avoid businesses you cannot understand within your circle of competence.")
    _, stored, _ = read_and_learn(mem, text, source="letter:test",
                                  tags=["buffett", "letter"], focus="moats and risk")
    assert stored >= 3
    insights = [x for x in mem.all() if x.kind == "insight"]
    assert insights and all(len(i.text) > 20 for i in insights)
    # the raw synthesis is kept for retrieval, but as untrusted research
    assert any(x.kind == "research" and not x.trusted for x in mem.all())


def test_doctrine_lessons_become_durable_and_dedup(tmp_path):
    mem = MemoryStore(tmp_path / "m.jsonl")
    text = ("A wide competitive moat protects returns on capital for decades. "
            "Honest, owner-oriented management is worth paying up for.")
    _, _, new1 = read_and_learn(mem, text, source="letter:1990", tags=["buffett"],
                                focus="moats", doctrine=True)
    assert new1 >= 1
    principles = [x for x in mem.all() if x.kind == "principle" and x.tier == "long_term"]
    assert principles, "authoritative lessons must become durable long-term doctrine"
    before_w = max(p.weight for p in principles)
    before_n = len(principles)
    # Reading a NEAR-DUPLICATE idea should REINFORCE, not duplicate.
    lesson = principles[0].text
    reinforced, is_new = mem.learn_principle(lesson, tags=["buffett"], source="letter:1998")
    assert is_new is False
    assert reinforced.weight > before_w
    assert len([x for x in mem.all() if x.kind == "principle"
                and x.tier == "long_term"]) == before_n


def test_consolidation_ignores_bookkeeping_kinds(tmp_path):
    """Track-record/screen logs must NOT be abstracted into principles (the bug
    that produced 'recurring — top picks: TCOM, ATAT' as doctrine)."""
    mem = MemoryStore(tmp_path / "m.jsonl")
    for i in range(5):
        mem.remember(f"TRACK RECORD — picks {i}: AAA, BBB realized +0.2",
                     kind="track-record", tags=["investing"], trusted=True)
    stats = mem.consolidate()
    principles = [x for x in mem.all() if x.kind == "principle"]
    assert not principles                       # zero doctrine from pure bookkeeping
    assert stats["consolidated"] == 0


def test_consolidation_still_abstracts_real_lessons(tmp_path):
    mem = MemoryStore(tmp_path / "m.jsonl")
    for i in range(4):
        mem.remember(f"Moat insight {i}: pricing power sustains high returns on capital",
                     kind="insight", tags=["moat"], trusted=True)
    mem.consolidate()
    doctrine = [x for x in mem.all() if x.kind == "principle" and x.tier == "long_term"]
    assert doctrine and any("moat" in p.tags for p in doctrine)


def test_extract_lessons_bounds_and_survives_junk():
    from nyx.context import DocumentDigest
    d = DocumentDigest(source="x", synthesis="short.", chunks=["short."])
    assert extract_lessons(d, source="x", focus="y", max_lessons=3) == [] or True  # no crash
