# RO Desalination Explorer: Implementation Plan

**Status:** plan only, no code written yet. On approval, this file is saved verbatim as `docs/ai-log/01-plan.md` in the new repo.
**Author:** Claude (Opus 5.5) in Claude Code, for a Separation Processes course AI project.

## 0. Context

The goal is a public, single-page educational site on GitHub Pages that teaches reverse osmosis (RO) desalination. It includes an interactive 1D model of an RO pressure vessel. The model is written in Python and runs in the browser through Pyodide (WebAssembly), so no server is needed. The site states clearly that it is an AI project. It also records the AI process (plan, critique, decisions, prompts) in `docs/ai-log/`.

### Decisions already made (from the clarifying questions)

| Question | Decision |
|---|---|
| Physical scale | One pressure vessel with N_e = 7 spiral-wound 8-inch elements in series. The 1D coordinate x runs along the vessel (L ≈ 7 m). Economics scale to a user-set plant capacity by counting vessels. |
| Osmotic pressure | van’t Hoff by default, plus a toggle for an NaCl osmotic-coefficient (Pitzer) correction. The page shows the difference between the two. |
| Citations | I research primary sources and cite every number. Anything I can’t confirm becomes a visible TODO-VERIFY. A checklist (`docs/sources-checklist.md`) lists every number for you to verify. |
| Location | A new folder you pick after approval. I run `git init` there. You create the GitHub repo and push (I’ll give you the exact commands). |

### Still open (I’ll use these defaults unless you say otherwise)

- **Pinned versions:** Pyodide stable at build time (expected 0.27.x / Python 3.12), Plotly.js 2.x, KaTeX 0.16.x. All exact versions are pinned from a CDN.
- **“Comparison of two implementations” (AI log §7):** I’ll write a second, independent reference solver (SciPy `solve_ivp` + `brentq`, run in CPython only) and cross-check it against the browser solver. You can also compare against another AI model’s implementation and log that yourself.
- **Brackish preset:** one-click presets for Seawater (35 g/L, 60 bar) and Brackish (3 g/L, 15 bar, higher A).

## 1. Architecture: options compared

| | A. Plain HTML + Pyodide (recommended) | B. marimo notebook → WASM HTML | C. Rust → WASM |
|---|---|---|---|
| Model language | Python (`ro_model.py`, the same file pytest tests) | Python (cells, or an imported module) | Rust. Fails the “model in Python” requirement. |
| Readability for a ChE student | High: a plain Python module plus a small, commented JS glue file | High for the model; the UI is in Python too | Low |
| Long-form page (theory, citations, video, transcript) | Full control over HTML/CSS layout, anchors and nav | Notebook layout; long prose and custom layout are clumsy | Full control |
| Equations | KaTeX auto-render | marimo markdown supports KaTeX | KaTeX |
| Plots | Plotly.js directly, fast to update | Plotly via Python wrapper (slower to re-render) | Plotly.js |
| Load time | Pyodide core + numpy ≈ 8–12 MB, about 3–8 s on first visit, then cached | Pyodide plus the marimo runtime: heavier and slower | Very fast (< 1 MB) |
| Single source of truth | Yes: the browser fetches the same `ro_model.py` | Yes, but export and versioning add friction | No: two implementations to keep in sync |
| Risk | You write some JS glue (~200 lines) | Tied to marimo’s export format and version churn | Off-requirement |

**Recommendation: A.** It is the only option where the exact file that pytest validates is the file running in the browser. It gives full control over a long educational page, and it keeps the Python free of web concerns. PyScript (a wrapper around Pyodide) was also considered. It adds an abstraction layer and saves little at this size, so plain Pyodide is used.

**Dependency choice:** the browser model uses only numpy. SciPy is not loaded in the browser because it adds several MB and noticeably more load time. The local root-finder is a short, readable bracketed solver (bisection/Illinois) written by hand. SciPy is used only in tests as the independent reference.

