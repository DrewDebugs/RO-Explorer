# Prompts: planning session

Two steps came before the build session in [`02-build-session.md`](02-build-session.md):

1. A **claude.ai chat with Claude** (pinned “Separation Processes” conversation), where the student
   picked the topic and Claude wrote the plan-mode prompt.
2. A **Claude Code session in plan mode**, where that prompt produced the plan saved verbatim in
   [`../01-plan.md`](../01-plan.md). The answers to Claude Code's clarifying questions are recorded in the
   plan itself (§0, “Decisions already made (from the clarifying questions)”).

The student's messages and the plan-mode prompt are **verbatim** (spelling kept as typed). Claude's
replies in the chat were long, so each is *[summarised in square brackets and italics]*.

---

## Part 1: claude.ai chat (topic choice and plan prompt)

**1.**
```text
I have to do an AI project for this class and these are the instructions     
Submissions must have the following components:
1. Publicly accessible website demo/documentation.  There are many options for you to choose from; a standalone WebAssembly build hosted on GitHub Pages is recommended, e.g., https://chetools.github.io/claude/packed-bed-runaway/
2. YouTube video of presentation - include as a link in the project website.  Copy and paste (Practice transcript, and AI critique to the comments section).  Include the link of the AI project and this submission requirements in your prompt requesting for a detailed critique.
3. Verbatim YouTube auto-generated transcript of the presentation - viewable section of the project website
4. Presentation/Documentation
Overview.  Demo what you/AI created.  Make it clear that it is an AI project exploring AI capabilities.  Explain the process, i.e., AI models, local/cloud services, prompts, etc., used to create it.  Focus on the planning, iteration steps where you provided guidance and your reasoning.  Explain key technical details of content related to this course and what you learned and what you want to learn more of in the future.   Attribution/references.

Projects should compare the outcomes using different AI models.
After generating a plan from one model, have a different AI model critique and suggest improvements.  Justify your decisions on what to accept/reject.  Implement the plan using at least 2 different AI models and compare.

Attribution/references, and what each group member contributed. Each member must submit the project separately (max of 20 points for each member on groups of up to 4, max of 50 points for individual submission)
In class presentations on the last day of class and on scheduled final exam time/location.
```
*[Claude reviewed the example project (a packed-bed reactor app on GitHub Pages, with a Rust/WebAssembly
solver, a Pyodide Python reference and pytest/cargo tests), turned the instructions into a checklist, and
suggested a distillation design tool (McCabe–Thiele, Ponchon–Savarit, FUG shortcut) built with two AI
models.]*

**2.**
```text
I want you to look through the lectures to understand what kind of topics he wants for this project and report back
```
*[Claude summarised what the lecturer said about the project across the lecture transcripts: he wants
separations not covered in class (mechanical vapor recompression, liquid–liquid extraction, membrane
separations / reverse osmosis, crystallization, chromatography), starting with industrial significance and
then theory; or an extension of a course topic, such as adding economics to a column design. His build
advice: start in plan mode and read the plan, demo as a web app, have the AI verify the site itself, try a
weak model first and compare, have another model critique the work, and document everything. Grading
rewards resourcefulness and being able to explain the work. Claude noted that a pure distillation tool
would overlap with the lecturer's own Ponchon–Savarit tool.]*

**3.**
```text
I will do reverse osmosis for water purification
```
*[Claude outlined how RO fits the lecturer's structure (significance, then theory: osmotic pressure,
solution–diffusion, concentration polarization, the recovery limit as an analogue of the McCabe–Thiele
pinch, energy and economics) and what the app could do.]*

**4.**
```text
yes including developing a (/plan) prompt for claude code and how to execute what im doing
```
*[Claude wrote a project plan (site sections and the 1D model), the plan-mode prompt below, and a step-by-step
workflow: set up a cloud Claude Code session linked to a GitHub repo; plan with model A; have model B critique
the plan and record accept/reject decisions; build it twice with two different AI models and compare; check
every number against its source; record a practice video, get an AI critique and post both in the YouTube
comments; then record the final video and put its auto-transcript on the site.]*

## Part 2: the plan-mode prompt given to Claude Code

Pasted into Claude Code (cloud session, plan mode). The plan it produced, after the clarifying questions,
is [`../01-plan.md`](../01-plan.md).

