# Comparison notes — Muse independent `ro_model.py` vs Claude Code implementation

**Date:** 2026-11-27
**Muse file:** `ro_model.py` (independent re-implementation from `01-plan.md` §3 only, no SciPy, numpy only)
**Reference:** DrewDebugs/RO-Explorer, decisions in `03-decisions.md` (patched copy: `03-decisions-patched.md`)

Run the Muse file with `python ro_model.py`. It prints the default case.

## Agreement — verified independently, same numbers

| Check | Plan / decisions | Muse `ro_model.py` |
|---|---|---|
| π van't Hoff, 35 g/L | 29.7 bar | 29.69 bar |
| π Pitzer, 35 g/L | 27.4 bar, φ ≈ 0.92 | 27.40 bar, φ(0.6 mol/kg) = 0.923 |
| SEC_min ideal, r = 0.5, vH | 1.14 kWh/m³ | 1.143 kWh/m³ |
| SEC_min ideal, r = 0.5, Pitzer | 1.06 kWh/m³ | 1.065 kWh/m³ |
| r_max ideal, 60 bar | 0.505 | 0.505 |
| Default vessel (A=1.4, B=0.05, feed 12 m³/h) | recovery 43.7%, Cp 148 mg/L, SEC 2.28 kWh/m³ with ERD | **43.7%, 148 mg/L, 2.28 kWh/m³** — exact match |
| Brackish preset (A=3, B=0.2, 12 m³/h) | 66% recovery | 65.8% |
| CAPEX | $1,439 per m³/d | $1,438 per m³/d |
| Water + salt balances, default run | — | relative error ~1e-16 |
| SEC ≥ SEC_min (actual) | SEC 2.28 > SEC_min 1.06 | 2.28 > 1.06 |
| RK4 convergence | default converges N=100 | recovery identical to 6 dp at N=50, 100, 200, 400; error at N=50 ~3e-9 relative |

## Differences to check in the Claude Code implementation

### 1. D12 — r_max test at 10× area (main discrepancy)
Muse cannot reproduce “10× normal area recovery matches r_max to <1e-6”.
- With default k = 180 LMH and 1.5 bar pressure drop, the A→∞ asymptote is **0.4959**, not 0.505 — concentration polarisation caps local flux at Jw ≈ k·ln(ΔP/π_b), so recovery saturates 0.009 below r_max.
- 10× area (70 elements, B=0): Muse gives 0.5016, diff 0.0035. 100× area: diff 0.00046.
- With CP and pressure drop both disabled, 70 elements gives 0.5051135 vs r_max 0.5051135 — matches to <1e-6.
- **Question for Claude Code:** does the D12 test disable CP and/or pressure drop, or use a different r_max definition? If it runs with default k and ΔP, the <1e-6 claim should not hold — check the test's setup, not just its pass/fail.

### 2. Water cost $0.83 vs $0.79
Muse economics gives **$0.83/m³**; D30 says $0.79/m³. CAPEX matches ($1,438 vs $1,439), so the gap is in the per-m³ denominator, not the plant cost.
- Muse divides annualised CAPEX, fixed O&M, membrane replacement and electricity all by annual water = capacity × 365 × availability (0.95).
- $0.79 is reproduced if annualised CAPEX and fixed O&M are divided by full capacity (availability = 1 in the denominator) while electricity stays per-m³.
- **Question:** which denominator does the repo use, and is availability applied consistently? Either is defensible, but it must be stated.

### 3. Inlet CP factor 1.207 at the new default
With A = 1.4, inlet Jw = 33.9 LMH, k = 180 LMH, CP = exp(33.9/180) = **1.207** — just above the plan §3.1 guideline CP ≤ 1.2. The old default (A = 1.0) gave 1.18. The decisions log does not mention this after D29. Probably fine, but the >1.2 warning (D15, CP > 1.2) may now fire at the inlet by default — check whether the repo's warning uses inlet CP or a vessel-average.

### 4. Pinch demo x_pinch depends on A and on the definition
- Muse, pinch preset (B=0, 40 bar, 2 m³/h): A=1.0 → x_pinch 4.52 m; A=1.4 → 3.59 m (definition: first x with Jw < 1% of inlet Jw). D23 says ~4.9 m.
- The difference is consistent with a different A (1.0 vs 1.4) and/or a different pinch threshold. Check the repo preset's A value and its pinch definition before calling this a mismatch.

## Deliberate implementation differences (not discrepancies)

- **Local solver:** Illinois (modified regula falsi) with forced bisection after 2 non-halving steps, tolerance |f| ≤ 1e-16 m/s (D9). No SciPy `brentq` in this file — the cross-check in the repo should be `brentq` vs this Illinois solver on the same inputs.
- **SEC_min, Pitzer:** Simpson in u = −ln(1−r′), n = 128 (D7). Van't Hoff uses the analytic form.
- **SEC_min, actual (leaky):** free-energy density f(c) = c·∫π(c′)/c′² dc′, evaluated in u = ln(c′) with Simpson n = 200, c_ref = 1 mol/m³ (cancels by salt balance).
- **TCF:** A uses 3020 K, B uses 2640 K (FilmTec design equations). The repo should confirm which constant it uses for each — the plan only gave the 2640–3020 K range.
- **Economics:** multiplier 12.5 is labelled calibrated, not verified (see patched D30). Same numbers as the repo, different claim about what they prove.
- **Molality:** error corrected to ~1% at 35 g/L (true 0.605 vs approx. 0.599 mol/kg), not ~2% (patched D6).

## What to run for a direct comparison

1. Same inputs, same outputs: default vessel, brackish preset, pinch preset, Pitzer on/off — compare recovery, Cp, brine, SEC, SEC_min (ideal and actual), x_pinch, N at convergence.
2. Local solver: sweep Cb = 35–70 g/L, P = 40–80 bar, B = 0 and 0.05 — compare Jw, Cp, Cm to 1e-9 relative.
3. Edge cases: B = 0 at ΔP ≤ π(Cb) (exact pinch, Jw = 0); tiny area (recovery ~1e-6); 10× area with CP on vs off (see §1 above).