## 2. File structure

```
ro-explorer/
├─ index.html                 # the single page (all 9 sections)
├─ assets/
│  ├─ app.js                  # Pyodide boot, input wiring, Plotly rendering (commented)
│  ├─ style.css               # light/dark, responsive
│  └─ references.js           # (optional) citation data rendered into §2/§9
├─ ro_model.py                # CORE MODEL: pure, documented functions, numpy only
├─ validation.py              # check functions shared by pytest AND the live browser panel
├─ tests/
│  ├─ conftest.py             # writes results.json (name, status, numbers) after the run
│  ├─ test_properties.py      # units, osmotic pressure, SEC_min
│  ├─ test_local_flux.py      # local solver limits
│  ├─ test_module.py          # 1D solver: balances, r_max, convergence
│  ├─ test_energy_cost.py     # SEC ≥ SEC_min sweep, ERD, cost hand-calc
│  └─ reference_impl.py       # independent SciPy implementation (second implementation)
├─ validation/results.json    # produced in CI and shown on the page
├─ docs/
│  ├─ ai-log/
│  │  ├─ 01-plan.md           # this plan
│  │  ├─ 02-critique.md       # (you) second-model critique
│  │  ├─ 03-decisions.md      # accept/reject table
│  │  ├─ 04-implementation-comparison.md
│  │  └─ prompts/             # verbatim prompts
│  ├─ sources-checklist.md    # every number → source → verified? (for you)
│  └─ transcript.md           # (you) video transcript, also inlined into the page
├─ requirements-dev.txt       # pytest, numpy, scipy (pinned)
├─ .github/workflows/pages.yml
├─ LICENSE                    # MIT (code); content CC BY 4.0 (stated in README)
└─ README.md
```

## 3. Equations and numerical method

### 3.1 Units

Inside `ro_model.py` everything is in SI: m, s, Pa, kg/m³ (which equals g/L), mol/m³, K. Conversions happen only at the boundary, in named helpers that are tested:

- 1 LMH = 1 L m⁻² h⁻¹ = 2.7778×10⁻⁷ m/s
- 1 LMH/bar = 2.7778×10⁻¹² m s⁻¹ Pa⁻¹
- 1 bar = 10⁵ Pa = 10⁵ J/m³ = 1/36 kWh/m³ (so SEC in kWh/m³ = ΔP[bar]/36 for ideal pumping)

### 3.2 Properties

- **van’t Hoff:** π = i·c·R·T with i = 2 and c = C/M_NaCl (M = 58.44 g/mol). For 35 g/L at 25 °C this gives π ≈ 29.7 bar.
- **Pitzer correction (toggle):** π = φ(m)·i·m·ρw·R·T. Here φ comes from the Pitzer NaCl parameters at 25 °C (Pitzer & Mayorga 1973: β⁰ = 0.0765, β¹ = 0.2664, C^φ = 0.00127, Aφ = 0.392). This gives φ ≈ 0.92 at 0.6 mol/kg, so π ≈ 27.4 bar. Molality is approximated from g/L (documented as a limitation). The T-dependence of the Pitzer parameters is ignored.
- **Temperature correction of A and B:** an Arrhenius-type TCF from the membrane manufacturer’s design manual (TODO-VERIFY constant, about 2640–3020 K). k is held constant (stated as a limitation).

### 3.3 Local (per-position) solution–diffusion + film model

At position x, given bulk concentration C_b and feed-side pressure P (permeate at P_p ≈ 1 atm), the unknowns are J_w, C_m and C_p:

- J_w = A[(P − P_p) − (π(C_m) − π(C_p))]
- J_s = B(C_m − C_p), C_p = J_s/J_w (local permeate)
- C_m = C_p + (C_b − C_p)·exp(J_w/k)

**Key simplification:** for a given J_w, write E = exp(J_w/k). Then C_p and C_m have closed forms:

