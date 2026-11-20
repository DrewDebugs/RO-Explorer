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

## Comparison with another AI model

The plan suggested that the user may also compare against an implementation written by a
different AI model. That comparison is for the user to add here.
