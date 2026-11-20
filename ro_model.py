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
M2  Local solution-diffusion + film model at one point of the membrane.
M3  1D model of a pressure vessel (RK4 along x), convergence check, pinch.
M4  Energy (pump, ERD, minimum work) and a simple economics model.
    Plus the engineering-unit API used by the web page (`run_from_ui`).

Pressures: all pressures are gauge pressures (relative to the atmosphere).
The permeate leaves at atmospheric pressure (P_p = 0 gauge) unless stated.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

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
# FilmTec design equations (Dow Form No. 609-02057-604), Eq. 16a,b:
# 2640 K above 25 degC, 3020 K below. Verified by the student (S11).
# FilmTec's Eq. 19 applies the same TCF to salt passage, as done here for B.
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
    TCF_K_ABOVE and TCF_K_BELOW at 25 degC (FilmTec Eq. 16a,b).
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


# ---------------------------------------------------------------------------
# Fast scalar versions (used inside the solvers)
# ---------------------------------------------------------------------------
# The vessel model calls the osmotic pressure thousands of times with plain
# floats. Python's math module is much faster than numpy for single numbers,
# which matters in the browser. Tests check these against the numpy versions.

_VH_COEFF = I_NACL * R_GAS / M_NACL  # pi_vH = _VH_COEFF * C * T


def _phi_scalar(m):
    """osmotic_coefficient_pitzer for one float."""
    sqrt_i = math.sqrt(m)
    return (
        1.0
        - PITZER_APHI * sqrt_i / (1.0 + PITZER_B * sqrt_i)
        + m * (PITZER_BETA0 + PITZER_BETA1 * math.exp(-PITZER_ALPHA * sqrt_i))
        + m * m * PITZER_CPHI
    )


def _pi_scalar(c, T, pitzer):
    """osmotic_pressure for one float (Pa). pitzer: bool."""
    p = _VH_COEFF * c * T
    if pitzer and c > 0.0:
        p *= _phi_scalar(c / M_NACL / RHO_WATER)
    return p


def _check_model(model):
    if model not in ("vant_hoff", "pitzer"):
        raise ValueError(f"unknown osmotic pressure model: {model!r}")
    return model == "pitzer"


# ---------------------------------------------------------------------------
# M2: local solution-diffusion + film model
# ---------------------------------------------------------------------------


@dataclass
class LocalSolution:
    """Result of the local membrane problem at one position (SI units)."""

    J_w: float  # water flux, m/s
    C_m: float  # concentration at the membrane surface, kg/m^3
    C_p: float  # local permeate concentration, kg/m^3
    J_s: float  # salt flux, kg m^-2 s^-1
    iterations: int  # root-finder iterations used
    residual: float  # |f(J_w)| at the solution, m/s


def local_concentrations(J_w, C_b, B, k):
    """C_p and C_m for a GIVEN water flux (closed form).

    From  J_s = B (C_m - C_p),  C_p = J_s / J_w  and the film model
    C_m = C_p + (C_b - C_p) exp(J_w / k), with E = exp(J_w / k):

        C_p = B E C_b / (J_w + B E)
        C_m = C_p + (C_b - C_p) E

    For B = 0 (ideal membrane) C_p = 0. At J_w = 0 with B > 0, C_p = C_b
    (with no water flow the membrane passes salt unhindered).
    """
    E = math.exp(min(J_w / k, 700.0))  # k may be math.inf -> E = 1
    if B == 0.0:
        C_p = 0.0
    else:
        C_p = B * E * C_b / (J_w + B * E)
    C_m = C_p + (C_b - C_p) * E
    return C_p, C_m