- C_p = B·E·C_b / (J_w + B·E)
- C_m = C_p + (C_b − C_p)·E

So the whole local problem reduces to one scalar equation f(J_w) = J_w − A[ΔP − π(C_m) + π(C_p)] = 0.

- For B > 0, f(0⁺) = −AΔP < 0 (at zero flux the membrane rejects nothing) and f(AΔP) = A·Δπ ≥ 0. So a root always exists in (0, AΔP] and is found by a bracketed solver. This is a teaching point: with a leaky membrane, flux never quite reaches zero. Instead, rejection collapses as the net driving pressure (NDP) approaches zero.
- For B = 0 (ideal rejection): if ΔP ≤ π(C_b), then J_w = 0 exactly. This is the pinch.
- **Solver:** Illinois (modified regula falsi) with a bisection fallback, tolerance |f| < 10⁻¹² m/s, at most 100 iterations. It is cross-checked against `scipy.optimize.brentq` in tests.
- CP factor = C_m/C_b. Local observed rejection = 1 − C_p/C_b. Local intrinsic rejection = 1 − C_p/C_m.

### 3.4 1D module (pressure vessel) balances

The state vector is y = [Q, S, Q_p, S_p, P], where S = Q·C_b is the salt mass flow. W is the effective membrane width, W = A_m/L, with A_m = N_e × A_element.

- dQ/dx = −J_w·W, dS/dx = −J_w·C_p·W
- dQ_p/dx = +J_w·W, dS_p/dx = +J_w·C_p·W (permeate accumulators)
- dP/dx = −ΔP_drop/L (optional linear pressure drop; 0 when switched off)

**Discretization:** classical RK4 with N uniform steps along x. The default is N = 200. Each RK4 stage calls the local solver, so a run is about 800 scalar solves, which takes tens of ms in Pyodide.

**Convergence check (automatic, on every run):** solve with N and 2N, then compare recovery, C_p (mixed) and SEC. If the max relative change is > 10⁻⁴, double N (up to N = 3200) and report the N used. The page shows “converged at N = …”.

**Pinch handling:** if the local flux falls below 1% of its inlet value (or is exactly 0 for B = 0), mark x_pinch. Downstream area makes almost no permeate. The plot shades that region and a warning appears.

**Outputs:** recovery r = Q_p/Q_f; mixed permeate C_p = S_p/Q_p; observed rejection R = 1 − C_p/C_f; brine C_b,out; and all profiles vs x.

### 3.5 Thermodynamic limit (why “pinch”)

- With ideal rejection and no CP, the brine at recovery r has πb = πf/(1 − r). Flux stops where ΔP = πb, which gives r_max = 1 − πf/ΔP.
- The analogy to McCabe–Thiele: the operating line touching the equilibrium curve gives infinite stages. Here, the applied pressure line touching the rising brine osmotic pressure curve gives infinite area. Adding membrane area past that point buys nothing.
- **Pre-run warnings:**
  - ΔP ≤ π_f: no production.
  - The predicted r approaches r_max (> 90% of r_max).
  - P > the typical SWRO element limit (~83 bar, TODO-VERIFY datasheet).
  - C_b,out above a stated brine/scaling guideline.

### 3.6 Energy

- **Pump energy, no ERD:** SEC = ΔP_f / (η_p·r)
- **With ERD** (pressure exchanger, brine leaves at P_b = P_f − ΔP_drop): SEC = [ΔP_f − ηERD·(1 − r)·(P_b − P_p)] / (ηp·r). Booster-pump details are ignored and documented as a simplification.
- **SEC_min (reversible, ideal rejection):** SEC_min = (1/r)∫₀ʳ π(C_f/(1 − r′)) dr′. With van’t Hoff this reduces to the analytic π_f·ln(1/(1 − r))/r. With the Pitzer toggle it is evaluated numerically (Simpson’s rule).
- **SEC_min for the actual separation (leaky membrane):** this is the test bound. A leaky membrane at low NDP can legitimately go below the ideal-rejection SEC_min, because it makes impure water. So “SEC ≥ SEC_min” is tested against the minimum work for the actual product and brine concentrations: W_min = V_p·f(C_p) + V_b·f(C_b) − V_f·f(C_f), where f(c) = c·∫_{c_ref}^{c} π(c′)/c′² dc′ is the free-energy density consistent with π(c) (dilute-solution approximation). For van’t Hoff this is iRT·c·ln c, and it reduces to the formula above as C_p → 0. Both bounds are shown on the page.
- **Single-stage practical bound (shown for teaching):** π_f/(1 − r), which is ΔP at the pinch.

