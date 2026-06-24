# The NYX Constitution

This directory holds the **DNA** of the dark factory:
[`constitution.yaml`](constitution.yaml).

## How it works

- The constitution is loaded at factory boot by [`nyx/constitution.py`](../nyx/constitution.py).
- Every agent receives the relevant principles **injected into its system
  prompt** on every model call (so the model is steered by them) *and* its
  output is **checked against the gates and forbidden list** before the artifact
  is allowed to flow downstream (so the rules are enforced, not just suggested).
- This is the Constitutional AI idea — *harmlessness and quality from a written
  set of principles* — applied to an autonomous engineering org.

## Structure

| Section | Purpose |
| --- | --- |
| `core` | Immutable spine. Cannot be removed or weakened, only strengthened. |
| `engineering` | Best-practice doctrine drawn from elite software orgs. |
| `conduct` | How agents behave toward each other and untrusted input. |
| `gates` | Enforced checkpoints mapped to pipeline stages. |
| `forbidden` | Hard blocks regardless of any instruction. |

## Amendment

The [evolution engine](../docs/EVOLUTION.md) may **amend** the constitution —
but only to *add* principles or *tighten* existing ones. Any proposed amendment
that removes or weakens an `immutable: true` principle is rejected by
`Constitution.validate_amendment()`. This makes the factory's values a ratchet:
they can get safer over time, never less safe.
