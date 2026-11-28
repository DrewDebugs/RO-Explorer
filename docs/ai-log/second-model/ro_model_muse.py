"""
RO Desalination Explorer — independent model implementation (Muse).

Independent re-implementation of the plan in ``01-plan.md`` (Claude Opus 5.5),
for comparison against the Claude Code implementation in the
DrewDebugs/RO-Explorer repo. Written from the plan text alone, not from
that repo's code, so agreement between the two is a genuine cross-check.

Scope: plan §3 only — properties, local solution-diffusion + film model,
1D pressure-vessel balances (RK4), energy / SEC_min, and economics (§3.7).
No web / Pyodide / Plotly code here. No SciPy: numpy only, plus stdlib
``math``. All internal units are SI (m, s, Pa, kg/m3, mol/m3, K);
conversions happen only at the boundary, in named, tested helpers.

Defaults: the *verified* defaults from ``03-decisions.md`` D29–D31
(A = 1.4 LMH/bar, B = 0.05 LMH, feed 12 m3/h, electricity $0.096/kWh),
not the plan's original §4 guesses (A = 1.0, B = 0.10, feed 9 m3/h).
The plan originals are kept as ``PLAN_DEFAULTS`` for comparison.
Pressures are gauge throughout (D14): permeate at 0 bar gauge.

Known limitations, stated on the page in the plan:
- k is constant along the vessel (bias quantified in 03-decisions.md C3).
- Molality is approximated from g/L (D6, ~1% low at 35 g/L).
- Pitzer toggle is NaCl, not full seawater (C10).
- TCF constants are FilmTec design-equation values, TODO-VERIFY in the
  plan; here A uses 3020 K and B uses 2640 K (see ``tcf``).
- Booster / intake / pretreatment energy is excluded (D17).

Run as a script for a smoke check:
    python ro_model.py
"""

from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

R_GAS = 8.314462618  # J / (mol K)
M_NACL = 58.44e-3  # kg / mol
I_NACL = 2.0  # van't Hoff factor for NaCl
RHO_WATER = 1000.0  # kg/m3, used only for the molality approximation (D6)
T_REF = 298.15  # K, 25 C

# Pitzer NaCl parameters at 25 C, Pitzer & Mayorga 1973 (plan §3.2)
PITZER_A_PHI = 0.392
PITZER_BETA0 = 0.0765
PITZER_BETA1 = 0.2664
PITZER_C_PHI = 0.00127
PITZER_B = 1.2  # kg^1/2 / mol^1/2
PITZER_ALPHA = 2.0

# ---------------------------------------------------------------------------
# Unit conversions (plan §3.1, all tested by round-trip)
# ---------------------------------------------------------------------------

def lmh_to_ms(lmh: float) -> float:
    """1 LMH = 1 L m^-2 h^-1 = 2.7778e-7 m/s."""
    return lmh * 1.0e-3 / 3600.0


def ms_to_lmh(ms: float) -> float:
    return ms * 3600.0 / 1.0e-3


def lmh_per_bar_to_ms_per_pa(v: float) -> float:
    return lmh_to_ms(v) / 1.0e5


def bar_to_pa(bar: float) -> float:
    return bar * 1.0e5


def pa_to_bar(pa: float) -> float:
    return pa / 1.0e5


def j_per_m3_to_kwh_per_m3(j_per_m3: float) -> float:
    """1 kWh = 3.6e6 J, so 1 bar (= 1e5 J/m3) = 1/36 kWh/m3."""
    return j_per_m3 / 3.6e6


def kwh_per_m3_to_j_per_m3(kwh: float) -> float:
    return kwh * 3.6e6


def bar_to_kwh_per_m3(bar: float) -> float:
    return bar / 36.0


# ---------------------------------------------------------------------------
# Osmotic pressure (plan §3.2)
# ---------------------------------------------------------------------------

def molality_from_conc(c_kg_m3: float) -> float:
    """Molality (mol/kg water) approximated from g/L, D6: m = (C/M) / rho_w."""
    return (c_kg_m3 / M_NACL) / RHO_WATER


