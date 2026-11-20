"""M5: compare the browser solver (ro_model) with the independent SciPy implementation."""

import math
from dataclasses import asdict, replace

import numpy as np
import pytest

import ro_model as m
import reference_impl as ref

BASE = m.VesselInputs()
CASES = {
    "seawater default": BASE,
    "seawater Pitzer": replace(BASE, model="pitzer"),
    "brackish": replace(BASE, C_f=3.0, P_f=15e5, A25=m.lmh_per_bar_to_si(5.0),
                        B25=float(m.lmh_to_m_per_s(0.3))),
    "strong polarisation": replace(BASE, k=float(m.lmh_to_m_per_s(40.0)), P_f=70e5),
    "warm, no pressure drop": replace(BASE, T=m.celsius_to_kelvin(35.0), dP_drop=0.0),
    "near pinch": replace(BASE, P_f=45e5, Q_f=4 / 3600),
}
FIELDS = ["Q", "C_b", "P", "Q_p", "J_w", "C_p"]


def max_rel_diff(a, b):
    a, b = np.asarray(a), np.asarray(b)
    scale = np.maximum(np.abs(b), 1e-300)
    return float(np.max(np.abs(a - b) / scale))


def compare(inp, rtol=1e-4):
    main = m.simulate_vessel(inp, rtol=rtol)
    r = ref.solve_vessel(asdict(inp), main.x)
    diffs = {f: max_rel_diff(getattr(main, f), r[f]) for f in FIELDS}
    return main, r, diffs


@pytest.mark.parametrize("name", list(CASES))
def test_profiles_agree_with_reference(name, record_property):
    main, r, diffs = compare(CASES[name])
    record_property("max_rel_diff", diffs)
    record_property("N", main.N)
    assert max(diffs.values()) < 1e-5, diffs


@pytest.mark.parametrize("name", ["seawater default", "near pinch"])
def test_tight_tolerance_agreement(name, record_property):
    """With a tighter convergence tolerance the two agree far more closely."""
    main, r, diffs = compare(CASES[name], rtol=1e-8)
    record_property("max_rel_diff", diffs)
    assert max(diffs.values()) < 1e-8, diffs


def test_ideal_case_closed_form(record_property):
    inp = replace(BASE, B25=0.0, k=math.inf, dP_drop=0.0)
    main = m.simulate_vessel(inp)
    exact = ref.ideal_vessel_analytic(asdict(inp), main.x)
    num = ref.solve_vessel(asdict(inp), main.x)["Q"]
    d_main, d_ref = max_rel_diff(main.Q, exact), max_rel_diff(num, exact)
    record_property("main_vs_exact", d_main)
    record_property("scipy_vs_exact", d_ref)
    assert d_main < 1e-6 and d_ref < 1e-9


def test_reference_pi_matches():
    for c in (0.0, 3.0, 35.0, 70.0):
        for pz in (False, True):
            assert ref.osmotic_pressure(c, 298.15, pz) == pytest.approx(
                float(m.osmotic_pressure(c, 298.15, "pitzer" if pz else "vant_hoff")), rel=1e-13)
