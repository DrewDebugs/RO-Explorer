"""Cross-check against the independent model written by a second AI (Muse).

docs/ai-log/second-model/ro_model_muse.py is kept verbatim as Muse wrote it. These tests pin down
where the two implementations agree, and document (rather than hide) where they differ.
Details: docs/ai-log/04-implementation-comparison.md.
"""

import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs" / "ai-log" / "second-model"))

import ro_model as claude  # noqa: E402
import ro_model_muse as muse  # noqa: E402

LMH = 1e-3 / 3600


@pytest.mark.parametrize("c", [0.5, 3.0, 35.0, 70.0])
def test_osmotic_pressure_agrees(c):
    assert muse.osmotic_pressure(c) == pytest.approx(float(claude.osmotic_pressure(c)), rel=1e-14)
    # Pitzer differs slightly: Muse uses rho_w = 1000 kg/m3 for molality, this repo 997.05
    assert muse.osmotic_pressure(c, use_pitzer=True) == pytest.approx(
        float(claude.osmotic_pressure(c, model="pitzer")), rel=2e-4)


def test_local_solver_agrees_van_t_hoff(record_property):
    worst = 0.0
    for cb in np.linspace(35, 70, 8):
        for P in np.linspace(40, 80, 9):
            for B in (0.0, 0.05, 0.5):
                A, k = 1.4 * LMH / 1e5, 180 * LMH
                a = claude.solve_local(float(cb), P * 1e5, A, B * LMH, k)
                b = muse.solve_local(float(cb), P * 1e5, 0.0, A, B * LMH, k)
                if a.J_w == 0:
                    assert b["jw_ms"] == 0.0
                else:
                    worst = max(worst, abs(b["jw_ms"] - a.J_w) / a.J_w)
    record_property("worst_rel_diff_Jw", worst)
    assert worst < 1e-8


@pytest.mark.parametrize("ui, kw", [
    ({}, {}),
    ({"C_f": 3, "P_f": 15, "A": 3.0, "B": 0.2},
     {"feed_salinity_g_l": 3.0, "feed_pressure_bar": 15.0, "a_lmh_per_bar": 3.0, "b_lmh": 0.2}),
    ({"k": 40, "P_f": 70}, {"k_lmh": 40.0, "feed_pressure_bar": 70.0}),
    ({"P_f": 40, "Q_f": 2, "A": 1.0, "B": 0, "k": 2000, "pressure_drop_on": False},
     {"feed_pressure_bar": 40.0, "feed_flow_m3_h": 2.0, "a_lmh_per_bar": 1.0, "b_lmh": 0.0, "k_lmh": 2000.0,
      "pressure_drop_bar": 0.0}),
])
def test_vessel_agrees_at_25C(ui, kw):
    a = claude.simulate_vessel(claude.inputs_from_ui(ui))
    b = muse.solve_vessel(**kw)
    assert b["recovery"] == pytest.approx(a.recovery, rel=1e-8)
    assert b["cp_mixed_final"] == pytest.approx(a.C_p_mixed, rel=1e-6)


def test_r_max_both_models_ideal_case():
    """Muse's question 1: with an ideal membrane, no CP and no pressure drop, both reach r_max."""
    inp = replace(claude.VesselInputs(), B25=0.0, k=math.inf, dP_drop=0.0, area_element=409.0)
    r_max = claude.r_max_ideal(35.0, 60e5)
    m = muse.solve_vessel(b_lmh=0.0, k_lmh=1e12, pressure_drop_bar=0.0, elements=70, element_length_m=0.1016)
    assert claude.simulate_vessel(inp).recovery == pytest.approx(r_max, abs=1e-6)
    assert m["recovery"] == pytest.approx(r_max, abs=1e-6)


def test_known_difference_temperature(record_property):
    """Documented difference: Muse's vessel model never applies the temperature correction to A and B,
    so its recovery rises in cold water. This repo's falls, as FilmTec's TCF requires."""
    rec = {T: (claude.simulate_vessel(claude.inputs_from_ui({"T": T})).recovery,
               muse.solve_vessel(temp_c=float(T))["recovery"]) for T in (15, 25, 35)}
    record_property("recovery_claude_muse_by_T", {T: [round(a, 4), round(b, 4)] for T, (a, b) in rec.items()})
    assert rec[15][0] < rec[25][0] < rec[35][0]          # this repo: permeance rises with T
    assert rec[25][1] == pytest.approx(rec[25][0], rel=1e-8)
    assert rec[15][1] > rec[25][1]                        # Muse: no TCF, so colder looks better