def solve_local(C_b, dP, A, B, k, T=T_REF, model="vant_hoff", ftol=1e-16, maxiter=100):
    """Solve the local membrane problem for J_w, C_m, C_p.

    C_b   bulk feed-side concentration, kg/m^3
    dP    transmembrane hydraulic pressure P - P_p, Pa
    A     water permeance, m s^-1 Pa^-1;  B salt permeance, m/s
    k     film mass-transfer coefficient, m/s (math.inf = no polarisation)

    The problem reduces to one equation in J_w:

        f(J_w) = J_w - A [dP - pi(C_m(J_w)) + pi(C_p(J_w))] = 0

    Bracket: for B > 0, f(0+) = -A dP < 0 and f(A dP) = A (pi_m - pi_p) >= 0,
    so a root always lies in (0, A dP]. For B = 0, if dP <= pi(C_b) the flux is
    exactly zero (the pinch). The root is found with the Illinois method
    (regula falsi with the stale end-point halved), falling back to a
    bisection step whenever the bracket fails to halve in two steps.
    """
    pitzer = _check_model(model)

    def f(J):
        C_p, C_m = local_concentrations(J, C_b, B, k)
        return J - A * (dP - _pi_scalar(C_m, T, pitzer) + _pi_scalar(C_p, T, pitzer))

    if dP <= 0.0 or A <= 0.0:
        return LocalSolution(0.0, C_b, C_b if B > 0 else 0.0, 0.0, 0, 0.0)

    a, b = 0.0, A * dP
    if B == 0.0:
        fa = -A * (dP - _pi_scalar(C_b, T, pitzer))
        if fa >= 0.0:  # applied pressure cannot beat the bulk osmotic pressure
            return LocalSolution(0.0, C_b, 0.0, 0.0, 0, 0.0)
    else:
        fa = -A * dP
    fb = f(b)

    it = 0
    if fb <= 0.0:  # only when pi_m = pi_p (e.g. C_b = 0): J_w = A dP exactly
        J, fJ = b, fb
    else:
        side = 0
        width_old = b - a
        J, fJ = b, fb
        for it in range(1, maxiter + 1):
            J = b - fb * (b - a) / (fb - fa)
            if not a < J < b:
                J = 0.5 * (a + b)
            fJ = f(J)
            if fJ == 0.0:
                break
            if fJ < 0.0:
                a, fa = J, fJ
                if side == -1:
                    fb *= 0.5
                side = -1
            else:
                b, fb = J, fJ
                if side == +1:
                    fa *= 0.5
                side = +1
            if abs(fJ) <= ftol or (b - a) <= 4e-16 * b:
                break
            if it % 2 == 0:  # safeguard: force a bisection if the bracket stalls
                if (b - a) > 0.25 * width_old:
                    J = 0.5 * (a + b)
                    fJ = f(J)
                    if fJ < 0.0:
                        a, fa = J, fJ
                    else:
                        b, fb = J, fJ
                    side = 0
                width_old = b - a
    C_p, C_m = local_concentrations(J, C_b, B, k)
    return LocalSolution(J, C_m, C_p, B * (C_m - C_p), it, abs(fJ))


# ---------------------------------------------------------------------------
# M3: 1D pressure-vessel model
# ---------------------------------------------------------------------------


@dataclass
class VesselInputs:
    """Inputs for one pressure vessel, SI units. Defaults = seawater preset."""

    C_f: float = 35.0  # feed concentration, kg/m^3
    P_f: float = 60.0e5  # feed pressure (gauge), Pa
    Q_f: float = 12.0 / 3600.0  # feed flow per vessel, m^3/s
    T: float = T_REF  # K
    A25: float = 1.4 * 2.7777777777777777e-12  # water permeance at 25 degC, m s^-1 Pa^-1 (fitted to FilmTec SW30HRLE-440)
    B25: float = 0.05 / 3.6e6  # salt permeance at 25 degC, m/s (fitted to FilmTec SW30HRLE-440)
    k: float = 180.0 / 3.6e6  # mass-transfer coefficient, m/s
    n_elements: int = 7
    area_element: float = 40.9  # m^2 (440 ft^2)
    length_element: float = 1.016  # m (40 in)
    dP_drop: float = 1.5e5  # feed-side pressure drop over the whole vessel, Pa
    P_p: float = 0.0  # permeate pressure (gauge), Pa
    model: str = "vant_hoff"  # osmotic pressure model

    @property
    def length(self):
        return self.n_elements * self.length_element

    @property
    def area(self):
        return self.n_elements * self.area_element

    @property
    def A(self):
        return self.A25 * float(temperature_correction_factor(self.T))

    @property
    def B(self):
        return self.B25 * float(temperature_correction_factor(self.T))


