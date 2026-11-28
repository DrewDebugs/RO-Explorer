# Comparison of two implementations

The plan (§0 “Still open”, M5) called for a second, independent implementation of
the model to check the one that runs in the browser. This file records how the two
were built and how closely they agree. The tests that produce these numbers are in
[`tests/test_reference.py`](../../tests/test_reference.py) and run in CI on every push.

## The two implementations

| | Browser solver: `ro_model.py` | Reference: `tests/reference_impl.py` |
|---|---|---|
| Runs in | Pyodide (browser) and CPython (tests) | CPython only (needs SciPy) |
| Dependencies | numpy | numpy, SciPy |
| Osmotic pressure | Own code (`_pi_scalar`) | Re-implemented separately from the same equations |
| Local membrane problem | Closed-form C_p, C_m for a given flux + hand-written Illinois root finder | Same closed form, root found with `scipy.optimize.brentq` |
| Along the vessel | Classical RK4, fixed uniform steps, step count doubled until results change < 10⁻⁴ | `scipy.integrate.solve_ivp`, DOP853 (8th order, adaptive step), rtol = 10⁻¹² |
| Shared code | — | None: it does not import `ro_model` |

Both were written by Claude (the same AI model) from the equations in the plan, so
this comparison catches coding and numerical errors, not errors in the equations
themselves. The physics is checked separately by the limit tests (r_max, zero-recovery
flux, ideal SEC_min, second-law sweep). For a third check that does not depend on any
numerical method, the reference file also contains a **closed-form solution** of the
ideal case (B = 0, no polarisation, no pressure drop, van’t Hoff), derived by hand:

$$\frac{dQ}{da} = -A\left(\Delta P - \frac{\pi_f Q_f}{Q}\right)
\;\Rightarrow\; Q + K\ln(Q-K) = Q_f + K\ln(Q_f-K) - A\,\Delta P\,a,\qquad K = \frac{\pi_f Q_f}{\Delta P}$$

## Results

Largest relative difference over all grid nodes and all of Q, C_b, P, Q_p, J_w and C_p.
The browser solver uses its normal settings (convergence tolerance 10⁻⁴), and then a
tight tolerance (10⁻⁸).

| Case | Recovery | RK4 steps | Max rel. diff (default) | Max rel. diff (tight) | Largest in |
|---|---|---|---|---|---|
| Seawater default (35 g/L, 60 bar, 12 m³/h, A = 1.4, B = 0.05) | 43.72 % | 100 | 2.8 × 10⁻⁹ | 2.8 × 10⁻⁹ | C_p |
| Seawater, Pitzer | 47.00 % | 100 | 4.2 × 10⁻⁹ | 2.6 × 10⁻¹⁰ | C_p |
| Brackish (3 g/L, 15 bar, A = 5 LMH/bar) | 80.08 % | 100 | 5.3 × 10⁻⁸ | 3.3 × 10⁻⁹ | C_p |
| Strong polarisation (k = 40 LMH, 70 bar) | 38.85 % | 100 | 1.1 × 10⁻¹⁰ | 1.1 × 10⁻¹⁰ | C_p |
| Warm (35 °C), no pressure drop | 45.81 % | 100 | 6.9 × 10⁻⁹ | 4.2 × 10⁻¹⁰ | C_p |
| Near pinch (45 bar, 4 m³/h) | 35.16 % | 100 | 3.3 × 10⁻⁸ | 2.4 × 10⁻⁹ | C_p |

Ideal case against the closed-form solution (feed flow Q along the vessel):

| Solver | Max rel. error vs exact |
|---|---|
| Browser solver (RK4, 100 steps) | 1.4 × 10⁻⁹ |
| SciPy reference (DOP853) | 1.2 × 10⁻¹¹ |

*These numbers were regenerated after the default membrane was refitted to the FilmTec SW30HRLE-440
datasheet (decision D29). The first run, with the original defaults (A = 1.0, B = 0.10 LMH, 9 m³/h), gave
the same picture: 2.8 × 10⁻¹⁰ to 2.0 × 10⁻⁷.*

The plan's target was agreement better than 10⁻⁵. Every case beats it by at least two
orders of magnitude, and the tests enforce < 10⁻⁵ (default) and < 10⁻⁸ (tight).

## Observations

- **The local permeate concentration C_p is always the most sensitive quantity.** It is a
  small number computed from the flux through C_p = B·E·C_b/(J_w + B·E), so small flux
  differences show up most there.
- **The brackish case is the least accurate at default settings (5 × 10⁻⁸).** At 80 %
  recovery the brine concentrates fivefold along the vessel, so the profiles curve more and
  the 10⁻⁴ convergence check stops at a coarser grid. Tightening the tolerance removes the
  difference.
- **Speed is similar in CPython:** roughly 10–35 ms per case for either solver. The hand-written
  solver only needs numpy, which is why it is the one that runs in the browser (SciPy would
  add several MB to the page load).
- Both solvers agree on the pinch behaviour: in the near-pinch case the local flux falls
  to a few percent of its inlet value in both.

## Comparison with a second AI model (Muse)