def pitzer_phi(molality: float) -> float:
    """Osmotic coefficient of NaCl from the Pitzer equation.

    phi = 1 - A_phi*sqrt(m)/(1 + b*sqrt(m))
              + m * [beta0 + beta1*exp(-alpha*sqrt(m)) + C_phi*m]
    At m = 0.6 mol/kg this gives phi ~= 0.92, matching plan §3.2.
    """
    if molality <= 0.0:
        return 1.0
    s = math.sqrt(molality)
    return (
        1.0
        - PITZER_A_PHI * s / (1.0 + PITZER_B * s)
        + molality
        * (
            PITZER_BETA0
            + PITZER_BETA1 * math.exp(-PITZER_ALPHA * s)
            + PITZER_C_PHI * molality
        )
    )


def osmotic_pressure_vant_hoff(c_kg_m3: float, temp_k: float = T_REF) -> float:
    """van't Hoff pi = i * c * R * T, c in mol/m3, result in Pa."""
    c_mol_m3 = c_kg_m3 / M_NACL
    return I_NACL * c_mol_m3 * R_GAS * temp_k


def osmotic_pressure(
    c_kg_m3: float, temp_k: float = T_REF, use_pitzer: bool = False
) -> float:
    """Osmotic pressure in Pa. Pitzer: pi = phi(m) * pi_van't Hoff (D6)."""
    pi_vh = osmotic_pressure_vant_hoff(c_kg_m3, temp_k)
    if not use_pitzer:
        return pi_vh
    return pitzer_phi(molality_from_conc(c_kg_m3)) * pi_vh


# ---------------------------------------------------------------------------
# Temperature correction (plan §3.2)
# ---------------------------------------------------------------------------

def tcf(temp_k: float, constant_k: float = 3020.0, temp_ref: float = T_REF) -> float:
    """Arrhenius-type temperature correction factor.

    TCF = exp(constant * (1/T_ref - 1/T)).
    Default 3020 K is the FilmTec water-permeability constant; use
    2640 K for salt permeability. Both are TODO-VERIFY in the plan
    (verified in the repo against FilmTec Eq. 16a,b, 03-decisions.md C11).
    """
    return math.exp(constant_k * (1.0 / temp_ref - 1.0 / temp_k))


def tcf_water(temp_k: float) -> float:
    return tcf(temp_k, 3020.0)


def tcf_salt(temp_k: float) -> float:
    return tcf(temp_k, 2640.0)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

PLAN_DEFAULTS = dict(
    feed_salinity_g_l=35.0,
    feed_pressure_bar=60.0,
    feed_flow_m3_h=9.0,
    temp_c=25.0,
    a_lmh_per_bar=1.0,
    b_lmh=0.10,
    k_lmh=180.0,
    elements=7,
    element_area_m2=40.9,
    element_length_m=1.016,
    pressure_drop_bar=1.5,
    pump_efficiency=0.80,
    erd_efficiency=0.95,
)

# Verified defaults, 03-decisions.md D29-D31 (supersede PLAN_DEFAULTS).
DEFAULTS = dict(
    PLAN_DEFAULTS,
    a_lmh_per_bar=1.4,
    b_lmh=0.05,
    feed_flow_m3_h=12.0,
    electricity_usd_per_kwh=0.096,
    element_cost_usd=1000.0,
    vessel_cost_usd=2700.0,
    pump_cost_usd_per_kw=400.0,
    other_plant_multiplier=12.5,
    fixed_om_fraction=0.045,
    membrane_life_years=5.0,
    interest=0.08,
    plant_life_years=25.0,
    plant_capacity_m3_d=100000.0,
    availability=0.95,
)

PRESETS = {
    "seawater": dict(feed_salinity_g_l=35.0, feed_pressure_bar=60.0,
                     a_lmh_per_bar=1.4, b_lmh=0.05, feed_flow_m3_h=12.0),
    "brackish": dict(feed_salinity_g_l=3.0, feed_pressure_bar=15.0,
                     a_lmh_per_bar=3.0, b_lmh=0.20, feed_flow_m3_h=12.0),
    # Pinch demo, 03-decisions.md D23: ideal membrane, reaches pinch ~4.9 m.
    "pinch": dict(feed_salinity_g_l=35.0, feed_pressure_bar=40.0,
                  a_lmh_per_bar=1.4, b_lmh=0.0, feed_flow_m3_h=2.0),
}