@dataclass
class VesselResult:
    """Profiles along the vessel (arrays) and summary numbers (SI)."""

    x: np.ndarray
    Q: np.ndarray  # feed-side flow, m^3/s
    C_b: np.ndarray  # bulk concentration, kg/m^3
    P: np.ndarray  # feed-side pressure, Pa
    Q_p: np.ndarray  # cumulative permeate flow, m^3/s
    S_p: np.ndarray  # cumulative permeate salt flow, kg/s
    J_w: np.ndarray  # local water flux, m/s
    C_m: np.ndarray
    C_p: np.ndarray  # local permeate concentration
    NDP: np.ndarray  # net driving pressure, Pa
    pi_b: np.ndarray
    pi_m: np.ndarray
    pi_p: np.ndarray
    recovery: float
    C_p_mixed: float  # mixed permeate concentration, kg/m^3
    rejection: float  # observed rejection 1 - C_p_mixed / C_f
    C_b_out: float
    P_out: float
    N: int  # RK4 steps used
    converged: bool
    x_pinch: float | None  # first position where J_w < 1 % of its inlet value

    @property
    def cp_factor(self):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.C_b > 0, self.C_m / np.where(self.C_b > 0, self.C_b, 1), 1.0)


def _rk4_vessel(inp: VesselInputs, N: int):
    """Integrate the vessel balances with classical RK4 and N uniform steps.

    State y = [Q, S, Q_p, S_p, P] with S = Q C_b (salt mass flow):
        dQ/dx = -J_w W,   dS/dx = -J_w C_p W
        dQ_p/dx = +J_w W, dS_p/dx = +J_w C_p W
        dP/dx = -dP_drop / L
    W = A_m / L is the membrane width per unit length.
    """
    L = inp.length
    W = inp.area / L
    A, B, k, T = inp.A, inp.B, inp.k, inp.T
    drop = inp.dP_drop / L
    Q_min = 1e-12 * inp.Q_f

    def rhs(y):
        Q, S, _, _, P = y
        if Q <= Q_min:
            return (0.0, 0.0, 0.0, 0.0, -drop)
        C_b = max(S / Q, 0.0)
        sol = solve_local(C_b, P - inp.P_p, A, B, k, T, inp.model)
        dq = sol.J_w * W
        ds = sol.J_w * sol.C_p * W
        return (-dq, -ds, dq, ds, -drop)

    h = L / N
    y = np.empty((N + 1, 5))
    y[0] = (inp.Q_f, inp.Q_f * inp.C_f, 0.0, 0.0, inp.P_f)
    cur = tuple(y[0])
    for i in range(N):
        k1 = rhs(cur)
        k2 = rhs(tuple(c + 0.5 * h * d for c, d in zip(cur, k1)))
        k3 = rhs(tuple(c + 0.5 * h * d for c, d in zip(cur, k2)))
        k4 = rhs(tuple(c + h * d for c, d in zip(cur, k3)))
        cur = tuple(
            c + h / 6.0 * (d1 + 2.0 * d2 + 2.0 * d3 + d4)
            for c, d1, d2, d3, d4 in zip(cur, k1, k2, k3, k4)
        )
        y[i + 1] = cur
    return np.linspace(0.0, L, N + 1), y


def _summary(inp, y):
    Q_out, S_out, Q_p, S_p, P_out = y[-1]
    r = Q_p / inp.Q_f
    C_p_mixed = S_p / Q_p if Q_p > 0 else 0.0
    C_b_out = S_out / Q_out if Q_out > 0 else float("inf")
    return r, C_p_mixed, C_b_out, P_out


def simulate_vessel(inp: VesselInputs, N: int = 50, rtol: float = 1e-4, N_max: int = 3200,
                    fixed_N: bool = False):
    """Solve the vessel and check grid convergence automatically.

    Solve with N and 2N steps and compare recovery, mixed permeate
    concentration and brine concentration. If the largest relative change is
    above rtol, double N and repeat (up to N_max). The finer solution is
    returned with `converged` saying whether rtol was met.
    With fixed_N=True a single run with N steps is returned (no check).
    """
    _check_model(inp.model)
    if fixed_N:
        x, y = _rk4_vessel(inp, N)
        converged = False
    else:
        x, y = _rk4_vessel(inp, N)
        s_old = _summary(inp, y)
        converged = False
        while True:
            N *= 2
            x, y = _rk4_vessel(inp, N)
            s_new = _summary(inp, y)
            change = max(
                abs(a - b) / max(abs(b), 1e-30) for a, b in zip(s_old[:3], s_new[:3])
            )
            if change <= rtol:
                converged = True
                break
            if N >= N_max:
                break
            s_old = s_new
    return _profiles(inp, x, y, N, converged)