The course requires implementing the plan with **at least two different AI models**. The comparison
above is between two implementations written by the *same* model (Claude). This section adds an
implementation by a different model, **Muse**, saved verbatim in
[`second-model/ro_model_muse.py`](second-model/ro_model_muse.py), with Muse's own notes
([`second-model/muse-comparison-notes.md`](second-model/muse-comparison-notes.md)).

**How it was made.** The student gave Muse the plan (`01-plan.md`) and the decisions log
(`03-decisions.md`) and asked for an independent numpy-only model. Muse did not see this repo's code,
but the decisions log does contain this repo's defaults, numerical choices (Illinois tolerance,
log-substituted Simpson integral, N = 50 start) and headline results. So Muse's code is independent,
but it was not blind to the design: agreement on the default case is a strong check of the code, not
of the design choices.

**How it was compared.** [`second-model/compare.py`](second-model/compare.py) runs both models on
identical inputs; [`tests/test_second_model.py`](../../tests/test_second_model.py) asserts the results in CI.

### Where the two models agree

| Check | Claude Code | Muse | Difference |
|---|---|---|---|
| π, van’t Hoff (0.5–70 g/L) | 29.69 bar at 35 g/L | 29.69 bar | exact |
| π, Pitzer (0.5–70 g/L) | 27.406 bar at 35 g/L | 27.404 bar | ≤ 1.6 × 10⁻⁴ (water density, below) |
| SEC_min ideal, r = 0.1–0.9 | 1.143 / 1.065 kWh/m³ at r = 0.5 | same | exact (vH), ≤ 4 × 10⁻⁴ (Pitzer) |
| Local solver, 216 van’t Hoff cases (35–70 g/L, 40–80 bar, B = 0–0.5 LMH) | — | — | ≤ 3 × 10⁻¹⁰ |
| Default seawater vessel | 43.723 %, 148.4 mg/L, brine 62.08 g/L, N = 100 | identical | 4 × 10⁻¹² |
| Brackish preset | 65.848 %, 43.1 mg/L | identical | 6 × 10⁻¹² |
| Strong polarisation (k = 40 LMH, 70 bar) | 38.846 % | identical | 1 × 10⁻¹² |
| Pinch preset (site inputs) | 25.748 % | identical | 2 × 10⁻¹¹ |
| Ideal membrane, 10× area, no CP or pressure drop, vs r_max (45/60/80 bar) | ≤ 7 × 10⁻¹¹ | ≤ 7 × 10⁻¹¹ | both reach r_max |
| Water cost at $0.08 / $0.096 per kWh | $0.790 / $0.827 | $0.790 / $0.826 | ≤ 0.1 % |

### Where they differ, and which is right

| Difference | Effect | Verdict |
|---|---|---|
| **Muse never applies the temperature correction** to A and B in its vessel model (the functions exist but are not called) | At 15 °C Muse gives 45.5 % recovery vs 40.4 % here; at 35 °C, 42.0 % vs 44.8 %. Muse's recovery *rises* in cold water, the wrong direction | **Bug in Muse's model.** Cold water makes membranes less permeable (FilmTec TCF < 1 below 25 °C) |
| **Muse assigns the FilmTec TCF constants as 3020 K for water and 2640 K for salt** | Would give a 4 % larger A at 35 °C | **Misreading by Muse.** FilmTec Eq. 16a,b use 2640 K above 25 °C and 3020 K below, for permeability; Eq. 19 applies the same factor to salt passage (verified by the student, S11) |
| Water density in the molality estimate: Muse 1000 kg/m³, here 997.05 | π (Pitzer) differs by ≤ 1.6 × 10⁻⁴; local flux by up to 0.3 % where the net driving pressure is almost zero (70 g/L, 55 bar) | Both are approximations; 997.05 is the density of water at 25 °C. Neither changes any result shown on the site |
| Pinch position: 4.92 m here (interpolated between grid nodes) vs 4.98 m (Muse: first node below 1 % of inlet flux) with the same inputs | 0.06 m, under one grid step (0.07 m) | Definition only. Muse's own pinch preset (3.6 m) used A = 1.4, k = 180 LMH and a 1.5 bar drop, not the site's preset (A = 1.0, k = 2000 LMH, no drop) |

### What the second model caught in this repo

Muse's notes and its audit of the decisions log (kept verbatim in
[`second-model/muse-03-decisions-patched.md`](second-model/muse-03-decisions-patched.md)) found real
issues here as well; they are answered one by one in `03-decisions.md` (M1–M13). Accepted: the molality
error is about 1 %, not 2 %; D12 did not say the r_max check disables polarisation and pressure drop;
D30's $0.79 predates the electricity update ($0.83 now); the default case now shows a polarisation note
(inlet CP 1.21), which D29 did not mention; the 1.42 vs 1.24 LMH/bar gap in D29 needed an explanation.

### Summary

| | Claude Code (Opus 5.5) | Muse |
|---|---|---|
| Scope | Full site: model, page, plots, validation panel, CI, 116 tests | Model and economics only (one file), with a smoke check |
| Physics at 25 °C | Reference | Agrees to 10⁻⁸ or better on every van’t Hoff vessel case; about 10⁻⁴ with Pitzer (water density) |
| Errors found | Wrong molality-error estimate (2 % → 1 %); unclear wording in three decision entries | Temperature correction never applied; TCF constants misassigned |
| Found by | Muse's audit | This comparison |