### 3.7 Economics (simple, all inputs editable)

- **Plant:** capacity Q_plant (m³/d) and availability (default 0.95). Number of vessels = Q_plant / (vessel permeate × 24 h).
- **CAPEX:**
  - membranes: $/element × elements
  - pressure vessels: $/vessel
  - high-pressure pump + ERD: $/kW of installed power
  - × an “other plant” (installation/intake/pretreatment) multiplier
- Annualize with CRF = i(1+i)ⁿ/((1+i)ⁿ − 1). Defaults: i = 8%, n = 25 yr. Membranes are replaced every n_m ≈ 5–7 yr as an annualized OPEX line.
- **OPEX:** electricity (SEC × price) + membrane replacement + a fixed O&M fraction of CAPEX.
- **Output:** a $/m³ breakdown (stacked bar). The page compares the result to a cited typical SWRO water-cost range and labels it clearly as a teaching model, not a cost estimate.

## 4. Default parameters (each will be sourced; TODO-VERIFY = I could not yet confirm)

| Input | Default | Range (slider) | Intended source (to confirm during research) |
|---|---|---|---|
| Feed salinity | 35 g/L NaCl | 0.5–70 | Standard seawater ~35 g/kg (Millero et al. 2008, Deep-Sea Res. I) |
| Feed pressure | 60 bar | 5–85 | Typical SWRO 55–70 bar (Elimelech & Phillip 2011, Science; manufacturer manual) |
| Feed flow / vessel | ~9 m³/h | 2–16 | Element feed-flow limits from datasheet; tuned so defaults give ~40–45% recovery (documented) |
| Temperature | 25 °C | 5–40 | Datasheet test condition |
| A | 1.0 LMH/bar | 0.3–10 | SWRO ~1–1.5, BWRO 3–7 (Werber, Osuji & Elimelech 2016, Nat. Rev. Mater.) |
| B | 0.10 LMH | 0–1 | Same as above |
| k | 180 LMH (5×10⁻⁵ m/s) | 20–2000 | Spiral-wound mass-transfer literature / design CP-factor guideline ≤ 1.2 (TODO-VERIFY) |
| Elements per vessel / area | 7 × 40.9 m², L = 7 × 1.016 m | 1–8 elements | 8-inch SWRO element datasheet (440 ft², 40 in) |
| Pressure drop | 1.5 bar per vessel (toggle) | 0–5 | Datasheet / design manual |
| Pump efficiency | 80% | 50–90% | Literature/manual |
| ERD efficiency | 95% (on) | 80–98% | Pressure-exchanger literature (TODO-VERIFY vendor claim vs independent) |
| Electricity | $0.08/kWh | 0.02–0.30 | EIA/IEA industrial average (TODO-VERIFY) |
| Membrane element | $600 / 8-in element | 200–1500 | TODO-VERIFY (Voutchkov 2018 cost text or literature) |
| Plant capacity | 100,000 m³/d | 1,000–1,000,000 | Illustrative |
| Interest / life | 8% / 25 yr | editable | Common engineering-economics assumptions (stated as assumptions) |

**Rule:** defaults are tuned only within sourced ranges, and any tuning is written down in `docs/ai-log/03-decisions.md`.

