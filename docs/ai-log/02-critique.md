# Second-model critique — RO Desalination Explorer plan (01-plan.md)

**Critiquing model:** Muse
**Plan author:** Claude (Opus 5.5) in Claude Code
**Date:** 2026-11-27
**Scope:** `01-plan.md` as uploaded, plan only — no code written yet. This is the second-model critique for `docs/ai-log/02-critique.md`.
**Method:** Re-derived the key numbers independently (Python, SI units) rather than re-reading the plan's claims. Where a number could not be confirmed from the plan alone, it is marked TODO-VERIFY, not accepted.

## Verdict

**Approve with fixes.** Architecture A (plain HTML + Pyodide, same `ro_model.py` in browser and pytest) is the right choice, and the core model math is correct. Do not start M1 until the five must-fix items in §2 are addressed — two are formula / operating-point errors that would show up in the demo, three are missing inputs that make M4 untestable.

## 1. Numbers verified

| Claim in plan | Independent check | Result |
|---|---|---|
| van't Hoff π, 35 g/L NaCl at 25 °C ≈ 29.7 bar | c = 35 / 58.44 = 599 mol/m³; π = 2 × 599 × 8.314 × 298.15 = 2.97 MPa | **29.7 bar — correct** |
| Pitzer π ≈ 27.4 bar (φ ≈ 0.92) | 29.7 × 0.92 = 27.3 bar | **Correct** |
| SEC_min, r = 0.5, van't Hoff ≈ 1.14 kWh/m³ | π × ln(2) / 0.5 / 36 = 29.7 × 0.693 / 0.5 / 36 = 1.14 | **Correct** |
| SEC_min, Pitzer ≈ 1.06 kWh/m³ | 27.3 × 0.693 / 0.5 / 36 = 1.05–1.06 | **Correct, matches Elimelech & Phillip 2011 (1.06)** |
| r_max = 1 − π_f / ΔP at 60 bar | 1 − 29.7 / 60 = 0.505 | **0.505 — correct** |
| 1 LMH = 2.7778×10⁻⁷ m/s; 1 LMH/bar = 2.7778×10⁻¹² m s⁻¹ Pa⁻¹ | 0.001 m³ / 3600 s; ÷ 10⁵ Pa | **Correct** |
| 1 bar = 1/36 kWh/m³ | 10⁵ J/m³ ÷ 3.6×10⁶ J/kWh = 0.02778 | **Correct** |
| Element area 40.9 m², L = 7 × 1.016 m | 440 ft² = 40.9 m²; 40 in = 1.016 m | **Correct** |
| k = 180 LMH = 5×10⁻⁵ m/s | 180 × 2.7778×10⁻⁷ = 5.0×10⁻⁵ | **Correct** |
| Inlet CP factor ≈ 1.18 | J_w ≈ 29 LMH = 8.3×10⁻⁶ m/s; exp(J_w/k) = exp(0.167) = 1.18 | **Correct, within ≤1.2 guideline** |
| Local solver bracket, B > 0 | f(0⁺) = −AΔP < 0; f(AΔP) = AΔπ ≥ 0, Δπ = π(C_m) − π(C_p) ≥ 0 | **Root in (0, AΔP] holds** |
| SEC_min integral → analytic form | (1/r)∫₀ʳ π_f/(1−r′) dr′ = π_f ln(1/(1−r))/r | **Correct** |
| CRF = i(1+i)ⁿ/((1+i)ⁿ − 1) | Standard annualisation | **Correct** |

Additional checks run for context (not in the plan): SEC, no ERD, at r = 0.45, η_p = 0.80: 60 / (0.80 × 0.45) / 36 = **4.63 kWh/m³**. With ERD (η_ERD = 0.95, P_b = 58.5 bar): **2.31 kWh/m³**. Both are plausible for SWRO and bracket the cited 2.5–4 kWh/m³ total range once intake/pretreatment are added — the plan should show this comparison explicitly.

## 2. Must fix before M1

### 2.1 SEC formula in §3.6 is missing the /36 conversion
As written, SEC = ΔP_f / (η_p·r) yields bar, not kWh/m³. Same for the ERD version. Fix: divide by 36, or state ΔP in kWh/m³ units. This is a one-line fix, but if it ships as written the page's SEC numbers will be 36× too large.

