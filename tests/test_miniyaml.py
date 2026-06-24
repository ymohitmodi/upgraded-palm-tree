from __future__ import annotations

from nyx import _miniyaml


def test_parses_nested_mappings_and_lists():
    text = """
meta:
  name: NYX
  version: 1.0.0
  amendable: true
core:
  - id: C1
    title: Sovereign
    immutable: true
    rule: |
      first line
      second line
  - id: C2
    title: No harm
forbidden:
  - do not lie
  - do not delete
"""
    data = _miniyaml.loads(text)
    assert data["meta"]["name"] == "NYX"
    assert data["meta"]["amendable"] is True
    assert data["core"][0]["id"] == "C1"
    assert data["core"][0]["immutable"] is True
    assert data["core"][0]["rule"] == "first line\nsecond line"
    assert data["core"][1]["title"] == "No harm"
    assert data["forbidden"] == ["do not lie", "do not delete"]


def test_flow_list_and_scalars():
    text = """
gates:
  - id: G1
    requires: [E1, C1]
    n: 3
    ratio: 0.5
"""
    data = _miniyaml.loads(text)
    g = data["gates"][0]
    assert g["requires"] == ["E1", "C1"]
    assert g["n"] == 3
    assert g["ratio"] == 0.5


def test_matches_pyyaml_when_available():
    text = "a:\n  b: 1\n  c: [x, y]\n"
    parsed = _miniyaml.loads(text)
    assert parsed == {"a": {"b": 1, "c": ["x", "y"]}}
