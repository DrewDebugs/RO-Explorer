"""M4 tests: energy and economics."""

import math
from dataclasses import replace

import numpy as np
import pytest

import ro_model as m

C_SEA = 35.0


def test_free_energy_density_gives_osmotic_pressure():
    """pi = c g'(c) - g(c) for both models (central difference)."""
    for model in ("vant_hoff", "pitzer"):
        for c in (1.0, 10.0, 35.0, 70.0):
            h = 1e-4 * c
            dg = (m.free_energy_density(c + h, model=model, n=256)
                  - m.free_energy_density(c - h, model=model, n=256)) / (2 * h)
            pi = c * dg - m.free_energy_density(c, model=model, n=256)
            assert pi == pytest.approx(float(m.osmotic_pressure(c, model=model)), rel=1e-6)


@pytest.mark.parametrize("model", ["vant_hoff", "pitzer"])
@pytest.mark.parametrize("r", [0.1, 0.5, 0.8])
def test_actual_bound_reduces_to_ideal(model, r):
    c_b = C_SEA / (1 - r)
    assert m.sec_min_actual(C_SEA, 0.0, c_b, r, model=model) == pytest.approx(
        m.sec_min(C_SEA, r, model=model), rel=1e-7)


def test_actual_bound_lower_for_leaky_membrane():
    r, c_p = 0.5, 0.5
    c_b = (C_SEA - r * c_p) / (1 - r)
    assert 0 < m.sec_min_actual(C_SEA, c_p, c_b, r) < m.sec_min(C_SEA, r)


def test_erd_lowers_sec():
    assert m.sec_erd(60e5, 58.5e5, 0.45, 0.8, 0.95) < m.sec_pump(60e5, 0.45, 0.8)
    # perfect pump and ERD, no pressure drop: SEC = P_f
    assert m.sec_erd(60e5, 60e5, 0.45, 1.0, 1.0) == pytest.approx(60e5)


def _random_inputs(rng):
    return m.VesselInputs(
        C_f=rng.uniform(0.5, 70),
        P_f=rng.uniform(5, 85) * 1e5,
        Q_f=rng.uniform(2, 16) / 3600,
        T=m.celsius_to_kelvin(rng.uniform(5, 40)),
        A25=m.lmh_per_bar_to_si(rng.uniform(0.3, 10)),
        B25=float(m.lmh_to_m_per_s(rng.uniform(0, 1))) if rng.random() > 0.1 else 0.0,
        k=float(m.lmh_to_m_per_s(rng.uniform(20, 2000))),
        n_elements=int(rng.integers(1, 9)),
        dP_drop=rng.uniform(0, 5) * 1e5,
        model=str(rng.choice(["vant_hoff", "pitzer"])),
    )


def test_sec_above_minimum_random_sweep():
    """Second law: SEC >= SEC_min(actual separation) for ~500 random cases,
    even with a perfect pump and ERD; and >= ideal SEC_min when B = 0."""
    rng = np.random.default_rng(2026)
    checked = 0
    for _ in range(500):
        inp = _random_inputs(rng)
        res = m.simulate_vessel(inp, N=40, fixed_N=True)
        r = res.recovery
        if not 1e-6 < r < 0.999:
            continue
        sec_best = m.sec_erd(inp.P_f, res.P_out, r, 1.0, 1.0)
        bound = m.sec_min_actual(inp.C_f, res.C_p_mixed, res.C_b_out, r, inp.T, inp.model)
        assert sec_best >= bound * (1 - 1e-9)
        assert m.sec_pump(inp.P_f, r, 0.8) >= sec_best
        if inp.B25 == 0:
            assert sec_best >= m.sec_min(inp.C_f, r, inp.T, inp.model)
        checked += 1
    assert checked > 400


def test_crf_known_value():
    assert m.capital_recovery_factor(0.08, 25) == pytest.approx(0.0936788, rel=1e-6)
    assert m.capital_recovery_factor(0.0, 20) == 0.05


def test_water_cost_hand_calculation():
    eco = m.EconomicsInputs(capacity=10_000, availability=0.9, electricity_price=0.10,
                            membrane_cost=500, vessel_cost=1000, pump_erd_cost=1000,
                            other_multiplier=5, interest=0.0, plant_life=20,
                            membrane_life=5, om_fraction=0.02)
    out = m.water_cost(sec_kwh_m3=3.0, vessel_permeate_m3h=4.0, n_elements=7, eco=eco)
    # 10,000 / (4 x 24) = 104.17 -> 105 vessels, 735 elements
    assert out["n_vessels"] == 105 and out["n_elements"] == 735
    # power 3 x 10,000/24 = 1250 kW; CAPEX = (367,500 + 105,000 + 1,250,000) x 5 = 8,612,500
    assert out["capex_total"] == pytest.approx(8_612_500)
    annual = 10_000 * 365 * 0.9  # 3,285,000 m^3
    p = out["parts"]
    assert p["capital"] == pytest.approx(8_612_500 / 20 / annual)
    assert p["energy"] == pytest.approx(0.30)
    assert p["membrane_replacement"] == pytest.approx(367_500 / 5 / annual)
    assert p["fixed_om"] == pytest.approx(0.02 * 8_612_500 / annual)
    assert out["total"] == pytest.approx(sum(p.values()))


def test_ui_api_round_trip():
    import json
    out = json.loads(m.run_from_ui("{}"))
    assert 0.40 < out["summary"]["recovery"] < 0.47
    assert out["energy"]["erd"] < out["energy"]["no_erd"]
    assert out["energy"]["min_actual"] < out["energy"]["min_ideal"] < out["energy"]["erd"]
    assert 0.3 < out["economics"]["total"] < 1.5
    assert len(out["profiles"]["x"]) == len(out["profiles"]["J_w"]) <= 201
    sweep = json.loads(m.pressure_sweep("{}", n=8))
    assert np.all(np.diff(sweep["recovery"]) >= 0)
    low = json.loads(m.run_from_ui(json.dumps({"P_f": 20})))
    assert any(w["level"] == "error" for w in low["warnings"])