### 2.2 Default operating point sits on the pinch
At 60 bar, r_max = 0.505. The tuned 40–45% recovery is 79–89% of r_max. The >90% r_max warning fires at 45.5% recovery, so the default demo will be borderline alarming. Options: lower default feed flow, raise default pressure to 65 bar, or move the warning to 95% of r_max and explain the choice. Do not leave the default and the warning threshold in conflict.

### 2.3 k is constant — and that biases the pinch
Crossflow falls ~45% along the vessel as permeate leaves, so the mass-transfer coefficient falls and concentration polarisation rises downstream. The model will underestimate CP and overestimate flux near the outlet — exactly where the pinch is decided. State this as a *bias*, not just a limitation, or make k a function of local Q. At minimum, add a test / note quantifying the direction of the error.

### 2.4 Permeate pressure and pressure drop are too clean at the pinch
P_p ≈ 1 atm constant and linear dP/dx are fine upstream, but near the pinch the net driving pressure is only a few bar, so a 0.5 bar error in P_p or ΔP_drop changes r_max noticeably. Flag this in the pinch section; do not present the pinch location as more precise than these assumptions allow.

### 2.5 Economics cannot be tested yet
M4 requires a hand calculation, but §4 gives no defaults for $/vessel or $/kW for pump + ERD. Fill those in (with sources or explicit TODO-VERIFY values) or M4 is untestable as written.

## 3. Smaller issues

- **Millero 35 g/kg ≠ 35 g/L.** At seawater density (~1.025 kg/L), 35 g/L is ~34.1 g/kg. Say 35 g/L ≈ 34 g/kg; do not cite Millero as exact for the g/L figure.
- **Brackish preset is incomplete.** It says "higher A" only. Brackish membranes also have higher B, and k / pressure drop differ. Specify B for that preset, or the preset will look unrealistically good.
- **SEC ≥ SEC_min test needs a tolerance.** Near the pinch, RK4 / Illinois error can violate a strict ≥ by ~10⁻⁴–10⁻³. Test SEC ≥ SEC_min − tolerance, and log the tolerance used.
- **Performance on slider drag.** N = 200, RK4, ~800 local solves is fine, but auto-convergence to N = 3200 is ~12,800 solves × ~10 Illinois iterations in Pyodide. With a 150 ms debounce that will lag on drag. Run the convergence check async, or only on slider release, not on every drag event.
- **Pitzer toggle is NaCl, not seawater.** Real seawater is not NaCl; φ_seawater ≠ φ_NaCl at the same molality. The toggle is a good teaching tool, but label it "NaCl Pitzer, not seawater Pitzer" on the page.
- **TCF constant (2640–3020 K) and ERD efficiency (95%)** remain TODO-VERIFY as the plan already notes. Do not hard-code a single value in §3.2 without the source in `sources-checklist.md`.

## 4. What to keep

- Plain Pyodide + numpy only, with the *same* `ro_model.py` in the browser and in pytest. This is the strongest decision in the plan.
- Illinois + `brentq` cross-check for the local solver, and the bracket argument as a teaching point.
- The actual-separation SEC_min bound (§3.6) — the correct way to handle the leaky-membrane case, where a membrane can legitimately go below the ideal-rejection SEC_min by making impure water. Show both bounds, as planned.
- Do not switch to marimo (export/version friction for a long page) or Rust (fails the "model in Python" requirement).

## 5. Suggested decisions for 03-decisions.md

| # | Decision | Recommendation |
|---|---|---|
| D1 | Fix §3.6 SEC formulas with /36 | Accept — one-line fix |
| D2 | Move default away from pinch, or move warning threshold | Accept one of the three options in §2.2; record which |
| D3 | k constant vs k(Q) | Accept constant for M3, with bias note; revisit if time allows |
| D4 | Fill $/vessel and $/kW defaults before M4 | Accept — required for M4 hand calc |
| D5 | SEC ≥ SEC_min test tolerance | Accept — add explicit tolerance |
| D6 | Convergence check on drag vs on release | Accept on-release / async |

## 6. What this critique does not cover

No code was written or run beyond the independent re-derivations in §1. Sources in §4 were not re-checked against primary literature — the `sources-checklist.md` sign-off remains the user's job, as the plan states. The YouTube / transcript sections (§8) are out of scope for this critique.
