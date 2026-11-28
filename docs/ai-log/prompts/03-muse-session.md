# Prompts: second AI model (Muse)

The conversation with Muse, the second AI model, which produced the critique
([`../02-critique.md`](../02-critique.md)), an audit of the decisions log, and an independent
implementation of the model ([`../second-model/`](../second-model/)).

The student's messages are **verbatim**. Muse's replies are summarised *[in square brackets and
italics]*; their outputs are saved verbatim as files. The copy of the conversation the student pasted
starts with Muse's first reply, so the opening message (sending Muse the plan and the course
requirements) is not shown; the suggested wording for it is in
[`01-planning-session.md`](01-planning-session.md), Part 3.

---

## Step 1: critique of the plan

**1.** *[Opening message, not in the pasted copy: the plan (`01-plan.md`) sent to Muse for critique.]*

*[Muse re-derived the plan's key numbers (π = 29.7 bar, SEC_min 1.14 / 1.06 kWh/m³, r_max = 0.505,
unit conversions, CP ≈ 1.18), gave the verdict “approve with fixes”, listed five must-fix items (SEC
formula missing /36, default operating point near the pinch, constant k, permeate pressure and pressure
drop at the pinch, missing economics defaults) and smaller issues, and asked whether to save the critique
or start building. An interactive choice widget was shown.]*

**2.**
```text
Critique only for now
```
*[Muse saved the critique as a draft `02-critique.md`; it is in the repo verbatim.]*

## Step 2: audit of the decisions log

**3.** *[The student shared `03-decisions.md` from the repo; the message itself is not in the pasted copy.]*

*[Muse checked the log against the plan and its own critique: it confirmed C1, C3, C4, D30's economics
(re-run: $1,438 per m³/day), D24, D6, D7, D12 and D29, and listed five fixes (critique-table numbering,
C2's percentage, economics calibration described as verification, the unexplained 1.42 vs 1.24 LMH/bar
gap, molality error 1 % not 2 %) plus three minor points (D26, D15, D28). It offered to patch the log.]*

## Step 3: patched log and an independent implementation

**4.**
```text
yes and also implement the plan and give me the file of the model code of the plan to give back to claude code for comparison
```
*[Muse returned three files, saved verbatim in [`../second-model/`](../second-model/): the patched
decisions log, its own numpy-only `ro_model.py`, and comparison notes with four questions for Claude
Code. It reported that its model matches the repo's default case exactly (43.7 %, 148 mg/L,
2.28 kWh/m³, $1,438 per m³/day).]*

## What happened next

The files were given to Claude Code, which ran both models side by side, answered every point
(M1–M13 in [`../03-decisions.md`](../03-decisions.md)) and wrote up the comparison in
[`../04-implementation-comparison.md`](../04-implementation-comparison.md). See
[`02-build-session.md`](02-build-session.md) for those prompts.