def _profiles(inp, x, y, N, converged):
    """Evaluate local quantities at every grid node and build a VesselResult."""
    pitzer = inp.model == "pitzer"
    Q, S, Q_p, S_p, P = y.T
    n = len(x)
    C_b = np.where(Q > 0, S / np.where(Q > 0, Q, 1.0), np.inf)
    J = np.empty(n)
    C_m = np.empty(n)
    C_pl = np.empty(n)
    A, B, k, T = inp.A, inp.B, inp.k, inp.T
    for i in range(n):
        if not math.isfinite(C_b[i]):  # feed fully recovered (degenerate case)
            J[i], C_m[i], C_pl[i] = 0.0, np.inf, np.nan
            continue
        sol = solve_local(float(C_b[i]), float(P[i] - inp.P_p), A, B, k, T, inp.model)
        J[i], C_m[i], C_pl[i] = sol.J_w, sol.C_m, sol.C_p
    pi_b = np.array([_pi_scalar(c, T, pitzer) for c in C_b])
    pi_m = np.array([_pi_scalar(c, T, pitzer) for c in C_m])
    pi_p = np.array([_pi_scalar(c, T, pitzer) for c in C_pl])
    NDP = (P - inp.P_p) - (pi_m - pi_p)
    r, C_p_mixed, C_b_out, P_out = _summary(inp, y)
    x_pinch = None
    if J[0] > 0:
        below = np.nonzero(J < 0.01 * J[0])[0]
        if below.size:
            i = below[0]
            # linear interpolation between the last node above and the first below
            j0, j1 = J[i - 1], J[i]
            target = 0.01 * J[0]
            x_pinch = float(x[i - 1] + (x[i] - x[i - 1]) * (j0 - target) / (j0 - j1))
    return VesselResult(
        x=x, Q=Q, C_b=C_b, P=P, Q_p=Q_p, S_p=S_p, J_w=J, C_m=C_m, C_p=C_pl, NDP=NDP,
        pi_b=pi_b, pi_m=pi_m, pi_p=pi_p, recovery=float(r), C_p_mixed=float(C_p_mixed),
        rejection=float(1.0 - C_p_mixed / inp.C_f) if inp.C_f > 0 else 1.0,
        C_b_out=float(C_b_out), P_out=float(P_out), N=N, converged=converged,
        x_pinch=x_pinch,
    )


def r_max_ideal(c_feed, dP, T=T_REF, model="vant_hoff"):
    """Thermodynamic recovery limit of one stage (ideal rejection, no CP).

    Flux stops where the brine osmotic pressure reaches the applied pressure:
    pi(C_f / (1 - r)) = dP. For van't Hoff, r_max = 1 - pi_f / dP. For Pitzer
    the equation is solved by bisection. Returns 0 if dP <= pi_f.
    """
    pitzer = _check_model(model)
    pi_f = _pi_scalar(c_feed, T, pitzer)
    if dP <= pi_f:
        return 0.0
    if not pitzer:
        return 1.0 - pi_f / dP
    lo, hi = 0.0, 1.0 - 1e-12
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _pi_scalar(c_feed / (1.0 - mid), T, True) < dP:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# M4: energy
# ---------------------------------------------------------------------------


def sec_pump(P_f, recovery, eta_pump):
    """Pump SEC without energy recovery (J/m^3 permeate).

    The high-pressure pump lifts all the feed from 0 to P_f (gauge):
        SEC = P_f / (eta_p r)
    """
    return P_f / (eta_pump * recovery)


def sec_erd(P_f, P_b, recovery, eta_pump, eta_erd, P_p=0.0):
    """Pump SEC with an isobaric energy-recovery device (J/m^3 permeate).

    The ERD returns eta_erd of the brine's pressure energy (1 - r)(P_b - P_p)
    to the feed, so the pumps only supply the rest:
        SEC = [P_f - eta_erd (1 - r)(P_b - P_p)] / (eta_p r)
    Booster pump losses are ignored (documented simplification).
    """
    return (P_f - eta_erd * (1.0 - recovery) * (P_b - P_p)) / (eta_pump * recovery)


