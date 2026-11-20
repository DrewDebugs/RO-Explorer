"""M1 tests: units, osmotic pressure, temperature correction, SEC_min."""

import numpy as np
import pytest
from scipy.integrate import quad

import ro_model as m

T25 = m.T_REF
C_SEA = 35.0  # kg/m^3 (= g/L) NaCl


# --------------------------------------------------------------------- units


@pytest.mark.parametrize(
    "fwd, back, x",
    [
        (m.bar_to_pa, m.pa_to_bar, 60.0),
        (m.lmh_to_m_per_s, m.m_per_s_to_lmh, 15.0),
        (m.lmh_per_bar_to_si, m.si_to_lmh_per_bar, 1.2),
        (m.kwh_per_m3_to_j_per_m3, m.j_per_m3_to_kwh_per_m3, 3.0),
    ],
)
def test_unit_round_trip(fwd, back, x):
    assert back(fwd(x)) == pytest.approx(x, rel=1e-14)


def test_unit_values():
    assert m.lmh_to_m_per_s(1.0) == pytest.approx(2.7778e-7, rel=1e-4)
    assert m.lmh_per_bar_to_si(1.0) == pytest.approx(2.7778e-12, rel=1e-4)
    # 1 bar of pressure on 1 m^3 is 1e5 J = 1/36 kWh
    assert m.j_per_m3_to_kwh_per_m3(m.bar_to_pa(1.0)) == pytest.approx(1 / 36, rel=1e-14)
    assert m.celsius_to_kelvin(25.0) == pytest.approx(298.15)


# --------------------------------------------------------- osmotic pressure


def test_vant_hoff_seawater():
    """35 g/L NaCl at 25 degC: pi = 2 * (35/58.44 mol/L) * R T = 29.7 bar."""
    assert m.pa_to_bar(m.osmotic_pressure_vant_hoff(C_SEA, T25)) == pytest.approx(29.7, abs=0.05)


def test_vant_hoff_is_linear_in_c_and_T():
    p = m.osmotic_pressure_vant_hoff
    assert p(70.0, T25) == pytest.approx(2 * p(35.0, T25), rel=1e-14)
    assert p(35.0, 2 * T25) == pytest.approx(2 * p(35.0, T25), rel=1e-14)
    assert p(0.0) == 0.0


def test_pitzer_seawater():
    """Plan section 3.2: phi ~ 0.92 at ~0.6 mol/kg, so pi ~ 27.4 bar."""
    mol = m.molality_estimate(C_SEA)
    assert mol == pytest.approx(0.60, abs=0.005)
    assert m.osmotic_coefficient_pitzer(mol) == pytest.approx(0.923, abs=0.002)
    assert m.pa_to_bar(m.osmotic_pressure_pitzer(C_SEA)) == pytest.approx(27.4, abs=0.05)


# TODO-VERIFY: NaCl osmotic coefficients at 25 degC, Robinson & Stokes,
# "Electrolyte Solutions" (2nd ed., 1959), Appendix 8.10. Listed in
# docs/sources-checklist.md.
ROBINSON_STOKES_PHI = {0.1: 0.932, 0.5: 0.921, 1.0: 0.936, 2.0: 0.983, 3.0: 1.045}


@pytest.mark.parametrize("molality, phi_ref", sorted(ROBINSON_STOKES_PHI.items()))
def test_pitzer_matches_tabulated_osmotic_coefficient(molality, phi_ref):
    assert m.osmotic_coefficient_pitzer(molality) == pytest.approx(phi_ref, abs=0.003)


def test_pitzer_dilute_limit():
    """phi -> 1 as m -> 0, so Pitzer and van't Hoff agree for very dilute water."""
    assert m.osmotic_coefficient_pitzer(0.0) == 1.0
    ratio = m.osmotic_pressure_pitzer(0.01) / m.osmotic_pressure_vant_hoff(0.01)
    assert ratio == pytest.approx(1.0, abs=0.01)


def test_osmotic_pressure_dispatch():
    assert m.osmotic_pressure(C_SEA) == m.osmotic_pressure_vant_hoff(C_SEA)
    assert m.osmotic_pressure(C_SEA, model="pitzer") == m.osmotic_pressure_pitzer(C_SEA)
    with pytest.raises(ValueError):
        m.osmotic_pressure(C_SEA, model="ideal")


