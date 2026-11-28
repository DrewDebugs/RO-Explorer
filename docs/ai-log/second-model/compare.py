"""Compare the Claude Code model (ro_model.py) with Muse's independent model (ro_model_muse.py).

Run from the repo root:   python docs/ai-log/second-model/compare.py
The same comparisons are asserted in tests/test_second_model.py, so CI re-checks them.
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(HERE)]

import ro_model as claude  # noqa: E402
import ro_model_muse as muse  # noqa: E402

LMH = 1e-3 / 3600


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def properties():
    rows = []
    for c in (0.5, 3, 35, 70):
        for pz in (False, True):
            a = float(claude.osmotic_pressure(c, model="pitzer" if pz else "vant_hoff"))
            b = muse.osmotic_pressure(c, use_pitzer=pz)
            rows.append((f"pi({c} g/L, {'Pitzer' if pz else 'vH'})", a / 1e5, b / 1e5, rel(b, a)))
    for r in (0.1, 0.5, 0.9):
        for pz in (False, True):
            a = claude.sec_min(35, r, model="pitzer" if pz else "vant_hoff") / 3.6e6
            b = muse.sec_min_ideal(35, r, use_pitzer=pz)
            rows.append((f"SEC_min ideal r={r} {'Pitzer' if pz else 'vH'}", a, b, rel(b, a)))
    return rows


def local_sweep():
    """Local solver over a grid of bulk concentration, pressure and B; returns the worst disagreement."""
    worst = 0.0
    n = 0
    for cb in np.linspace(35, 70, 8):
        for P in np.linspace(40, 80, 9):
            for B_lmh in (0.0, 0.05, 0.5):
                for pz in (False, True):
                    A = 1.4 * LMH / 1e5
                    k = 180 * LMH
                    a = claude.solve_local(float(cb), P * 1e5, A, B_lmh * LMH, k, model="pitzer" if pz else "vant_hoff")
                    b = muse.solve_local(float(cb), P * 1e5, 0.0, A, B_lmh * LMH, k, use_pitzer=pz)
                    if a.J_w == 0 or b["jw_ms"] == 0:
                        assert a.J_w == b["jw_ms"] == 0.0
                        continue
                    worst = max(worst, rel(b["jw_ms"], a.J_w), rel(b["cm_kg_m3"], a.C_m))
                    if a.C_p > 0:
                        worst = max(worst, rel(b["cp_kg_m3"], a.C_p))
                    n += 1
    return worst, n


def vessel(label, ui, muse_kwargs):
    inp = claude.inputs_from_ui(ui)
    a = claude.simulate_vessel(inp)
    b = muse.solve_vessel(**muse_kwargs)
    return (label, a.recovery, b["recovery"], a.C_p_mixed, b["cp_mixed_final"], a.C_b_out, b["brine_kg_m3"], a.N, b["n_steps"])


def vessels():
    base_ui = {}
    base_m = {}
    cases = [
        ("Seawater default", base_ui, base_m),
        ("Seawater, Pitzer", {"pitzer": True}, {"use_pitzer": True}),
        ("Brackish preset", {"C_f": 3, "P_f": 15, "A": 3.0, "B": 0.2},
         {"feed_salinity_g_l": 3.0, "feed_pressure_bar": 15.0, "a_lmh_per_bar": 3.0, "b_lmh": 0.2}),
        ("Strong polarisation (k = 40, 70 bar)", {"k": 40, "P_f": 70}, {"k_lmh": 40.0, "feed_pressure_bar": 70.0}),
        ("No pressure drop", {"pressure_drop_on": False}, {"pressure_drop_bar": 0.0}),
        # The site's pinch preset: A = 1.0, B = 0, k = 2000, no pressure drop
        ("Pinch preset (site inputs)", {"P_f": 40, "Q_f": 2, "A": 1.0, "B": 0, "k": 2000, "pressure_drop_on": False},
         {"feed_pressure_bar": 40.0, "feed_flow_m3_h": 2.0, "a_lmh_per_bar": 1.0, "b_lmh": 0.0, "k_lmh": 2000.0,
          "pressure_drop_bar": 0.0}),
    ]
    return [vessel(*c) for c in cases]


def question_d12():
    """Muse §1: the r_max check. The repo's test uses an ideal membrane, no CP and no pressure drop."""
    out = []
    for P in (45, 60, 80):
        inp = replace(claude.VesselInputs(), B25=0.0, k=math.inf, dP_drop=0.0, P_f=P * 1e5, area_element=409.0)
        r = claude.simulate_vessel(inp).recovery
        m = muse.solve_vessel(feed_pressure_bar=float(P), b_lmh=0.0, k_lmh=1e12, pressure_drop_bar=0.0, elements=70,
                              element_length_m=1.016 / 10)  # same total area and length as 7 x 409 m2
        out.append((P, claude.r_max_ideal(35, P * 1e5), r, m["recovery"]))
    return out