# ---------------------------------------------------------------------------
# Local (per-position) solution-diffusion + film model (plan §3.3)
# ---------------------------------------------------------------------------

def local_cp_cm(jw_ms: float, cb_kg_m3: float, b_ms: float, k_ms: float):
    """Closed forms for a given J_w (plan §3.3).

    E = exp(J_w/k);  C_p = B*E*C_b / (J_w + B*E);
    C_m = C_p + (C_b - C_p)*E.  All concentrations in kg/m3.
    """
    if b_ms == 0.0:
        return 0.0, cb_kg_m3 * math.exp(min(jw_ms / k_ms, 100.0)) if k_ms > 0 else cb_kg_m3
    # exp argument is small in practice (|J_w/k| < ~1); clip for safety.
    e = math.exp(max(-100.0, min(100.0, jw_ms / k_ms))) if k_ms > 0 else 1.0
    cp = b_ms * e * cb_kg_m3 / (jw_ms + b_ms * e)
    cm = cp + (cb_kg_m3 - cp) * e
    return cp, cm


def _local_residual(jw_ms, cb, delta_p_pa, a_ms_per_pa, b_ms, k_ms, temp_k, use_pitzer):
    cp, cm = local_cp_cm(jw_ms, cb, b_ms, k_ms)
    pi_m = osmotic_pressure(cm, temp_k, use_pitzer)
    pi_p = osmotic_pressure(cp, temp_k, use_pitzer)
    return jw_ms - a_ms_per_pa * (delta_p_pa - (pi_m - pi_p)), cp, cm


