"""M3 tests: the 1D pressure-vessel model."""

import math
from dataclasses import replace

import numpy as np
import pytest

import ro_model as m

BASE = m.VesselInputs()
IDEAL = replace(BASE, B25=0.0, k=math.inf, dP_drop=0.0)


@pytest.fixture(scope="module")
def base_result():
    return m.simulate_vessel(BASE)


def test_default_case_is_reasonable(base_result):
    r = base_result
    assert r.converged
    assert 0.40 <= r.recovery <= 0.47
    assert r.rejection > 0.98
    assert r.x_pinch is None


def test_mass_balance(base_result):
    r = base_result
    Q_out, S_out = r.Q[-1], r.C_b[-1] * r.Q[-1]
    assert (Q_out + r.Q_p[-1]) / BASE.Q_f == pytest.approx(1.0, abs=1e-12)
    assert (S_out + r.S_p[-1]) / (BASE.Q_f * BASE.C_f) == pytest.approx(1.0, abs=1e-12)


def test_permeate_equals_integrated_local_flux():
    """Q_p from the ODE equals the integral of J_w W dx over the profile nodes."""
    res = m.simulate_vessel(BASE, N=400, fixed_N=True)
    W = BASE.area / BASE.length
    h = res.x[1] - res.x[0]
    J = res.J_w
    simpson = h / 3 * (J[0] + J[-1] + 4 * J[1:-1:2].sum() + 2 * J[2:-1:2].sum())
    assert simpson * W == pytest.approx(res.Q_p[-1], rel=1e-8)


def test_grid_convergence_order_is_four():
    ref = m.simulate_vessel(BASE, N=2048, fixed_N=True).recovery
    errs = [abs(m.simulate_vessel(BASE, N=n, fixed_N=True).recovery - ref) for n in (4, 8, 16)]
    orders = [math.log2(errs[i] / errs[i + 1]) for i in range(2)]
    assert all(3.5 < p < 4.5 for p in orders), orders


def test_auto_convergence_meets_tolerance(base_result):
    finer = m.simulate_vessel(BASE, N=base_result.N * 4, fixed_N=True)
    assert base_result.recovery == pytest.approx(finer.recovery, rel=1e-4)
    assert base_result.C_p_mixed == pytest.approx(finer.C_p_mixed, rel=1e-4)


def test_r_max_limit_with_large_area():
    """Ideal membrane, no CP, 10x the normal area: recovery -> 1 - pi_f / dP.

    (With 1000x the area the whole approach to the pinch happens within a few
    millimetres, which a uniform grid cannot resolve.)
    """
    for P in (45e5, 60e5, 80e5):
        inp = replace(IDEAL, P_f=P, area_element=40.9 * 10)
        res = m.simulate_vessel(inp)
        r_max = m.r_max_ideal(inp.C_f, P)
        assert r_max == pytest.approx(1 - float(m.osmotic_pressure(inp.C_f)) / P, rel=1e-14)
        assert res.recovery == pytest.approx(r_max, abs=1e-3)
        assert res.recovery <= r_max + 1e-9


def test_tiny_area_gives_local_flux():
    """Area -> 0: average flux = A (dP - pi_f) for an ideal membrane."""
    inp = replace(IDEAL, n_elements=1, area_element=1e-6)
    res = m.simulate_vessel(inp)
    J_avg = res.Q_p[-1] / inp.area
    # recovery ~ 3e-9 shifts pi_b by ~3e-9, so agreement is expected to ~1e-8
    assert J_avg == pytest.approx(inp.A * (inp.P_f - float(m.osmotic_pressure(inp.C_f))), rel=1e-8)


def _sweep(inp, pressures):
    res = [m.simulate_vessel(replace(inp, P_f=P * 1e5)) for P in pressures]
    return np.array([r.recovery for r in res]), np.array([r.rejection for r in res])


def test_pressure_sweep_recovery_monotonic():
    rec, _ = _sweep(BASE, np.linspace(35, 80, 10))
    assert np.all(np.diff(rec) > 0)


def test_pressure_sweep_rejection():
    """At low recovery (16 m^3/h feed) observed rejection rises with pressure.

    At the default 12 m^3/h it peaks near 75 bar and then falls: the extra
    recovery concentrates the brine, and permeate made from it is saltier.
    (The plan expected monotonic rejection at vessel level; see decisions log.)
    """
    P = np.linspace(35, 80, 10)
    _, rej_hi_flow = _sweep(replace(BASE, Q_f=16 / 3600), P)
    assert np.all(np.diff(rej_hi_flow) > 0)
    _, rej = _sweep(BASE, P)
    i = int(np.argmax(rej))
    assert 0 < i < len(P) - 1  # interior maximum


def test_pinch_detected_for_ideal_membrane_at_low_pressure():
    res = m.simulate_vessel(replace(IDEAL, P_f=40e5, Q_f=2 / 3600))
    assert res.x_pinch is not None and 0 < res.x_pinch < BASE.length
    assert res.J_w[-1] < 0.01 * res.J_w[0]
    assert res.recovery == pytest.approx(m.r_max_ideal(35.0, 40e5), abs=1e-3)


def test_profile_sanity(base_result):
    r = base_result
    assert np.all(r.C_p <= r.C_b) and np.all(r.C_b <= r.C_m)
    assert np.all(r.NDP > 0)
    assert np.all(np.diff(r.C_b) > 0)  # brine concentrates along the vessel
    assert np.allclose(r.P, BASE.P_f - BASE.dP_drop * r.x / BASE.length, rtol=1e-12)
    assert np.all(r.cp_factor >= 1)


def test_pitzer_gives_higher_recovery(base_result):
    pz = m.simulate_vessel(replace(BASE, model="pitzer"))
    assert pz.recovery > base_result.recovery


def test_r_max_pitzer_solves_brine_equation():
    r = m.r_max_ideal(35.0, 60e5, model="pitzer")
    assert float(m.osmotic_pressure(35.0 / (1 - r), model="pitzer")) == pytest.approx(60e5, rel=1e-9)
    assert m.r_max_ideal(35.0, 20e5) == 0.0


def test_temperature_raises_permeance():
    warm = replace(BASE, T=m.celsius_to_kelvin(35.0))
    assert warm.A > BASE.A and warm.B > BASE.B
    assert m.simulate_vessel(warm).recovery > m.simulate_vessel(BASE).recovery


def _levels_and_text(inp):
    res = m.simulate_vessel(inp)
    return " | ".join(t for _, t in m.check_warnings(inp, res))


def test_warnings():
    assert "osmotic" in " ".join(t for _, t in m.check_warnings(replace(BASE, P_f=25e5)))
    assert "limit of" in _levels_and_text(replace(BASE, P_f=85e5))
    assert "thermodynamic limit" in _levels_and_text(replace(BASE, Q_f=9 / 3600))  # ~91 % of r_max
    brackish_extreme = replace(BASE, C_f=1.0, P_f=60e5, Q_f=2 / 3600,
                               A25=m.lmh_per_bar_to_si(8.0))
    text = _levels_and_text(brackish_extreme)
    assert "almost all the feed" in text and "teaching threshold" in text
    assert "polarisation" in _levels_and_text(replace(BASE, k=float(m.lmh_to_m_per_s(40.0))))
    assert "Pinch" in _levels_and_text(replace(IDEAL, P_f=40e5, Q_f=2 / 3600))