def question_cost():
    """Muse §2: $0.83 vs $0.79 — the repo's value at both electricity prices."""
    import json
    res = {}
    for price in (0.08, 0.096):
        o = json.loads(claude.run_from_ui(json.dumps({"electricity_price": price})))
        run = muse.solve_vessel()
        sec = muse.sec_with_erd(60.0, run["recovery"])
        e = muse.economics(run, sec, electricity_usd_per_kwh=price)
        res[price] = (o["economics"]["total"], e["water_cost_usd_per_m3"])
    return res


def question_cp():
    r = claude.simulate_vessel(claude.VesselInputs())
    w = [t for lv, t in claude.check_warnings(claude.VesselInputs(), r) if "polarisation" in t]
    return float(r.cp_factor[0]), w


def question_pinch():
    ui = {"P_f": 40, "Q_f": 2, "A": 1.0, "B": 0, "k": 2000, "pressure_drop_on": False}
    a = claude.simulate_vessel(claude.inputs_from_ui(ui))
    b_site = muse.solve_vessel(feed_pressure_bar=40.0, feed_flow_m3_h=2.0, a_lmh_per_bar=1.0, b_lmh=0.0, k_lmh=2000.0,
                               pressure_drop_bar=0.0)
    b_muse = muse.solve_vessel(**{**muse.PRESETS["pinch"]})
    return a.x_pinch, b_site["x_pinch_m"], b_muse["x_pinch_m"]


def tcf_difference():
    rows = []
    for T in (15, 25, 35):
        Tk = T + 273.15
        rows.append((T, float(claude.temperature_correction_factor(Tk)), muse.tcf_water(Tk), muse.tcf_salt(Tk)))
    return rows


if __name__ == "__main__":
    print("== Properties ==")
    for name, a, b, d in properties():
        print(f"{name:32s} Claude {a:10.5f}  Muse {b:10.5f}  rel diff {d:.1e}")
    w, n = local_sweep()
    print(f"\n== Local solver: {n} cases, worst relative difference in J_w, C_m, C_p = {w:.1e}")
    print("\n== Vessel (recovery, permeate mg/L, brine g/L, N) ==")
    for lab, ra, rb, ca, cb, ba, bb, na, nb in vessels():
        print(f"{lab:38s} r {100*ra:7.3f} / {100*rb:7.3f} %   Cp {1000*ca:6.1f} / {1000*cb:6.1f}   brine {ba:6.2f} / {bb:6.2f}   N {na}/{nb}   rel diff r {rel(rb, ra):.1e}")
    print("\n== Muse Q1 (D12): ideal membrane, no CP, no pressure drop, 10x area ==")
    for P, rm, ra, rb in question_d12():
        print(f"{P} bar: r_max {rm:.7f}  Claude {ra:.7f} (diff {abs(ra-rm):.1e})  Muse {rb:.7f} (diff {abs(rb-rm):.1e})")
    print("\n== Muse Q2: water cost ($/m3) Claude / Muse ==")
    for p, (a, b) in question_cost().items():
        print(f"electricity ${p}/kWh: {a:.3f} / {b:.3f}")
    cp0, warn = question_cp()
    print(f"\n== Muse Q3: inlet CP {cp0:.3f}; repo warning: {warn}")
    a, bs, bm = question_pinch()
    print(f"\n== Muse Q4: pinch x — Claude (site preset) {a:.3f} m; Muse with site inputs {bs} m; Muse's own preset {bm} m")
    print("\n== TCF (Claude one constant per T range; Muse 3020 for A, 2640 for B) ==")
    for T, c, mw, ms in tcf_difference():
        print(f"{T} C: Claude {c:.4f}   Muse A {mw:.4f}   Muse B {ms:.4f}")
