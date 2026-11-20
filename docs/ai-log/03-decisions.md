# Decisions log

This file records every change from the approved plan ([`01-plan.md`](01-plan.md), kept
verbatim as approved) and every accept/reject decision on the second-model critique
(`02-critique.md`, to be added).

## Changes from the approved plan

| # | Plan section | Approved text | What was done instead | Why | Milestone |
|---|---|---|---|---|---|
| D1 | §0 Location, §7 step 1 | New local folder with `git init`; the user creates the GitHub repo and pushes | The user created `DrewDebugs/RO-Explorer` on GitHub; Claude clones it and commits and pushes directly | The user's choice after the plan was approved | M0 |
| D2 | §2 file tree, §7 step 4 | Folder `ro-explorer/`; site at `https://<user>.github.io/ro-explorer/` | Repo is `RO-Explorer`; site will be at `https://drewdebugs.github.io/RO-Explorer/` | Matches the actual repo name. Pages URLs are case-sensitive in the path | M0 |
| D3 | §0 Still open (pinned versions) | Pyodide stable at build time, “expected 0.27.x / Python 3.12” | **Pyodide 314.0.7** (Python 3.14.2, numpy 2.4.6). CI uses Python 3.14 and `numpy==2.4.6` | The plan pinned “stable at build time”; 0.27.x was only a guess. Pyodide moved to Python-based version numbers (314.x = Python 3.14). 314.0.8 (13 Nov 2026) was skipped as less than two weeks old at build time. Versions read from that release's `pyodide-lock.json` | M0 |
| D4 | §5 M0 | “CI runs an empty pytest” | CI runs a 3-test smoke file (`tests/test_smoke.py`): Python and numpy match Pyodide; the plan file exists | pytest returns exit code 5 (failure) when it collects no tests, so a truly empty run would break CI. The smoke test also guards the CPython/Pyodide version match (plan §6 risk) | M0 |
| D5 | §7 step 2 | One workflow that tests, builds and deploys | The M0 workflow only runs tests; build and deploy jobs are added at M10 | There is no page to deploy yet, and a deploy job would fail until Pages is enabled | M0 |
| D6 | §3.2 Pitzer | π = φ(m)·i·m·ρw·R·T, molality “approximated from g/L” | Molality estimated as m = (C/M)/ρw, so π_Pitzer = φ(m) × π_van’t Hoff exactly | Makes the relation between the two models explicit and keeps the van’t Hoff limit exact as m → 0. Underestimates true molality by ~2 % at 35 g/L (documented in the code) | M1 |
| D7 | §3.6 SEC_min integral | “evaluated numerically (Simpson’s rule)” | Simpson’s rule after substituting u = −ln(1 − r′); default n = 128 intervals | In u the integrand is π(C_f e^u)e^−u, which is constant for van’t Hoff and nearly constant for Pitzer, so Simpson stays accurate near r → 1. Checked against SciPy `quad` in the original variable (< 10⁻⁸) | M1 |
| D8 | §5 M1, §2 | `docs/sources-checklist.md` created at M7 | Started at M1 and extended each milestone | Each number gets logged when it enters the code, so none are missed | M1 |

## Critique: accept / reject

*(Filled in after `02-critique.md` is added.)*

| # | Critique point | Accepted? | Action / reason |
|---|---|---|---|
