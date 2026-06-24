# Vision — The Solopreneur Dark Factory

## The thesis

For all of software history, a company's output was bounded by how many skilled
people it could hire, coordinate, and retain. NYX rejects that bound.

A **dark factory** — borrowed from lights‑out manufacturing where automated
plants run without humans on the floor — is a codebase where AI agents *plan,
write, test, and ship* software with the human supervising **outcomes**, not
keystrokes ([Dark Factory pattern](https://aipatternbook.com/dark-factory),
[BCG Platinion](https://www.bcgplatinion.com/insights/the-dark-software-factory)).

By 2026 this is no longer theoretical. Frontier and strong open‑weight models
crossed the capability threshold; structured agent factories report **3–5×**
throughput over AI‑autocomplete workflows, and some teams generate over a
thousand AI‑authored pull requests per week. The leverage is real — but raw
leverage without **governance** is a liability.

NYX is the answer to a specific question:

> *What is the smallest, safest, most capable software company a single human can
> run — with zero physical employees and a swarm of agents that gets better
> every week?*

## The new org chart

| Classical company | NYX factory |
| --- | --- |
| Product manager | **Explorer** agent (finds & frames the opportunity) |
| Staff engineer / architect | **Architect** agent (designs the system) |
| Engineering team | **Coder** fan‑out swarm (parallel implementations) |
| Code reviewer | **Reviewer** agent (constitution + quality) |
| QA | **Tester** agent (acceptance + regression) |
| DevOps / release eng | **Deployer** agent (gated, reversible releases) |
| SRE / on‑call | **Operator** agent (health, incidents, ops excellence) |
| AppSec / red team | **Security** agent (injection, secrets, threat model) |
| The founder | **You** (intent, taste, the final gate) |

The founder's job compresses to the two things models are worst at and humans
are best at: **deciding what is worth building** and **owning the consequences**.

## Three non‑negotiables

1. **Constitution before capability.** A factory that can ship a thousand PRs a
   week can also cause a thousand incidents a week. NYX binds every agent to a
   machine‑readable [Constitution](../constitution/constitution.yaml) and refuses
   to let unconstitutional artifacts flow downstream. Safety and quality are
   *constructed in*.

2. **Evolution, not stagnation.** The factory keeps a
   [Darwin‑Gödel](https://arxiv.org/abs/2505.22954) archive of its own agents.
   A mutated agent (better prompt, better tool, better workflow) is admitted
   only if it empirically beats its ancestor on a benchmark. The company's
   engineering skill compounds automatically.

3. **Run it from a corner of a room.** The brain is [Ollama Cloud](https://docs.ollama.com/cloud);
   the body is a fanless **Windows 11 mini‑PC**. No data center, no ops team,
   no headcount. Capital expenditure: one mini‑PC and ~$20–100/month of model
   capacity.

## What "really large scale" means here

Scale in a dark factory is not headcount — it is **concurrent agent‑hours** and
**evolved capability**. A single operator can:

- run dozens of fan‑out swarms in parallel across multiple products,
- operate every shipped product 24/7 via the Operator agent,
- and compound engineering quality every evolution cycle —

…all from one machine, governed by one constitution, owned by one human.

That is the dark factory: **a company that is mostly software, building
software, supervised by a person who sets the direction and holds the line.**