def sec_single_stage_bound(c_feed, recovery, T=T_REF, model="vant_hoff"):
    """Least pressure a single stage needs: brine osmotic pressure at the outlet,
    pi(C_f / (1 - r)); equals pi_f / (1 - r) for van't Hoff (J/m^3)."""
    return float(osmotic_pressure(c_feed / (1.0 - recovery), T, model))


def free_energy_density(c, T=T_REF, model="vant_hoff", n=64):
    """Free-energy density g(c) consistent with pi(c) (J/m^3, dilute solution).

    g(c) = c * integral_{c_ref}^{c} pi(c') / c'^2 dc'  satisfies
    pi = c g'(c) - g(c). With pi = a c phi(c) (a = i R T / M):

        g(c) = a c [ ln(c / c_ref) + integral_0^c (phi(c') - 1) / c' dc' ]

    c_ref = 1 kg/m^3; the terms linear in c cancel in any salt-conserving
    balance. The excess integral uses c' = c t^2, which makes the integrand
    smooth: 2 (phi(c t^2) - 1) / t, integrated by Simpson's rule on [0, 1].
    """
    pitzer = _check_model(model)
    if c <= 0.0:
        return 0.0
    a = _VH_COEFF * T
    g = math.log(c)
    if pitzer:
        mol = c / M_NACL / RHO_WATER
        if n % 2:
            n += 1
        t = np.linspace(0.0, 1.0, n + 1)
        vals = np.empty(n + 1)
        vals[0] = -2.0 * PITZER_APHI * math.sqrt(mol)  # limit t -> 0
        vals[1:] = 2.0 * (osmotic_coefficient_pitzer(mol * t[1:] ** 2) - 1.0) / t[1:]
        hh = 1.0 / n
        g += hh / 3.0 * (vals[0] + vals[-1] + 4 * vals[1:-1:2].sum() + 2 * vals[2:-1:2].sum())
    return a * c * g


def sec_min_actual(c_feed, c_perm, c_brine, recovery, T=T_REF, model="vant_hoff"):
    """Minimum work for the separation the membrane ACTUALLY makes (J/m^3 permeate).

    W_min / V_p = [r g(C_p) + (1 - r) g(C_b) - g(C_f)] / r

    For C_p -> 0 this equals the ideal-rejection SEC_min. A leaky membrane
    makes impure permeate, so its bound can be below the ideal SEC_min.
    """
    r = recovery
    w = (r * free_energy_density(c_perm, T, model)
         + (1.0 - r) * free_energy_density(c_brine, T, model)
         - free_energy_density(c_feed, T, model))
    return w / r


# ---------------------------------------------------------------------------
# M4: economics (teaching model, all inputs editable)
# ---------------------------------------------------------------------------


@dataclass
class EconomicsInputs:
    """Plant-level cost inputs. Values marked TODO-VERIFY in the sources checklist."""

    capacity: float = 100_000.0  # m^3/d design permeate capacity
    availability: float = 0.95  # fraction of the year the plant produces
    electricity_price: float = 0.096  # $/kWh (EIA Table 5.6.A, U.S. industrial average, S21)
    membrane_cost: float = 1000.0  # $ per 8-inch element (retail listing, S22)
    vessel_cost: float = 2700.0  # $ per pressure vessel (list price, S23)
    pump_erd_cost: float = 400.0  # $ per kW of HP pump + ERD (calibrated: 2.6 % of CAPEX, S24)
    other_multiplier: float = 12.5  # total plant CAPEX / RO-train equipment CAPEX (calibrated: membranes 3.9 % of CAPEX, S25)
    interest: float = 0.08  # 1/yr
    plant_life: float = 25.0  # yr
    membrane_life: float = 5.0  # yr
    om_fraction: float = 0.045  # fixed O&M per year, fraction of CAPEX (calibrated: energy 45 % of OPEX, S26)


def capital_recovery_factor(i, n):
    """CRF = i (1+i)^n / ((1+i)^n - 1); n/a for i = 0 -> 1/n."""
    if i == 0:
        return 1.0 / n
    g = (1.0 + i) ** n
    return i * g / (g - 1.0)