def solve_local(
    cb_kg_m3: float,
    pressure_pa: float,
    permeate_pressure_pa: float = 0.0,
    a_ms_per_pa: float = None,
    b_ms: float = None,
    k_ms: float = None,
    temp_k: float = T_REF,
    use_pitzer: bool = False,
    tol: float = 1.0e-16,
    max_iter: int = 100,
) -> dict:
    """Solve the local flux problem for one position.

    Returns dict with J_w (m/s), C_p, C_m (kg/m3), CP factor, observed
    and intrinsic rejection, NDP (Pa), iterations, and a flag for the
    B = 0 pinch (J_w = 0 exactly when delta_P <= pi(C_b)).
    Defaults for A/B/k are the verified defaults, converted to SI.
    """
    if a_ms_per_pa is None:
        a_ms_per_pa = lmh_per_bar_to_ms_per_pa(DEFAULTS["a_lmh_per_bar"])
    if b_ms is None:
        b_ms = lmh_to_ms(DEFAULTS["b_lmh"])
    if k_ms is None:
        k_ms = lmh_to_ms(DEFAULTS["k_lmh"])

    delta_p = pressure_pa - permeate_pressure_pa
    if delta_p <= 0.0:
        return dict(jw_ms=0.0, cp_kg_m3=cb_kg_m3, cm_kg_m3=cb_kg_m3,
                    cp_factor=1.0, rejection_obs=0.0, rejection_int=0.0,
                    ndp_pa=delta_p, iterations=0, pinched=True)

    if b_ms == 0.0:
        # Ideal rejection: exact pinch.
        if delta_p <= osmotic_pressure(cb_kg_m3, temp_k, use_pitzer):
            return dict(jw_ms=0.0, cp_kg_m3=0.0, cm_kg_m3=cb_kg_m3,
                        cp_factor=1.0, rejection_obs=1.0, rejection_int=1.0,
                        ndp_pa=delta_p, iterations=0, pinched=True)

    # Bracket (0, A*delta_P] for B > 0 (plan §3.3); for B = 0 the upper
    # end is also a valid bracket once delta_P > pi(C_b).
    lo, hi = 0.0, a_ms_per_pa * delta_p
    f_lo, _, _ = _local_residual(lo, cb_kg_m3, delta_p, a_ms_per_pa, b_ms, k_ms, temp_k, use_pitzer)
    f_hi, _, _ = _local_residual(hi, cb_kg_m3, delta_p, a_ms_per_pa, b_ms, k_ms, temp_k, use_pitzer)
    if f_hi == 0.0:
        jw = hi
        _, cp, cm = _local_residual(jw, cb_kg_m3, delta_p, a_ms_per_pa, b_ms, k_ms, temp_k, use_pitzer)
        return _local_result(jw, cp, cm, cb_kg_m3, delta_p, 0, temp_k, use_pitzer)
    # Illinois (modified regula falsi) with bisection fallback (D9:
    # tolerance |f| <= 1e-16 m/s, forced bisection if the bracket does
    # not halve in two iterations).
    side = 0
    width0 = hi - lo
    last_width = width0
    stall = 0
    jw = 0.5 * (lo + hi)
    it = 0
    for it in range(1, max_iter + 1):
        if side == 1:
            f_lo *= 0.5
        elif side == -1:
            f_hi *= 0.5
        # Regula falsi step; fall back to bisection if it leaves the bracket.
        denom = f_hi - f_lo
        x = lo - f_lo * (hi - lo) / denom if denom != 0.0 else 0.5 * (lo + hi)
        if not (lo < x < hi):
            x = 0.5 * (lo + hi)
        f_x, cp, cm = _local_residual(x, cb_kg_m3, delta_p, a_ms_per_pa, b_ms, k_ms, temp_k, use_pitzer)
        if abs(f_x) <= tol:
            return _local_result(x, cp, cm, cb_kg_m3, delta_p, it, temp_k, use_pitzer)
        if f_x * f_lo < 0:
            hi, f_hi, side = x, f_x, -1
        else:
            lo, f_lo, side = x, f_x, 1
        width = hi - lo
        if width > 0.5 * last_width:
            stall += 1
        else:
            stall = 0
        last_width = width
        if stall >= 2:
            # Forced bisection step (D9).
            x = 0.5 * (lo + hi)
            f_x, cp, cm = _local_residual(x, cb_kg_m3, delta_p, a_ms_per_pa, b_ms, k_ms, temp_k, use_pitzer)
            if abs(f_x) <= tol:
                return _local_result(x, cp, cm, cb_kg_m3, delta_p, it, temp_k, use_pitzer)
            if f_x * f_lo < 0:
                hi, f_hi = x, f_x
            else:
                lo, f_lo = x, f_x
            stall = 0
            last_width = hi - lo
        jw = 0.5 * (lo + hi)
    _, cp, cm = _local_residual(jw, cb_kg_m3, delta_p, a_ms_per_pa, b_ms, k_ms, temp_k, use_pitzer)
    return _local_result(jw, cp, cm, cb_kg_m3, delta_p, it, temp_k, use_pitzer)


def _local_result(jw, cp, cm, cb, delta_p, it, temp_k=T_REF, use_pitzer=False):
    cp_factor = cm / cb if cb > 0 else 1.0
    ndp = delta_p - (osmotic_pressure(cm, temp_k, use_pitzer)
                     - osmotic_pressure(cp, temp_k, use_pitzer))
    return dict(
        jw_ms=float(jw), cp_kg_m3=float(cp), cm_kg_m3=float(cm),
        cp_factor=float(cp_factor),
        rejection_obs=float(1.0 - cp / cb) if cb > 0 else 0.0,
        rejection_int=float(1.0 - cp / cm) if cm > 0 else 0.0,
        ndp_pa=float(ndp),
        iterations=int(it), pinched=bool(jw == 0.0),
    )

# ---------------------------------------------------------------------------
# 1D pressure-vessel model (plan §3.4) — classical RK4
# ---------------------------------------------------------------------------

def _rhs(state, width_m, a, b, k, temp_k, use_pitzer, dp_drop_pa, length_m):
    """Right-hand side for y = [Q, S, Qp, Sp, P] (SI: m3/s, kg/s, Pa)."""
    q, s, _qp, _sp, p = state
    if q <= 0.0:
        return np.array([0.0, 0.0, 0.0, 0.0, -dp_drop_pa / length_m])
    cb = s / q
    loc = solve_local(cb, p, 0.0, a, b, k, temp_k, use_pitzer)
    jw, cp = loc["jw_ms"], loc["cp_kg_m3"]
    return np.array([
        -jw * width_m,
        -jw * cp * width_m,
        jw * width_m,
        jw * cp * width_m,
        -dp_drop_pa / length_m,
    ])