def test_osmotic_pressure_vectorised():
    c = np.array([0.0, 3.0, 35.0, 70.0])
    for model in ("vant_hoff", "pitzer"):
        pi = m.osmotic_pressure(c, model=model)
        assert pi.shape == c.shape
        assert np.all(np.diff(pi) > 0)


# ------------------------------------------------------ temperature factor


def test_tcf_reference_and_monotonic():
    assert m.temperature_correction_factor(T25) == pytest.approx(1.0, rel=1e-15)
    T = m.celsius_to_kelvin(np.linspace(5, 40, 36))
    assert np.all(np.diff(m.temperature_correction_factor(T)) > 0)


def test_tcf_formula():
    T35, T15 = m.celsius_to_kelvin(35.0), m.celsius_to_kelvin(15.0)
    assert m.temperature_correction_factor(T35) == pytest.approx(
        np.exp(m.TCF_K_ABOVE * (1 / T25 - 1 / T35)), rel=1e-14
    )
    assert m.temperature_correction_factor(T15) == pytest.approx(
        np.exp(m.TCF_K_BELOW * (1 / T25 - 1 / T15)), rel=1e-14
    )


# ------------------------------------------------------------------ SEC_min


def _sec_min_quad(c_feed, r, model):
    """Independent check: integrate in the ORIGINAL recovery variable with SciPy."""
    val, _ = quad(lambda rp: m.osmotic_pressure(c_feed / (1 - rp), model=model), 0.0, r,
                  epsabs=0.0, epsrel=1e-13, limit=200)
    return val / r


@pytest.mark.parametrize("r", [0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95])
def test_sec_min_numeric_equals_analytic_vant_hoff(r):
    analytic = m.sec_min_vant_hoff(C_SEA, r)
    assert m.sec_min(C_SEA, r, model="vant_hoff") == pytest.approx(analytic, rel=1e-8)
    assert _sec_min_quad(C_SEA, r, "vant_hoff") == pytest.approx(analytic, rel=1e-8)


@pytest.mark.parametrize("r", [0.1, 0.5, 0.9])
def test_sec_min_pitzer_matches_scipy_quad(r):
    assert m.sec_min(C_SEA, r, model="pitzer") == pytest.approx(
        _sec_min_quad(C_SEA, r, "pitzer"), rel=1e-8
    )


def test_sec_min_simpson_converged():
    """Default n = 128 is converged to < 1e-9 even at 90 % recovery with Pitzer."""
    default = m.sec_min(C_SEA, 0.9, model="pitzer")
    fine = m.sec_min(C_SEA, 0.9, model="pitzer", n=2048)
    assert default == pytest.approx(fine, rel=1e-9)
    # an odd n is rounded up to the next even number (Simpson needs pairs)
    assert m.sec_min(C_SEA, 0.5, n=7) == m.sec_min(C_SEA, 0.5, n=8)


def test_sec_min_limits_and_monotonic():
    pi_f = m.osmotic_pressure_vant_hoff(C_SEA)
    assert m.sec_min(C_SEA, 0.0) == pytest.approx(pi_f)
    assert m.sec_min_vant_hoff(C_SEA, 0.0) == pytest.approx(pi_f)
    assert m.sec_min_vant_hoff(C_SEA, 1e-9) == pytest.approx(pi_f, rel=1e-8)
    rs = np.linspace(0.05, 0.9, 18)
    for model in ("vant_hoff", "pitzer"):
        e = [m.sec_min(C_SEA, r, model=model) for r in rs]
        assert np.all(np.diff(e) > 0)
    with pytest.raises(ValueError):
        m.sec_min(C_SEA, 1.0)


def test_sec_min_seawater_50pct():
    """35 g/L, r = 0.5. Elimelech & Phillip (2011, Science) give 1.06 kWh/m^3.

    van't Hoff gives ~1.14 (pi_f ln2 / 0.5); the Pitzer correction (phi ~ 0.92-0.94)
    brings it to ~1.06. The ~8 % gap is the non-ideality of the salt solution.
    """
    vh = float(m.j_per_m3_to_kwh_per_m3(m.sec_min(C_SEA, 0.5, model="vant_hoff")))
    pz = float(m.j_per_m3_to_kwh_per_m3(m.sec_min(C_SEA, 0.5, model="pitzer")))
    assert vh == pytest.approx(1.143, abs=0.005)
    assert pz == pytest.approx(1.06, rel=0.02)
    assert 0.90 < pz / vh < 0.95