**Industrial-significance facts to research and cite** (none are used until sourced):

- installed global capacity and RO share (e.g., Jones et al. 2019, Sci. Total Environ.)
- regional and country dominance
- the largest RO plants (e.g., Taweelah, Sorek/Sorek-2, Carlsbad), using plant-operator or peer-reviewed sources
- major membrane manufacturers (DuPont/FilmTec, Toray, Nitto Hydranautics, LG Chem, …)
- typical SWRO SEC (~2.5–4 kWh/m³ total)
- applications: seawater, brackish, ultrapure water, potable reuse

## 5. Milestones (each ends with green tests)

| # | Milestone | Tested at this step |
|---|---|---|
| M0 | Project folder, git init, save plan to `docs/ai-log/01-plan.md`, README skeleton, CI workflow skeleton | CI runs an empty pytest |
| M1 | `ro_model.py`: unit helpers, π (vH + Pitzer), TCF, SEC_min (analytic + integral) | Units round-trip (bar, LMH, LMH/bar, kWh/m³). π(35 g/L) ≈ 29.7 bar (vH). SEC_min analytic = integral (< 10⁻⁸ rel). 35 g/L, r = 0.5: vH → ~1.14 kWh/m³; Pitzer → ~1.06 kWh/m³ vs Elimelech & Phillip 2011 (1.06), with the ~8% gap explained by φ ≈ 0.92 |
| M2 | Local solver (closed-form C_p/C_m + Illinois) | k → ∞: CP factor → 1. Zero-recovery limit: with k → ∞, B = 0, area → 0: J_w = A(ΔP − π_f) to 10⁻⁹. B = 0 with ΔP ≤ π → J_w = 0. Matches brentq |
| M3 | 1D RK4 module + auto-convergence + pinch detection | Mass balance (water and salt) closure < 10⁻⁶ rel. Grid convergence: observed order ≈ 4. r_max: B = 0, k → ∞, large area → r → 1 − π_f/ΔP (within 10⁻³). Higher P → higher flux and higher rejection (monotonic over a sweep) |
| M4 | Energy + economics | SEC ≥ SEC_min(actual separation) over a seeded random sweep (~500 cases), plus ≥ ideal SEC_min when B = 0. ERD lowers SEC. Cost function matches a hand calculation |
| M5 | `reference_impl.py` (SciPy solve_ivp, brentq) | Profiles agree with the main solver to < 10⁻⁵ rel. Written up in `04-implementation-comparison.md` |
| M6 | `validation.py` + `conftest.py` → `results.json` | Results file contains every test with measured numbers |
| M7 | `index.html` content: §1–3, 5, 9 with KaTeX and citations; research pass; `sources-checklist.md` | No uncited number (grep check for figures without a citation marker) |
| M8 | `app.js`: Pyodide boot (loading bar), slider ↔ number-box sync, 150 ms debounce, presets, Plotly plots, warnings | Manual + browser checks (see §8) |
| M9 | Validation section (§6): CI results table + a “re-run checks in your browser” button calling `validation.py` | Browser and CI agree |
| M10 | Placeholders for §7 AI log, §8 YouTube + transcript, then deploy | Live URL loads |

**Plots in §4:**

- J_w(x) with NDP(x)
- C_b, C_m, C_p vs x
- P(x) vs πb(x) and πm(x), with the NDP gap shaded and the pinch marked
- CP factor (x)
- SEC bar chart: no ERD / ERD / SEC_min (actual) / SEC_min (ideal) / π_f/(1 − r)
- Recovery vs feed pressure sweep with the r_max = 1 − π_f/ΔP curve overlaid (the “pinch” picture)

## 6. Risks / limitations and mitigations