def water_cost(sec_kwh_m3, vessel_permeate_m3h, n_elements, eco: EconomicsInputs):
    """Levelised water cost ($/m^3) and its breakdown.

    n_vessels = ceil(capacity / (vessel permeate x 24 h))
    CAPEX     = (membranes + vessels + pump/ERD power x $/kW) x other_multiplier
    capital   = CRF x CAPEX / annual production
    energy    = SEC x electricity price
    membranes = membrane set cost / membrane life / annual production
    O&M       = om_fraction x CAPEX / annual production
    """
    if vessel_permeate_m3h <= 0:
        raise ValueError("the vessel produces no permeate")
    n_vessels = math.ceil(eco.capacity / (vessel_permeate_m3h * 24.0) - 1e-9)
    n_el = n_vessels * n_elements
    power_kw = sec_kwh_m3 * eco.capacity / 24.0
    capex_membranes = n_el * eco.membrane_cost
    capex_vessels = n_vessels * eco.vessel_cost
    capex_pumps = power_kw * eco.pump_erd_cost
    capex_total = (capex_membranes + capex_vessels + capex_pumps) * eco.other_multiplier
    annual = eco.capacity * 365.0 * eco.availability
    crf = capital_recovery_factor(eco.interest, eco.plant_life)
    parts = {
        "capital": crf * capex_total / annual,
        "energy": sec_kwh_m3 * eco.electricity_price,
        "membrane_replacement": capex_membranes / eco.membrane_life / annual,
        "fixed_om": eco.om_fraction * capex_total / annual,
    }
    return {
        "total": sum(parts.values()),
        "parts": parts,
        "n_vessels": n_vessels,
        "n_elements": n_el,
        "power_kw": power_kw,
        "capex_total": capex_total,
        "capex_per_m3d": capex_total / eco.capacity,
        "crf": crf,
        "annual_m3": annual,
    }


# ---------------------------------------------------------------------------
# Engineering-unit API used by the web page
# ---------------------------------------------------------------------------

UI_DEFAULTS = {
    # vessel
    "C_f": 35.0,  # g/L
    "P_f": 60.0,  # bar
    "Q_f": 12.0,  # m^3/h per vessel
    "T": 25.0,  # degC
    "A": 1.4,  # LMH/bar at 25 degC (datasheet fit, see sources checklist S12)
    "B": 0.05,  # LMH at 25 degC (datasheet fit, S13)
    "k": 180.0,  # LMH
    "n_elements": 7,
    "dP_drop": 1.5,  # bar per vessel
    "pressure_drop_on": True,
    "pitzer": False,
    # energy
    "eta_pump": 0.80,
    "eta_erd": 0.95,
    "erd_on": True,
    # economics
    "capacity": 100_000.0,
    "availability": 0.95,
    "electricity_price": 0.096,
    "membrane_cost": 1000.0,
    "vessel_cost": 2700.0,
    "pump_erd_cost": 400.0,
    "other_multiplier": 12.5,
    "interest": 8.0,  # %
    "plant_life": 25.0,
    "membrane_life": 5.0,
    "om_fraction": 4.5,  # % of CAPEX per year
}

# Thresholds for warnings on the page.
ELEMENT_MAX_PRESSURE_BAR = 83.0  # FilmTec SW30HRLE-440 datasheet: 1,200 psig (83 bar); verified (S10)
BRINE_GUIDELINE_GL = 70.0  # TODO-VERIFY: teaching threshold for brine/scaling concern
CP_GUIDELINE = 1.2  # teaching threshold; FilmTec's correlation exp(0.7*Y_i) gives ~1.06 for a typical element


def inputs_from_ui(ui):
    """Convert a dict of engineering-unit inputs (see UI_DEFAULTS) to VesselInputs."""
    u = {**UI_DEFAULTS, **ui}
    return VesselInputs(
        C_f=float(u["C_f"]),
        P_f=float(u["P_f"]) * PA_PER_BAR,
        Q_f=float(u["Q_f"]) / 3600.0,
        T=float(u["T"]) + 273.15,
        A25=float(u["A"]) * M_PER_S_PER_LMH / PA_PER_BAR,
        B25=float(u["B"]) * M_PER_S_PER_LMH,
        k=float(u["k"]) * M_PER_S_PER_LMH,
        n_elements=int(u["n_elements"]),
        dP_drop=float(u["dP_drop"]) * PA_PER_BAR if u["pressure_drop_on"] else 0.0,
        model="pitzer" if u["pitzer"] else "vant_hoff",
    )


