"""Validation checks shared by pytest (CI) and the page's "re-run in your browser" button.

Each check runs the model against something known independently (a unit
identity, a published value, a limiting case with an exact answer, a
conservation law or the second law) and returns a dict:

    {"id", "title", "category", "expected", "measured", "passed", "values"}

`expected` and `measured` are short human-readable strings for the page;
`values` holds the raw numbers. Only numpy and ro_model are used, so every
check also runs in Pyodide. `fast=True` shrinks the random sweep for the browser.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace

import numpy as np

import ro_model as m

CHECKS = []


def check(check_id, title, category):
    def deco(fn):
        CHECKS.append((check_id, title, category, fn))
        return fn
    return deco


def _result(passed, expected, measured, **values):
    return {"passed": bool(passed), "expected": expected, "measured": measured,
            "values": {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                       for k, v in values.items()}}


BASE = m.VesselInputs()
IDEAL = replace(BASE, B25=0.0, k=math.inf, dP_drop=0.0)


# ------------------------------------------------------------------ properties


@check("V01", "Unit conversions: 1 bar on 1 m³ = 1/36 kWh; 1 LMH = 2.7778×10⁻⁷ m/s", "Units")
def v_units(fast):
    e = float(m.j_per_m3_to_kwh_per_m3(m.bar_to_pa(1.0)))
    j = float(m.lmh_to_m_per_s(1.0))
    rt = float(m.si_to_lmh_per_bar(m.lmh_per_bar_to_si(1.234)))
    ok = abs(e * 36 - 1) < 1e-14 and abs(j / 2.7777777777777776e-7 - 1) < 1e-14 and abs(rt - 1.234) < 1e-14
    return _result(ok, "1/36 = 0.027778 kWh/m³", f"{e:.6f} kWh/m³", kwh_per_bar=e, lmh_si=j)


@check("V02", "van’t Hoff osmotic pressure of 35 g/L NaCl at 25 °C", "Properties")
def v_pi_vh(fast):
    p = float(m.pa_to_bar(m.osmotic_pressure(35.0)))
    return _result(abs(p - 29.7) < 0.05, "29.7 bar (2·C/M·RT)", f"{p:.2f} bar", pi_bar=p)


@check("V03", "Pitzer osmotic coefficient vs tabulated NaCl data, 0.1–3 mol/kg", "Properties")
def v_pitzer(fast):
    table = {0.1: 0.932, 0.5: 0.921, 1.0: 0.936, 2.0: 0.983, 3.0: 1.045}  # Robinson & Stokes 1949; verified by the student (S6)
    dev = max(abs(float(m.osmotic_coefficient_pitzer(k)) - v) for k, v in table.items())
    return _result(dev < 0.003, "|Δφ| < 0.003", f"max |Δφ| = {dev:.4f}", max_abs_dev=dev)


@check("V04", "SEC_min: numerical integral equals the analytic van’t Hoff formula", "Energy")
def v_secmin(fast):
    rs = [0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95]
    err = max(abs(m.sec_min(35.0, r) / float(m.sec_min_vant_hoff(35.0, r)) - 1) for r in rs)
    return _result(err < 1e-8, "rel. error < 10⁻⁸", f"{err:.1e}", max_rel_err=err)


@check("V05", "Minimum energy, 35 g/L at 50 % recovery (Elimelech & Phillip 2011: 1.06 kWh/m³)", "Energy")
def v_secmin_lit(fast):
    vh = float(m.j_per_m3_to_kwh_per_m3(m.sec_min(35.0, 0.5)))
    pz = float(m.j_per_m3_to_kwh_per_m3(m.sec_min(35.0, 0.5, model="pitzer")))
    return _result(abs(pz / 1.06 - 1) < 0.02, "1.06 kWh/m³ (± 2 %)",
                   f"Pitzer {pz:.3f}, van’t Hoff {vh:.3f} kWh/m³", pitzer=pz, vant_hoff=vh)


# ------------------------------------------------------------------ local model


@check("V06", "Local flux, ideal membrane without polarisation: J = A(ΔP − π_f)", "Local model")
def v_local_limit(fast):
    A = m.lmh_per_bar_to_si(1.0)
    pi_f = float(m.osmotic_pressure(35.0))
    err = max(abs(m.solve_local(35.0, dP, A, 0.0, math.inf).J_w / (A * (dP - pi_f)) - 1)
              for dP in (35e5, 60e5, 80e5))
    return _result(err < 1e-9, "rel. error < 10⁻⁹", f"{err:.1e}", max_rel_err=err)


@check("V07", "Ideal membrane below the osmotic pressure: zero flux (the pinch)", "Local model")
def v_local_pinch(fast):
    A, k = m.lmh_per_bar_to_si(1.0), float(m.lmh_to_m_per_s(180))
    J = max(m.solve_local(35.0, dP, A, 0.0, k).J_w for dP in (10e5, 25e5, 29.6e5))
    return _result(J == 0.0, "J_w = 0 exactly", f"max J_w = {J:g} m/s", max_flux=J)


@check("V08", "Polarisation vanishes as k → ∞ (C_m/C_b → 1)", "Local model")
def v_local_cp(fast):
    A, B = m.lmh_per_bar_to_si(1.0), float(m.lmh_to_m_per_s(0.1))
    cps = [m.solve_local(35.0, 60e5, A, B, float(m.lmh_to_m_per_s(k))).C_m / 35.0 for k in (180, 1e3, 1e5, 1e7)]
    ok = all(np.diff(cps) < 0) and abs(cps[-1] - 1) < 1e-5
    return _result(ok, "decreasing to 1", " → ".join(f"{c:.6f}" for c in cps), cp_factors=cps)


# ------------------------------------------------------------------ vessel model


@check("V09", "Water and salt mass balances close over the vessel", "Vessel model")
def v_balance(fast):
    r = m.simulate_vessel(BASE)
    ew = abs((r.Q[-1] + r.Q_p[-1]) / BASE.Q_f - 1)
    es = abs((r.Q[-1] * r.C_b[-1] + r.S_p[-1]) / (BASE.Q_f * BASE.C_f) - 1)
    return _result(max(ew, es) < 1e-6, "closure < 10⁻⁶", f"water {ew:.1e}, salt {es:.1e}",
                   water=ew, salt=es)


@check("V10", "RK4 grid convergence: observed order ≈ 4", "Vessel model")
def v_order(fast):
    ref = m.simulate_vessel(BASE, N=1024, fixed_N=True).recovery
    errs = [abs(m.simulate_vessel(BASE, N=n, fixed_N=True).recovery - ref) for n in (2, 4, 8)]
    orders = [math.log2(errs[i] / errs[i + 1]) for i in range(2)]
    return _result(all(3.5 < p < 4.5 for p in orders), "3.5 – 4.5",
                   ", ".join(f"{p:.2f}" for p in orders), orders=orders)


@check("V11", "Recovery limit: ideal membrane + large area → r_max = 1 − π_f/ΔP", "Vessel model")
def v_rmax(fast):
    errs = []
    for P in (45e5, 60e5, 80e5):
        res = m.simulate_vessel(replace(IDEAL, P_f=P, area_element=409.0))
        errs.append(abs(res.recovery - m.r_max_ideal(35.0, P)))
    return _result(max(errs) < 1e-3, "|r − r_max| < 10⁻³", f"max {max(errs):.1e}", max_abs_err=max(errs))


def _ideal_exact_Q(inp, x):
    """Closed-form feed flow for the ideal case, solved by bisection (no SciPy)."""
    A, dP = inp.A, inp.P_f - inp.P_p
    W = inp.area / inp.length
    K = float(m.osmotic_pressure(inp.C_f, inp.T)) * inp.Q_f / dP
    target = inp.Q_f + K * math.log(inp.Q_f - K) - A * dP * W * x
    lo, hi = K * (1 + 1e-15), inp.Q_f
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid + K * math.log(mid - K) > target:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


@check("V12", "Ideal vessel vs closed-form solution Q + K ln(Q − K) = const − AΔP·a", "Vessel model")
def v_exact(fast):
    res = m.simulate_vessel(IDEAL)
    err = max(abs(q / _ideal_exact_Q(IDEAL, x) - 1) for x, q in zip(res.x, res.Q))
    return _result(err < 1e-6, "rel. error < 10⁻⁶", f"{err:.1e}", max_rel_err=err)


@check("V13", "Higher feed pressure gives higher recovery", "Vessel model")
def v_monotonic(fast):
    P = np.linspace(35, 80, 6 if fast else 10)
    rec = [m.simulate_vessel(replace(BASE, P_f=p * 1e5)).recovery for p in P]
    return _result(all(np.diff(rec) > 0), "strictly increasing",
                   f"{100*rec[0]:.1f} % → {100*rec[-1]:.1f} %", recovery=rec)


# ------------------------------------------------------------------ energy & cost


@check("V14", "Second law: SEC ≥ minimum work for the actual separation (random cases)", "Energy")
def v_second_law(fast):
    rng = np.random.default_rng(2026)
    n = 60 if fast else 500
    worst, checked = math.inf, 0
    for _ in range(n):
        inp = m.VesselInputs(
            C_f=rng.uniform(0.5, 70), P_f=rng.uniform(5, 85) * 1e5, Q_f=rng.uniform(2, 16) / 3600,
            T=rng.uniform(278.15, 313.15), A25=m.lmh_per_bar_to_si(rng.uniform(0.3, 10)),
            B25=float(m.lmh_to_m_per_s(rng.uniform(0, 1))) if rng.random() > 0.1 else 0.0,
            k=float(m.lmh_to_m_per_s(rng.uniform(20, 2000))), n_elements=int(rng.integers(1, 9)),
            dP_drop=rng.uniform(0, 5) * 1e5, model=str(rng.choice(["vant_hoff", "pitzer"])))
        res = m.simulate_vessel(inp, N=40, fixed_N=True)
        r = res.recovery
        if not 1e-6 < r < 0.999:
            continue
        sec = m.sec_erd(inp.P_f, res.P_out, r, 1.0, 1.0)  # perfect pump and ERD
        bound = m.sec_min_actual(inp.C_f, res.C_p_mixed, res.C_b_out, r, inp.T, inp.model)
        worst = min(worst, sec / bound)
        checked += 1
    return _result(worst >= 1 - 1e-9, "SEC / SEC_min ≥ 1 in every case",
                   f"min ratio {worst:.3f} over {checked} cases", min_ratio=worst, cases=checked)


@check("V15", "Energy recovery device lowers SEC", "Energy")
def v_erd(fast):
    r = m.simulate_vessel(BASE)
    a = m.sec_pump(BASE.P_f, r.recovery, 0.8) / m.J_PER_KWH
    b = m.sec_erd(BASE.P_f, r.P_out, r.recovery, 0.8, 0.95) / m.J_PER_KWH
    return _result(b < a, "SEC with ERD < without", f"{b:.2f} < {a:.2f} kWh/m³", erd=b, no_erd=a)


@check("V16", "Water cost matches a hand calculation", "Economics")
def v_cost(fast):
    eco = m.EconomicsInputs(capacity=10_000, availability=0.9, electricity_price=0.10,
                            membrane_cost=500, vessel_cost=1000, pump_erd_cost=1000,
                            other_multiplier=5, interest=0.0, plant_life=20, membrane_life=5,
                            om_fraction=0.02)
    out = m.water_cost(3.0, 4.0, 7, eco)
    annual = 10_000 * 365 * 0.9
    hand = 8_612_500 / 20 / annual + 0.30 + 367_500 / 5 / annual + 0.02 * 8_612_500 / annual
    return _result(abs(out["total"] / hand - 1) < 1e-12, f"{hand:.6f} $/m³",
                   f"{out['total']:.6f} $/m³", model=out["total"], hand=hand)


# ------------------------------------------------------------------ runner


def run_all(fast=False):
    results = []
    for cid, title, cat, fn in CHECKS:
        try:
            r = fn(fast)
        except Exception as exc:  # report, don't crash the page
            r = _result(False, "", f"error: {exc!r}")
        results.append({"id": cid, "title": title, "category": cat, **r})
    return results


def run_all_json(fast=True):
    return json.dumps(run_all(fast))
