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
| D9 | §3.3 solver tolerance | Illinois, tolerance \|f\| < 10⁻¹² m/s | Tolerance \|f\| ≤ 10⁻¹⁶ m/s (or a bracket of a few ulp), plus a forced bisection step whenever the bracket fails to halve in two iterations | 10⁻¹² m/s is ~10⁻⁶ of a typical flux, too loose for the 4th-order convergence test and the 10⁻¹⁰ brentq comparison. The tighter tolerance costs ~2 extra iterations | M2 |
| D10 | §3.4 discretization | Default N = 200, doubled until the change is < 10⁻⁴ | Start at N = 50; compare N and 2N and double until the change is < 10⁻⁴ (max 3200). The default case converges at N = 100 | The check guarantees accuracy, so a smaller start is just faster (important in the browser) | M3 |
| D11 | §5 M3 test “higher P → higher rejection” | Monotonic in P over a sweep | Holds **locally** (tested) and at the vessel level at low recovery (16 m³/h feed). At the default 9 m³/h, observed rejection **peaks near 70 bar and then falls** | Found by the test. More pressure → more recovery → saltier brine at the vessel end → saltier mixed permeate. Kept as a teaching point instead of hiding it | M3 |
| D12 | §5 M3 r_max test | “large area → r → 1 − π_f/ΔP within 10⁻³” | 10× the normal area. Recovery matches r_max to < 10⁻⁶ at 45, 60 and 80 bar | With 1000× area the whole approach to the pinch happens in the first millimetres, which a uniform RK4 grid can't resolve (it overshot r_max by 1.6×10⁻⁴) | M3 |
| D13 | §5 M2 zero-recovery limit | J_w = A(ΔP − π_f) to 10⁻⁹ | Exact to 10⁻⁹ in the **local** solver. At the vessel level (area 10⁻⁶ m²) agreement is 10⁻⁸ | The tiny vessel still has recovery ~3×10⁻⁹, which shifts π_b by about that much | M3 |
| D14 | §3.4, §3.6 | Pressures not specified as gauge or absolute | All pressures are gauge; the permeate is at atmospheric pressure (0 gauge); the pump lifts feed from 0 to P_f | Matches how feed pressure is quoted in practice | M3 |
| D15 | §3.5 warnings | Four warnings | Added: recovery > 95 % (model breaks down), CP factor above the ~1.2 guideline, grid not converged. Brine threshold set to 70 g/L (TODO-VERIFY) | Extreme brackish settings can recover > 99 % of the feed, where the model is no longer meaningful | M3 |
| D16 | §3.7 economics defaults | Inputs listed, values not given for vessels, pumps, multiplier, O&M | $1,500/vessel, $1,000/kW pump + ERD, “other plant” multiplier 7, fixed O&M 2 %/yr, membrane life 5 yr (all **TODO-VERIFY**). Defaults give CAPEX ≈ $1,080 per m³/d and ≈ $0.56/m³ | The multiplier was chosen so total CAPEX per m³/d lands in the range quoted for large SWRO plants; to be checked against the cited range in M7 | M4 |
| D17 | §3.6 energy | Booster pump ignored | As planned. SEC counts only the high-pressure RO pumps (no intake, pretreatment or post-treatment energy) | Stated on the page; plant-wide SEC is higher | M4 |

## Critique: accept / reject

*(Filled in after `02-critique.md` is added.)*

| # | Critique point | Accepted? | Action / reason |
|---|---|---|---|