def economics_from_ui(ui):
    u = {**UI_DEFAULTS, **ui}
    return EconomicsInputs(
        capacity=float(u["capacity"]),
        availability=float(u["availability"]),
        electricity_price=float(u["electricity_price"]),
        membrane_cost=float(u["membrane_cost"]),
        vessel_cost=float(u["vessel_cost"]),
        pump_erd_cost=float(u["pump_erd_cost"]),
        other_multiplier=float(u["other_multiplier"]),
        interest=float(u["interest"]) / 100.0,
        plant_life=float(u["plant_life"]),
        membrane_life=float(u["membrane_life"]),
        om_fraction=float(u["om_fraction"]) / 100.0,
    )


def energy_summary(inp: VesselInputs, res: VesselResult, eta_pump, eta_erd):
    """All SEC numbers in kWh/m^3 for the bar chart."""
    r = res.recovery
    kwh = lambda e: float(e) / J_PER_KWH  # noqa: E731
    out = {
        "no_erd": kwh(sec_pump(inp.P_f, r, eta_pump)) if r > 0 else None,
        "erd": kwh(sec_erd(inp.P_f, res.P_out, r, eta_pump, eta_erd, inp.P_p)) if r > 0 else None,
        "min_ideal": kwh(sec_min(inp.C_f, r, inp.T, inp.model)) if 0 < r < 1 else None,
        "min_actual": None,
        "single_stage": kwh(sec_single_stage_bound(inp.C_f, r, inp.T, inp.model)) if 0 < r < 1 else None,
    }
    if 0 < r < 1:
        out["min_actual"] = kwh(sec_min_actual(inp.C_f, res.C_p_mixed, res.C_b_out, r, inp.T, inp.model))
    return out


def check_warnings(inp: VesselInputs, res: VesselResult | None = None):
    """Warnings shown on the page. Returns a list of (level, message)."""
    w = []
    pitzer = inp.model == "pitzer"
    pi_f = _pi_scalar(inp.C_f, inp.T, pitzer)
    dP = inp.P_f - inp.P_p
    if dP <= pi_f:
        w.append(("error", f"Feed pressure ({dP/1e5:.1f} bar) is at or below the feed osmotic "
                           f"pressure ({pi_f/1e5:.1f} bar): no useful production. A leaky membrane "
                           f"still passes some water, but it carries almost all the salt."))
    if inp.P_f / 1e5 > ELEMENT_MAX_PRESSURE_BAR:
        w.append(("warn", f"Feed pressure is above the ~{ELEMENT_MAX_PRESSURE_BAR:.0f} bar limit of "
                          f"typical seawater RO elements."))
    if res is not None and dP > pi_f:
        r_max = r_max_ideal(inp.C_f, dP - inp.dP_drop, inp.T, inp.model)
        if r_max > 0 and res.recovery > 0.9 * r_max:
            w.append(("warn", f"Recovery ({100*res.recovery:.1f} %) is above 90 % of the "
                              f"thermodynamic limit r_max ≈ {100*r_max:.1f} %: the vessel is close "
                              f"to the pinch, and extra membrane area adds little water."))
        if res.recovery > 0.95:
            w.append(("warn", f"Recovery is {100*res.recovery:.1f} %: almost all the feed passes the "
                              f"membrane. This is far outside normal operation (scaling would stop it) "
                              f"and the model's assumptions break down."))
        if res.x_pinch is not None:
            w.append(("warn", f"Pinch: the local flux falls below 1 % of its inlet value at "
                              f"x ≈ {res.x_pinch:.2f} m. Membrane downstream of this point "
                              f"produces almost nothing."))
        if res.C_b_out > BRINE_GUIDELINE_GL:
            w.append(("warn", f"Brine leaves at {res.C_b_out:.0f} g/L, above the {BRINE_GUIDELINE_GL:.0f} g/L "
                              f"teaching threshold: scaling and brine disposal become concerns "
                              f"(not modelled)."))
        cp_max = float(np.nanmax(res.cp_factor))
        if cp_max > CP_GUIDELINE:
            w.append(("info", f"Concentration polarisation factor reaches {cp_max:.2f}, which is high: "
                              f"FilmTec's design correlation gives about 1.06 for a typical 8-inch element."))
        if not res.converged:
            w.append(("info", f"Grid convergence check did not reach the tolerance (N = {res.N})."))
    return w


