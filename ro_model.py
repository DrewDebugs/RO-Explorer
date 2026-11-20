"""RO Desalination Explorer: core model.

This module is the single source of truth for the physics. The same file is
checked by pytest (CPython) and fetched by the web page, which runs it in the
browser through Pyodide. It depends only on numpy.

Conventions
-----------
* Everything inside this module is SI: m, s, Pa, kg/m^3 (= g/L), mol/m^3, K.
  Conversions to engineering units (bar, LMH, LMH/bar, kWh/m^3, degC) happen
  only through the named helpers in the "Units" section.
* Salt is modelled as NaCl. Concentrations C are mass concentrations in kg/m^3.

Contents (grows milestone by milestone, see docs/ai-log/01-plan.md)
-------------------------------------------------------------------
M1  Units, osmotic pressure (van't Hoff and Pitzer), temperature correction
    factor, minimum specific energy SEC_min for ideal rejection.
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

R_GAS = 8.314462618  # J/(mol K), exact SI value (2019 redefinition)
M_NACL = 0.05844  # kg/mol, molar mass of NaCl (58.44 g/mol)
I_NACL = 2  # van't Hoff factor: NaCl -> Na+ + Cl-
RHO_WATER = 997.05  # kg/m^3, pure water at 25 degC (used only to estimate molality)
T_REF = 298.15  # K, 25 degC reference temperature
P_ATM = 101325.0  # Pa

# Pitzer parameters for aqueous NaCl at 25 degC (Pitzer & Mayorga 1973).
PITZER_BETA0 = 0.0765
PITZER_BETA1 = 0.2664
PITZER_CPHI = 0.00127
PITZER_APHI = 0.392  # Debye-Hueckel osmotic coefficient parameter, kg^0.5 mol^-0.5
PITZER_B = 1.2  # kg^0.5 mol^-0.5, universal Pitzer constant
PITZER_ALPHA = 2.0  # kg^0.5 mol^-0.5, for 1:1 electrolytes

# Temperature correction factor constants (Arrhenius form) for A and B.
# TODO-VERIFY: values as given in the membrane manufacturer's design manual
# (FilmTec form: 2640 K above 25 degC, 3020 K below). Listed in
# docs/sources-checklist.md for the user to confirm.
TCF_K_ABOVE = 2640.0  # K, used for T >= 25 degC
TCF_K_BELOW = 3020.0  # K, used for T < 25 degC

# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

PA_PER_BAR = 1.0e5
M_PER_S_PER_LMH = 1.0e-3 / 3600.0  # 1 L m^-2 h^-1 in m/s  (= 2.7778e-7)
J_PER_KWH = 3.6e6


def bar_to_pa(p_bar):
    """Pressure: bar -> Pa."""
    return np.asarray(p_bar, dtype=float) * PA_PER_BAR


def pa_to_bar(p_pa):
    """Pressure: Pa -> bar."""
    return np.asarray(p_pa, dtype=float) / PA_PER_BAR


def lmh_to_m_per_s(j_lmh):
    """Flux: L m^-2 h^-1 (LMH) -> m/s."""
    return np.asarray(j_lmh, dtype=float) * M_PER_S_PER_LMH


def m_per_s_to_lmh(j_si):
    """Flux: m/s -> LMH."""
    return np.asarray(j_si, dtype=float) / M_PER_S_PER_LMH


def lmh_per_bar_to_si(a_lmh_bar):
    """Water permeance A: LMH/bar -> m s^-1 Pa^-1 (1 LMH/bar = 2.7778e-12)."""
    return np.asarray(a_lmh_bar, dtype=float) * M_PER_S_PER_LMH / PA_PER_BAR


def si_to_lmh_per_bar(a_si):
    """Water permeance A: m s^-1 Pa^-1 -> LMH/bar."""
    return np.asarray(a_si, dtype=float) * PA_PER_BAR / M_PER_S_PER_LMH


def j_per_m3_to_kwh_per_m3(e_si):
    """Specific energy: J/m^3 (= Pa) -> kWh/m^3.  1 bar = 1/36 kWh/m^3."""
    return np.asarray(e_si, dtype=float) / J_PER_KWH


def kwh_per_m3_to_j_per_m3(e_kwh):
    """Specific energy: kWh/m^3 -> J/m^3."""
    return np.asarray(e_kwh, dtype=float) * J_PER_KWH


def celsius_to_kelvin(t_c):
    """Temperature: degC -> K."""
    return np.asarray(t_c, dtype=float) + 273.15


# ---------------------------------------------------------------------------
# Osmotic pressure
# ---------------------------------------------------------------------------


def molality_estimate(c):
    """Approximate NaCl molality (mol/kg water) from mass concentration (kg/m^3).

    Assumes 1 m^3 of solution contains RHO_WATER kg of water, i.e. it ignores
    the volume taken up by the salt. At 35 g/L this underestimates the true
    molality by about 2 % (documented limitation).
    """
    return np.asarray(c, dtype=float) / M_NACL / RHO_WATER


def osmotic_coefficient_pitzer(m):
    """Osmotic coefficient phi of aqueous NaCl at 25 degC (Pitzer model).

    For a 1:1 electrolyte (ionic strength I = m):

        phi - 1 = -A_phi sqrt(I) / (1 + b sqrt(I))
                  + m (beta0 + beta1 exp(-alpha sqrt(I)))
                  + m^2 C_phi

    Parameters are fixed at their 25 degC values; their temperature dependence
    is ignored (documented limitation).
    """
    m = np.asarray(m, dtype=float)
    sqrt_i = np.sqrt(m)
    debye_hueckel = -PITZER_APHI * sqrt_i / (1.0 + PITZER_B * sqrt_i)
    b_phi = PITZER_BETA0 + PITZER_BETA1 * np.exp(-PITZER_ALPHA * sqrt_i)
    return 1.0 + debye_hueckel + m * b_phi + m**2 * PITZER_CPHI


def osmotic_pressure_vant_hoff(c, T=T_REF):
    """Osmotic pressure (Pa) by van't Hoff: pi = i (C/M) R T.

    c : NaCl mass concentration, kg/m^3 (= g/L)
    T : temperature, K
    """
    return I_NACL * (np.asarray(c, dtype=float) / M_NACL) * R_GAS * T


def osmotic_pressure_pitzer(c, T=T_REF):
    """Osmotic pressure (Pa) with the Pitzer osmotic coefficient.

    pi = phi(m) * i * m * rho_w * R * T. With the molality estimate
    m = (C/M)/rho_w used here, this is exactly phi(m) times the van't Hoff value.
    """
    return osmotic_coefficient_pitzer(molality_estimate(c)) * osmotic_pressure_vant_hoff(c, T)


def osmotic_pressure(c, T=T_REF, model="vant_hoff"):
    """Osmotic pressure (Pa). model = 'vant_hoff' (default) or 'pitzer'."""
    if model == "vant_hoff":
        return osmotic_pressure_vant_hoff(c, T)
    if model == "pitzer":
        return osmotic_pressure_pitzer(c, T)
    raise ValueError(f"unknown osmotic pressure model: {model!r}")


# ---------------------------------------------------------------------------
# Temperature correction of membrane permeances
# ---------------------------------------------------------------------------


def temperature_correction_factor(T):
    """TCF for the water and salt permeances A and B (Arrhenius form).

        TCF = exp[K (1/T_ref - 1/T)],  A(T) = A_25 * TCF,  B(T) = B_25 * TCF

    TCF = 1 at 25 degC, > 1 above it, < 1 below it. K switches between
    TCF_K_ABOVE and TCF_K_BELOW at 25 degC (TODO-VERIFY constants above).
    The mass-transfer coefficient k is NOT corrected (documented limitation).
    """
    T = np.asarray(T, dtype=float)
    k = np.where(T >= T_REF, TCF_K_ABOVE, TCF_K_BELOW)
    return np.exp(k * (1.0 / T_REF - 1.0 / T))


# ---------------------------------------------------------------------------
# Minimum specific energy (reversible separation, ideal rejection)
# ---------------------------------------------------------------------------


def sec_min_vant_hoff(c_feed, recovery, T=T_REF):
    """Analytic reversible SEC (J/m^3 of permeate) for van't Hoff, ideal rejection.

        SEC_min = pi_f ln(1/(1 - r)) / r      (-> pi_f as r -> 0)
    """
    r = np.asarray(recovery, dtype=float)
    pi_f = osmotic_pressure_vant_hoff(c_feed, T)
    # -log1p(-r)/r is accurate also for very small r; its limit at r = 0 is 1.
    with np.errstate(divide="ignore", invalid="ignore"):
        factor = np.where(r > 0, -np.log1p(-r) / np.where(r > 0, r, 1.0), 1.0)
    return pi_f * factor


def sec_min(c_feed, recovery, T=T_REF, model="vant_hoff", n=128):
    """Reversible SEC (J/m^3 of permeate) for ideal rejection, any pi model.

        SEC_min = (1/r) * integral_0^r  pi(C_f / (1 - r')) dr'

    Pure water is removed reversibly while the brine concentrates; the work
    per unit permeate is the average osmotic pressure seen along the way.

    Numerical method: substitute u = -ln(1 - r'), so C = C_f e^u and
    dr' = e^-u du. The integral becomes (1/r) * integral_0^U pi(C_f e^u) e^-u du
    with U = -ln(1 - r). For van't Hoff the new integrand is the constant pi_f,
    and for Pitzer it is pi_f times a slowly varying phi, so composite
    Simpson's rule with n intervals is very accurate even at high recovery.
    """
    r = float(recovery)
    if not 0.0 <= r < 1.0:
        raise ValueError("recovery must be in [0, 1)")
    if r == 0.0:
        return float(osmotic_pressure(c_feed, T, model))
    if n % 2:
        n += 1
    u_end = -np.log1p(-r)
    u = np.linspace(0.0, u_end, n + 1)
    g = osmotic_pressure(c_feed * np.exp(u), T, model) * np.exp(-u)
    h = u_end / n
    simpson = h / 3.0 * (g[0] + g[-1] + 4.0 * g[1:-1:2].sum() + 2.0 * g[2:-1:2].sum())
    return float(simpson / r)