```text
I'm a chemical engineering student. For my Separation Processes course I'm building an AI project: an educational website on reverse osmosis (RO) for water purification. Do NOT write code yet. Produce a detailed implementation plan, and ask me clarifying questions first if anything is ambiguous.

PROJECT GOAL
A publicly accessible, single-page educational website + interactive calculator on GitHub Pages that teaches RO desalination and lets users explore an RO module model. It must state clearly that it is an AI project exploring AI capabilities.

HOSTING / ARCHITECTURE REQUIREMENTS
- Static site on GitHub Pages; all computation client-side (no server).
- Model written in Python, run in the browser via WebAssembly (Pyodide). In the plan, compare 2–3 options (e.g., plain HTML + Pyodide, marimo notebook exported to WebAssembly HTML, Rust→WASM) with pros/cons and recommend one. Keep the code readable for a ChE student.
- Plotly for plots; KaTeX or MathJax for equations.
- Repo layout: core model as pure, documented Python functions (e.g., ro_model.py), tests/ with pytest, index.html, README, and docs/ai-log/ for my AI process documentation.

PAGE SECTIONS
1. Overview (AI project statement; what the app does).
2. Industrial significance: applications (seawater/brackish desalination, ultrapure water, reuse), major plants, membrane manufacturers, dominant countries/companies, typical energy use. EVERY number must have a cited source. Never invent figures. If unsure, leave a clearly marked TODO for me to verify.
3. Theory with equations and plain-language explanation: osmotic pressure (van't Hoff, and its limitations), solution–diffusion model (water flux J_w = A(ΔP − Δπ), salt flux J_s = B(C_m − C_p)), observed vs intrinsic rejection, recovery, concentration polarization (film model C_m = C_p + (C_b − C_p)exp(J_w/k)), the thermodynamic limit (brine osmotic pressure rises along the module; flux → 0 where ΔP = π; r_max = 1 − π_f/ΔP for ideal rejection without CP; analogy to a "pinch" in McCabe–Thiele), minimum specific energy SEC_min = π_f·ln(1/(1−r))/r, energy recovery devices, spiral-wound modules, stages and passes, fouling/scaling and pretreatment (qualitative).
4. Interactive app:
   - Inputs (sliders + number boxes, with sensible documented defaults and units): feed salinity (g/L NaCl), feed pressure (bar), feed flow, temperature, water permeability A (LMH/bar), salt permeability B (LMH), mass-transfer coefficient k, membrane area / element length, pump efficiency, ERD efficiency (on/off), electricity price, membrane cost.
   - Model: 1D discretization along the membrane length solving the local flux equations with mass balances (dQ/dx = −J_w·W, d(QC)/dx = −J_s·W), local CP, local permeate concentration; optional linear feed-side pressure drop.
   - Outputs/plots: flux, bulk and membrane-surface concentration, osmotic pressure vs applied pressure along the length (show where net driving pressure → 0), CP factor; summary of recovery, permeate concentration, rejection, SEC with/without ERD vs SEC_min, cost per m³.
   - Warn the user when inputs exceed the thermodynamic limit.
5. Economics: simple CAPEX (membrane area, pump) + OPEX (electricity) → annualized $/m³, with all cost inputs editable and sourced defaults.
6. Validation section showing test results.
7. AI process log (I will supply content): plan, second-model critique, accept/reject decisions, comparison of two implementations, prompts.
8. Presentation: embedded YouTube video + full verbatim transcript (I will supply).
9. References and attribution.

VALIDATION TESTS (pytest; show results on the page)
- Zero-recovery limit: J_w equals A(ΔP − π_f) analytically when area → 0 (no CP).
- Mass balance closure (water and salt) to < 1e-6 relative error.
- SEC ≥ SEC_min for every run.
- SEC_min function matches the analytic formula; for 35 g/L at 50% recovery, compare with the literature value (~1.06 kWh/m³, Elimelech & Phillip, Science 2011) and explain any difference from the van't Hoff approximation.
- Max recovery with ideal rejection and k → ∞ approaches 1 − π_f/ΔP.
- CP factor → 1 as k → ∞; higher pressure → higher flux and higher rejection.
- Unit consistency (bar, LMH, kWh/m³).

VERIFICATION OF THE WEBSITE
After building, open the site in a browser, take screenshots of every section, and confirm all equations render, plots appear, sliders update results, and there are no console errors. Fix issues before reporting done.

PLAN OUTPUT I WANT
- Clarifying questions (first).
- Recommended architecture with justification and alternatives considered.
- File structure.
- Step-by-step milestones with what gets tested at each.
- Equations and numerical method (discretization, step count, convergence check).
- Default parameter values with the source for each.
- Risks/limitations (e.g., van't Hoff vs real seawater, constant A/B, Pyodide load time) and mitigations.
- Deployment steps for GitHub Pages.
- Save the final plan as docs/ai-log/01-plan.md.
```

## Part 3: the critique prompt suggested for the second model

The chat suggested this prompt for the second-model critique (the result is
[`../02-critique.md`](../02-critique.md), by Muse). *Student: if you changed the wording when you used it,
replace this with what you actually sent.*

```text
Below are my course's AI-project requirements and an implementation plan another AI wrote for a reverse osmosis educational web app. Critique the plan in detail: (1) physics/engineering correctness of every equation and assumption, (2) anything missing relative to the requirements, (3) feasibility of the architecture on GitHub Pages, (4) gaps in validation/testing, (5) concrete improvements, ranked by importance. Be specific and skeptical.
[paste the requirements text]
[paste 01-plan.md]
```