def _downsample(a, n_max=201):
    a = np.asarray(a, dtype=float)
    if len(a) <= n_max:
        idx = np.arange(len(a))
    else:
        idx = np.unique(np.round(np.linspace(0, len(a) - 1, n_max)).astype(int))
    return [None if not math.isfinite(v) else float(v) for v in a[idx]]


def run_from_ui(params_json: str) -> str:
    """Run everything the page shows, in engineering units. JSON in, JSON out.

    Units out: x in m, pressures in bar, flux in LMH, concentrations in g/L,
    flows in m^3/h, energy in kWh/m^3, costs in $/m^3.
    """
    ui = {**UI_DEFAULTS, **json.loads(params_json)}
    inp = inputs_from_ui(ui)
    res = simulate_vessel(inp)
    out = {
        "inputs_si": asdict(inp),
        "summary": {
            "recovery": res.recovery,
            "permeate_m3h": float(res.Q_p[-1] * 3600.0),
            "C_p_mixed": res.C_p_mixed,
            "rejection": res.rejection,
            "C_b_out": res.C_b_out,
            "P_out_bar": res.P_out / 1e5,
            "avg_flux_lmh": float(res.Q_p[-1] / inp.area / M_PER_S_PER_LMH),
            "pi_f_bar": _pi_scalar(inp.C_f, inp.T, inp.model == "pitzer") / 1e5,
            "r_max": r_max_ideal(inp.C_f, inp.P_f - inp.P_p - inp.dP_drop, inp.T, inp.model),
            "N": res.N,
            "converged": res.converged,
            "x_pinch": res.x_pinch,
            "A_T": float(si_to_lmh_per_bar(inp.A)),
            "B_T": float(m_per_s_to_lmh(inp.B)),
        },
        "profiles": {
            "x": _downsample(res.x),
            "J_w": _downsample(m_per_s_to_lmh(res.J_w)),
            "NDP": _downsample(res.NDP / 1e5),
            "C_b": _downsample(res.C_b),
            "C_m": _downsample(res.C_m),
            "C_p": _downsample(res.C_p),
            "P": _downsample(res.P / 1e5),
            "pi_b": _downsample(res.pi_b / 1e5),
            "pi_m": _downsample(res.pi_m / 1e5),
            "pi_p": _downsample(res.pi_p / 1e5),
            "cp": _downsample(res.cp_factor),
        },
        "warnings": [{"level": lv, "text": t} for lv, t in check_warnings(inp, res)],
    }
    energy = energy_summary(inp, res, float(ui["eta_pump"]), float(ui["eta_erd"]))
    out["energy"] = energy
    sec_used = energy["erd"] if ui["erd_on"] else energy["no_erd"]
    if res.Q_p[-1] > 0 and sec_used is not None:
        cost = water_cost(sec_used, float(res.Q_p[-1] * 3600.0), inp.n_elements,
                          economics_from_ui(ui))
        out["economics"] = cost
    else:
        out["economics"] = None
    return json.dumps(out)


def pressure_sweep(params_json: str, n: int = 25) -> str:
    """Recovery and rejection vs feed pressure (the 'pinch picture'). JSON out.

    Uses a fixed RK4 grid (N = 100) for speed; the r_max curve is the ideal
    single-stage limit evaluated at the same pressures.
    """
    ui = {**UI_DEFAULTS, **json.loads(params_json)}
    base = inputs_from_ui(ui)
    pitzer = base.model == "pitzer"
    pi_f = _pi_scalar(base.C_f, base.T, pitzer) / 1e5
    p_lo = max(1.0, 0.6 * pi_f)
    p_hi = max(ui["P_f"] * 1.3, pi_f * 2.5, 20.0)
    p_hi = min(p_hi, 120.0)
    P = np.linspace(p_lo, p_hi, n)
    rec, rej, rmax = [], [], []
    for p in P:
        inp = inputs_from_ui({**ui, "P_f": float(p)})
        res = simulate_vessel(inp, N=100, fixed_N=True)
        rec.append(res.recovery)
        rej.append(res.rejection)
        rmax.append(r_max_ideal(base.C_f, p * 1e5 - inp.dP_drop, base.T, base.model))
    return json.dumps({"P": P.tolist(), "recovery": rec, "rejection": rej, "r_max": rmax,
                       "pi_f": pi_f})
