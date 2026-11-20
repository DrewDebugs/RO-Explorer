"""M2 tests: the local solution-diffusion + film model."""

import math

import numpy as np
import pytest
from scipy.optimize import brentq

import ro_model as m

A = m.lmh_per_bar_to_si(1.0)
B = float(m.lmh_to_m_per_s(0.1))
K = float(m.lmh_to_m_per_s(180.0))
C_SEA = 35.0
PI_F = float(m.osmotic_pressure(C_SEA))


def test_scalar_pi_matches_numpy():
    c = np.linspace(0, 120, 61)
    for T in (278.15, 298.15, 313.15):
        assert np.allclose([m._pi_scalar(x, T, False) for x in c], m.osmotic_pressure(c, T), rtol=1e-14)
        assert np.allclose([m._pi_scalar(x, T, True) for x in c],
                           m.osmotic_pressure(c, T, "pitzer"), rtol=1e-13)


def test_closed_form_satisfies_the_three_equations():
    J = float(m.lmh_to_m_per_s(20.0))
    C_p, C_m = m.local_concentrations(J, C_SEA, B, K)
    assert C_p == pytest.approx(B * (C_m - C_p) / J, rel=1e-13)  # C_p = J_s / J_w
    assert C_m == pytest.approx(C_p + (C_SEA - C_p) * math.exp(J / K), rel=1e-13)  # film


def test_no_polarisation_when_k_infinite():
    s = m.solve_local(C_SEA, 60e5, A, B, math.inf)
    assert s.C_m == pytest.approx(C_SEA, rel=1e-14)
    s2 = m.solve_local(C_SEA, 60e5, A, B, m.lmh_to_m_per_s(1e7))
    assert s2.C_m / C_SEA == pytest.approx(1.0, abs=1e-5)


def test_zero_recovery_limit_ideal_membrane():
    """k -> inf, B = 0: J_w = A (dP - pi_f) exactly."""
    for dP in (35e5, 60e5, 80e5):
        s = m.solve_local(C_SEA, dP, A, 0.0, math.inf)
        assert s.J_w == pytest.approx(A * (dP - PI_F), rel=1e-9)
        assert s.C_p == 0.0


def test_ideal_membrane_below_osmotic_pressure_gives_zero_flux():
    for dP in (0.0, 10e5, PI_F, PI_F * 0.999):
        s = m.solve_local(C_SEA, dP, A, 0.0, K)
        assert s.J_w == 0.0


def test_leaky_membrane_below_osmotic_pressure():
    """B > 0: flux never quite stops, but rejection collapses as NDP -> 0."""
    low = m.solve_local(C_SEA, 0.5 * PI_F, A, B, K)
    high = m.solve_local(C_SEA, 60e5, A, B, K)
    assert low.J_w > 0
    # flux ~ 0.1 LMH, comparable to B, so about half the salt passes
    assert 1 - low.C_p / C_SEA < 0.6
    assert 1 - high.C_p / C_SEA > 0.98


def test_zero_concentration():
    s = m.solve_local(0.0, 10e5, A, B, K)
    assert s.J_w == pytest.approx(A * 10e5, rel=1e-15)


def _brentq_flux(C_b, dP, A_, B_, k_, model):
    pitzer = model == "pitzer"

    def f(J):
        C_p, C_m = m.local_concentrations(J, C_b, B_, k_)
        return J - A_ * (dP - m._pi_scalar(C_m, 298.15, pitzer) + m._pi_scalar(C_p, 298.15, pitzer))

    return brentq(f, 1e-300, A_ * dP, xtol=1e-30, rtol=1e-15, maxiter=500)


def test_matches_brentq_random():
    rng = np.random.default_rng(42)
    for _ in range(300):
        C_b = rng.uniform(0.5, 100)
        dP = rng.uniform(5, 85) * 1e5
        A_ = m.lmh_per_bar_to_si(rng.uniform(0.3, 10))
        B_ = float(m.lmh_to_m_per_s(rng.uniform(0.001, 1)))
        k_ = float(m.lmh_to_m_per_s(rng.uniform(20, 2000)))
        model = rng.choice(["vant_hoff", "pitzer"])
        s = m.solve_local(C_b, dP, A_, B_, k_, model=model)
        assert s.iterations < 100
        assert s.J_w == pytest.approx(_brentq_flux(C_b, dP, A_, B_, k_, model), rel=1e-10)
        assert s.C_p <= C_b <= s.C_m * (1 + 1e-14)


def test_flux_and_rejection_increase_with_pressure():
    dPs = np.linspace(5, 85, 33) * 1e5
    sols = [m.solve_local(C_SEA, p, A, B, K) for p in dPs]
    J = np.array([s.J_w for s in sols])
    R = np.array([1 - s.C_p / C_SEA for s in sols])
    assert np.all(np.diff(J) > 0)
    assert np.all(np.diff(R) > 0)


def test_unknown_model():
    with pytest.raises(ValueError):
        m.solve_local(C_SEA, 60e5, A, B, K, model="ideal")