def solve_vessel_n(
    n_steps: int,
    feed_flow_m3_h: float = DEFAULTS["feed_flow_m3_h"],
    feed_salinity_g_l: float = DEFAULTS["feed_salinity_g_l"],
    feed_pressure_bar: float = DEFAULTS["feed_pressure_bar"],
    temp_c: float = DEFAULTS["temp_c"],
    a_lmh_per_bar: float = DEFAULTS["a_lmh_per_bar"],
    b_lmh: float = DEFAULTS["b_lmh"],
    k_lmh: float = DEFAULTS["k_lmh"],
    elements: int = DEFAULTS["elements"],
    element_area_m2: float = DEFAULTS["element_area_m2"],
    element_length_m: float = DEFAULTS["element_length_m"],
    pressure_drop_bar: float = DEFAULTS["pressure_drop_bar"],
    use_pitzer: bool = False,
) -> dict:
    """One RK4 run with N uniform steps. Returns profiles + summary."""
    temp_k = temp_c + 273.15
    length_m = elements * element_length_m
    area_m2 = elements * element_area_m2
    width_m = area_m2 / length_m
    a = lmh_per_bar_to_ms_per_pa(a_lmh_per_bar)
    b = lmh_to_ms(b_lmh)
    k = lmh_to_ms(k_lmh)
    dp_drop_pa = bar_to_pa(pressure_drop_bar)

    q0 = feed_flow_m3_h / 3600.0  # m3/s
    cf = feed_salinity_g_l  # kg/m3 (= g/L)
    y = np.array([q0, q0 * cf, 0.0, 0.0, bar_to_pa(feed_pressure_bar)], dtype=float)
    dx = length_m / n_steps
    xs = np.linspace(0.0, length_m, n_steps + 1)
    prof = np.zeros((n_steps + 1, 5))
    jw_prof = np.zeros(n_steps + 1)
    cp_prof = np.zeros(n_steps + 1)
    cm_prof = np.zeros(n_steps + 1)
    prof[0] = y
    for i in range(n_steps):
        # Record local values at the start of the step.
        cb = y[1] / y[0] if y[0] > 0 else cf
        loc = solve_local(cb, y[4], 0.0, a, b, k, temp_k, use_pitzer)
        jw_prof[i], cp_prof[i], cm_prof[i] = loc["jw_ms"], loc["cp_kg_m3"], loc["cm_kg_m3"]
        k1 = _rhs(y, width_m, a, b, k, temp_k, use_pitzer, dp_drop_pa, length_m)
        k2 = _rhs(y + 0.5 * dx * k1, width_m, a, b, k, temp_k, use_pitzer, dp_drop_pa, length_m)
        k3 = _rhs(y + 0.5 * dx * k2, width_m, a, b, k, temp_k, use_pitzer, dp_drop_pa, length_m)
        k4 = _rhs(y + dx * k3, width_m, a, b, k, temp_k, use_pitzer, dp_drop_pa, length_m)
        y = y + (dx / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        y[0] = max(y[0], 0.0)
        prof[i + 1] = y
    cb_end = prof[-1, 1] / prof[-1, 0] if prof[-1, 0] > 0 else cf
    loc = solve_local(cb_end, prof[-1, 4], 0.0, a, b, k, temp_k, use_pitzer)
    jw_prof[-1], cp_prof[-1], cm_prof[-1] = loc["jw_ms"], loc["cp_kg_m3"], loc["cm_kg_m3"]

    q_out, s_out, qp, sp, _p_out = prof[-1]
    recovery = qp / q0 if q0 > 0 else 0.0
    cp_mixed = sp / qp if qp > 0 else 0.0
    # Pinch: first x where local flux < 1% of inlet flux (plan §3.4).
    x_pinch = None
    if jw_prof[0] > 0:
        below = np.where(jw_prof < 0.01 * jw_prof[0])[0]
        if len(below):
            x_pinch = float(xs[below[0]])
    return dict(
        x_m=xs, q_m3_s=prof[:, 0], cb_kg_m3=prof[:, 1] / np.maximum(prof[:, 0], 1e-300),
        qp_m3_s=prof[:, 2], cp_mixed_kg_m3=prof[:, 3] / np.maximum(prof[:, 2], 1e-300),
        p_pa=prof[:, 4], jw_ms=jw_prof, cp_local_kg_m3=cp_prof, cm_kg_m3=cm_prof,
        recovery=float(recovery), cp_mixed_final=float(cp_mixed),
        rejection_obs=float(1.0 - cp_mixed / cf) if qp > 0 else 0.0,
        brine_kg_m3=float(cb_end), length_m=float(length_m),
        area_m2=float(area_m2), n_steps=int(n_steps), x_pinch_m=x_pinch,
        feed_flow_m3_h=float(feed_flow_m3_h), feed_salinity_g_l=float(cf),
        feed_pressure_bar=float(feed_pressure_bar),
    )


def solve_vessel(*args, n_start: int = 50, tol: float = 1.0e-4, n_max: int = 3200, **kwargs) -> dict:
    """Auto-converging vessel solve (plan §3.4, D10).

    Solve with N and 2N, compare recovery, mixed permeate concentration
    and SEC; double until max relative change < 1e-4 (max 3200).
    Returns the finer run, with ``n_steps`` and ``converged`` set.
    """
    prev = solve_vessel_n(n_start, *args, **kwargs)
    while True:
        nxt = solve_vessel_n(prev["n_steps"] * 2, *args, **kwargs)
        # SEC needs a pressure/efficiency; use recovery/Cp as proxies
        # plus a no-ERD SEC at the run's pressure for the SEC comparison.
        def _sec(run):
            return run["feed_pressure_bar"] / (0.80 * run["recovery"]) / 36.0 if run["recovery"] > 0 else 0.0
        changes = []
        for key, ref in (("recovery", prev["recovery"]), ("cp_mixed_final", prev["cp_mixed_final"])):
            denom = abs(ref) if abs(ref) > 1e-12 else 1.0
            changes.append(abs(nxt[key] - ref) / denom)
        changes.append(abs(_sec(nxt) - _sec(prev)) / max(abs(_sec(prev)), 1e-12))
        if max(changes) < tol or nxt["n_steps"] >= n_max:
            nxt["converged"] = bool(max(changes) < tol)
            nxt["max_rel_change"] = float(max(changes))
            return nxt
        prev = nxt


def r_max_ideal(feed_salinity_g_l: float, feed_pressure_bar: float, temp_k: float = T_REF, use_pitzer: bool = False) -> float:
    """Ideal-membrane max recovery r_max = 1 - pi_f / delta_P (plan §3.5)."""
    pi_f = osmotic_pressure(feed_salinity_g_l, temp_k, use_pitzer)
    return 1.0 - pi_f / bar_to_pa(feed_pressure_bar)


# ---------------------------------------------------------------------------
# Energy (plan §3.6)
# ---------------------------------------------------------------------------

def sec_no_erd(feed_pressure_bar: float, recovery: float, pump_efficiency: float = 0.80) -> float:
    """SEC in kWh/m3, no ERD: SEC = delta_P / (eta_p * r) / 36 (see §2.1 fix)."""
    return bar_to_kwh_per_m3(feed_pressure_bar / (pump_efficiency * recovery))


def sec_with_erd(feed_pressure_bar: float, recovery: float, pressure_drop_bar: float = 1.5,
                 pump_efficiency: float = 0.80, erd_efficiency: float = 0.95) -> float:
    """SEC in kWh/m3 with a pressure exchanger (plan §3.6, D17: HP pumps only)."""
    p_b = feed_pressure_bar - pressure_drop_bar  # brine pressure, bar gauge
    numerator_bar = feed_pressure_bar - erd_efficiency * (1.0 - recovery) * p_b
    return bar_to_kwh_per_m3(numerator_bar / (pump_efficiency * recovery))


def sec_min_ideal(feed_salinity_g_l: float, recovery: float, temp_k: float = T_REF, use_pitzer: bool = False) -> float:
    """Reversible SEC_min in kWh/m3, ideal rejection (plan §3.6).

    Analytic for van't Hoff: pi_f * ln(1/(1-r)) / r / 36.
    Pitzer: Simpson in u = -ln(1-r') (D7), n = 128 intervals, which
    makes the integrand constant for van't Hoff and near-constant
    for Pitzer.
    """
    if recovery <= 0.0:
        return 0.0
    if not use_pitzer:
        pi_f = osmotic_pressure_vant_hoff(feed_salinity_g_l, temp_k)
        return j_per_m3_to_kwh_per_m3(pi_f * math.log(1.0 / (1.0 - recovery)) / recovery)
    # Simpson in u.
    n = 128
    u_max = -math.log(1.0 - recovery)
    us = np.linspace(0.0, u_max, n + 1)
    # integrand: pi(C_f * exp(u)) * exp(-u), in Pa
    vals = np.array([osmotic_pressure(feed_salinity_g_l * math.exp(u), temp_k, True) * math.exp(-u) for u in us])
    h = u_max / n
    integral = h / 3.0 * (vals[0] + vals[-1] + 4.0 * vals[1:-1:2].sum() + 2.0 * vals[2:-1:2].sum())
    return j_per_m3_to_kwh_per_m3(integral / recovery)


def _free_energy_density(c_kg_m3: float, temp_k: float = T_REF, use_pitzer: bool = False) -> float:
    """f(c) in J/m3: f(c) = c * integral_{c_ref}^{c} pi(c')/c'^2 dc'.

    c_ref = 1 mol/m3 (cancels in W_min by salt balance). Evaluated
    in u = ln(c') so the integrand pi/c' is well behaved.
    For van't Hoff this is iRT*c*ln(c/c_ref) exactly.
    """
    c_mol = c_kg_m3 / M_NACL
    if c_mol <= 1.0:
        return 0.0
    n = 200
    us = np.linspace(0.0, math.log(c_mol), n + 1)
    # pi(c')/c' in Pa / (mol/m3), c' = exp(u) mol/m3
    vals = np.array([
        osmotic_pressure(math.exp(u) * M_NACL, temp_k, use_pitzer) / math.exp(u) for u in us
    ])
    h = us[-1] / n
    integral = h / 3.0 * (vals[0] + vals[-1] + 4.0 * vals[1:-1:2].sum() + 2.0 * vals[2:-1:2].sum())
    return c_mol * integral  # J/m3 (c in mol/m3 * Pa/(mol/m3) * dimensionless)


def sec_min_actual(feed_salinity_g_l: float, cp_kg_m3: float, brine_kg_m3: float,
                   recovery: float, temp_k: float = T_REF, use_pitzer: bool = False) -> float:
    """SEC_min for the actual (leaky) separation, kWh/m3 permeate (plan §3.6).

    W_min = Vp*f(Cp) + Vb*f(Cb) - Vf*f(Cf), Vf = 1 m3, Vp = r, Vb = 1-r;
    divide by Vp.
    """
    if recovery <= 0.0:
        return 0.0
    w = (recovery * _free_energy_density(cp_kg_m3, temp_k, use_pitzer)
         + (1.0 - recovery) * _free_energy_density(brine_kg_m3, temp_k, use_pitzer)
         - _free_energy_density(feed_salinity_g_l, temp_k, use_pitzer))
    return j_per_m3_to_kwh_per_m3(w / recovery)


# ---------------------------------------------------------------------------
# Economics (plan §3.7, defaults D30-D31 — calibrated, see decisions log)
# ---------------------------------------------------------------------------

def crf(interest: float, years: float) -> float:
    return interest * (1.0 + interest) ** years / ((1.0 + interest) ** years - 1.0)


def economics(run: dict, sec_kwh_m3: float,
              plant_capacity_m3_d: float = DEFAULTS["plant_capacity_m3_d"],
              availability: float = DEFAULTS["availability"],
              electricity_usd_per_kwh: float = DEFAULTS["electricity_usd_per_kwh"],
              element_cost_usd: float = DEFAULTS["element_cost_usd"],
              vessel_cost_usd: float = DEFAULTS["vessel_cost_usd"],
              pump_cost_usd_per_kw: float = DEFAULTS["pump_cost_usd_per_kw"],
              other_plant_multiplier: float = DEFAULTS["other_plant_multiplier"],
              fixed_om_fraction: float = DEFAULTS["fixed_om_fraction"],
              membrane_life_years: float = DEFAULTS["membrane_life_years"],
              interest: float = DEFAULTS["interest"],
              plant_life_years: float = DEFAULTS["plant_life_years"],
              elements: int = DEFAULTS["elements"]) -> dict:
    """Simple teaching economics, $/m3. Multiplier is calibrated (D30),
    not independently verified — see 03-decisions.md patched note."""
    permeate_m3_d_per_vessel = run["qp_m3_s"][-1] * 86400.0
    n_vessels = plant_capacity_m3_d / permeate_m3_d_per_vessel if permeate_m3_d_per_vessel > 0 else float("inf")
    n_elements = n_vessels * elements
    capex_membranes = n_elements * element_cost_usd
    capex_vessels = n_vessels * vessel_cost_usd
    power_kw = sec_kwh_m3 * plant_capacity_m3_d / 24.0
    capex_pump_erd = power_kw * pump_cost_usd_per_kw
    capex_base = capex_membranes + capex_vessels + capex_pump_erd
    capex_total = capex_base * other_plant_multiplier
    annual_water_m3 = plant_capacity_m3_d * 365.0 * availability
    annualised_capex = capex_total * crf(interest, plant_life_years)
    opex_electricity = sec_kwh_m3 * electricity_usd_per_kwh * annual_water_m3
    opex_membranes = capex_membranes / membrane_life_years
    opex_fixed = fixed_om_fraction * capex_total
    opex_total = opex_electricity + opex_membranes + opex_fixed
    total_per_m3 = (annualised_capex + opex_total) / annual_water_m3
    return dict(
        n_vessels=float(n_vessels), n_elements=float(n_elements),
        capex_per_m3_d=float(capex_total / plant_capacity_m3_d),
        capex_total_usd=float(capex_total),
        capex_membranes_usd=float(capex_membranes),
        capex_vessels_usd=float(capex_vessels),
        capex_pump_erd_usd=float(capex_pump_erd),
        power_kw=float(power_kw),
        water_cost_usd_per_m3=float(total_per_m3),
        capex_per_m3=float(annualised_capex / annual_water_m3),
        opex_electricity_per_m3=float(opex_electricity / annual_water_m3),
        opex_membranes_per_m3=float(opex_membranes / annual_water_m3),
        opex_fixed_per_m3=float(opex_fixed / annual_water_m3),
    )


# ---------------------------------------------------------------------------
# Demo / smoke check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"pi(35 g/L, vH) = {pa_to_bar(osmotic_pressure(35.0)):.2f} bar")
    print(f"pi(35 g/L, Pitzer) = {pa_to_bar(osmotic_pressure(35.0, use_pitzer=True)):.2f} bar")
    print(f"SEC_min ideal, r=0.5, vH = {sec_min_ideal(35.0, 0.5):.3f} kWh/m3")
    print(f"SEC_min ideal, r=0.5, Pitzer = {sec_min_ideal(35.0, 0.5, use_pitzer=True):.3f} kWh/m3")
    print(f"r_max ideal, 60 bar = {r_max_ideal(35.0, 60.0):.3f}")
    run = solve_vessel()
    print(f"Default vessel: recovery = {run['recovery']*100:.1f}%, "
          f"Cp = {run['cp_mixed_final']*1000:.0f} mg/L, "
          f"brine = {run['brine_kg_m3']:.1f} g/L, N = {run['n_steps']}, "
          f"converged = {run['converged']}, x_pinch = {run['x_pinch_m']}")
    sec = sec_with_erd(60.0, run["recovery"])
    print(f"SEC with ERD = {sec:.2f} kWh/m3; SEC_min actual = "
          f"{sec_min_actual(35.0, run['cp_mixed_final'], run['brine_kg_m3'], run['recovery']):.2f} kWh/m3")
    econ = economics(run, sec)
    print(f"CAPEX = ${econ['capex_per_m3_d']:.0f} per m3/d; water = ${econ['water_cost_usd_per_m3']:.2f}/m3")