| Risk | Mitigation |
|---|---|
| van’t Hoff overestimates seawater π (~8%), and real seawater isn’t NaCl | Pitzer toggle. The difference is shown explicitly. The text explains it, and the SEC_min test quantifies it. |
| Constant A, B, k (no pressure/concentration/compaction dependence; k is not tied to crossflow velocity) | Stated on the page. TCF covers temperature for A and B only. k is user-editable, with a note that it falls along the vessel as crossflow decreases. |
| Lumping a vessel into one 1D channel (W = A_m/L); spacers, permeate pressure and channel geometry ignored | Documented. Element datasheets are used only for orders of magnitude, not to claim a match. |
| No fouling or scaling in the model | Covered qualitatively in §3. A warning appears when brine concentration exceeds a guideline value. |
| Pyodide first load 3–8 s; mobile memory | Loading bar. Theory content renders immediately without Python. numpy only (no SciPy). The CDN is cached. Inputs stay disabled until ready. |
| Python version mismatch (CPython tests vs Pyodide) | Pin Pyodide. CI uses the same Python minor version. Browser verification runs the live validation checks. |
| Leaky membrane makes the “SEC ≥ SEC_min” test ambiguous | Use the actual-separation bound (§3.6). Both bounds are explained on the page. |
| Invented or unverifiable figures | Hard rule: no number without a citation. TODO-VERIFY badges are visible on the page. `sources-checklist.md` is for your sign-off. |
| Root-finder failure near pinch | Bracketed method (guaranteed convergence). Tests cover the pinch, ΔP < π_f, and B = 0. |
| Economics oversimplified | Labeled “teaching model”. All inputs editable. Compared against a cited literature range. |

## 7. Deployment (GitHub Pages)

1. You create an empty public GitHub repo (e.g. `ro-explorer`), and I give you the `git remote add` / `git push` commands.
2. `.github/workflows/pages.yml` runs on each push to `main`:
   - checkout → setup-python (pinned) → `pip install -r requirements-dev.txt`
   - pytest, which writes `validation/results.json`. The build fails on a test failure.
   - copy `index.html`, `assets/`, `ro_model.py`, `validation.py` and `validation/` into `_site/`
   - `actions/upload-pages-artifact` → `actions/deploy-pages`
3. In the repo, go to Settings → Pages → Source: GitHub Actions.
4. The site is served at `https://<user>.github.io/ro-explorer/`. All asset paths are relative, so the subpath works.
5. The README shows a CI badge and links to the live site.

## 8. Verification (before reporting done)

1. `pytest -q`: all green. Print the summary and coverage of `ro_model.py`.
2. Serve locally (`python -m http.server`) and open the page in the built-in browser. Then:
   - screenshot every section (desktop and ~375 px mobile width)
   - equations: no `.katex-error` elements; inline and display math are visible
   - plots: each Plotly div has rendered traces
   - sliders: move feed pressure, A and salinity, and confirm the summary numbers and plots change and that the number box and slider stay in sync
   - warnings: set P < π_f and P near the pinch, and confirm the warning appears
   - console: `read_console_messages` shows no errors
   - the “re-run validation” button matches CI results
3. Fix any issue and repeat. Then report, with screenshots attached.
4. After you push: repeat the smoke check on the live URL.

## 9. Page sections ↔ sources of content

| § | Content | Who |
|---|---|---|
| 1 Overview | AI-project statement (model, tool, what was AI-generated vs human-verified), what the app does | Me (draft) → you approve |
| 2 Industry | Researched and cited; TODO-VERIFY where unsure | Me → you verify |
| 3 Theory | Equations + plain language (§3 of this plan) | Me |
| 4 App | Model + plots | Me |
| 5 Economics | §3.7 | Me |
| 6 Validation | CI + live checks | Me |
| 7 AI log | Plan (this), critique, decisions, comparison, prompts | You supply; I format |
| 8 Presentation | YouTube embed (youtube-nocookie.com) + verbatim transcript | You supply |
| 9 References | Full citation list (DOIs/URLs), library credits (Pyodide, numpy, Plotly, KaTeX), AI attribution | Me |
