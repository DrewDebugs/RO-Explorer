"""Independent reference implementation of the RO vessel model (CPython + SciPy).

Written separately from ro_model.py and sharing no code with it: the osmotic
pressure, the local membrane problem and the vessel balances are re-implemented
here from the equations in docs/ai-log/01-plan.md (section 3), using
scipy.optimize.brentq for the local solve and scipy.integrate.solve_ivp
(DOP853, adaptive step) for the balances along the vessel.

It also contains a closed-form solution for the ideal case (B = 0, no
concentration polarisation, no pressure drop, van't Hoff), derived by hand:

    dQ/da = -A (dP - pi_f Q_f / Q)       (a = membrane area so far)
    => Q + K ln(Q - K) = Q_f + K ln(Q_f - K) - A dP a,   K = pi_f Q_f / dP

Inputs are a plain dict of SI values with the same keys as ro_model.VesselInputs.
"""

import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

R = 8.314462618
M = 0.05844
RHO_W = 997.05


def osmotic_pressure(c, T, pitzer):
    """pi in Pa for NaCl at mass concentration c (kg/m^3)."""
    if c <= 0:
        return 0.0
    pi_ideal = 2.0 * c / M * R * T
    if not pitzer:
        return pi_ideal
    mol = c / M / RHO_W
    s = math.sqrt(mol)
    phi = 1 - 0.392 * s / (1 + 1.2 * s) + mol * (0.0765 + 0.2664 * math.exp(-2 * s)) + 0.00127 * mol**2
    return phi * pi_ideal


def permeance_factor(T):
    k = 2640.0 if T >= 298.15 else 3020.0
    return math.exp(k * (1 / 298.15 - 1 / T))


def local_flux(C_b, dP, A, B, k, T, pitzer):
    """Return (J_w, C_m, C_p) using brentq on the water-flux equation."""
    if dP <= 0:
        return 0.0, C_b, (C_b if B > 0 else 0.0)

    def conc(J):
        E = math.exp(J / k) if math.isfinite(k) else 1.0
        Cp = 0.0 if B == 0 else B * E * C_b / (J + B * E)
        return Cp, Cp + (C_b - Cp) * E

    def g(J):
        Cp, Cm = conc(J)
        return J - A * (dP - osmotic_pressure(Cm, T, pitzer) + osmotic_pressure(Cp, T, pitzer))

    if B == 0 and dP <= osmotic_pressure(C_b, T, pitzer):
        return 0.0, C_b, 0.0
    hi = A * dP
    if g(hi) <= 0:
        J = hi
    else:
        J = brentq(g, 1e-300, hi, xtol=1e-300, rtol=4 * np.finfo(float).eps, maxiter=500)
    Cp, Cm = conc(J)
    return J, Cm, Cp


def solve_vessel(p, x_eval):
    """Integrate the balances with solve_ivp. Returns dict of arrays at x_eval."""
    pitzer = p["model"] == "pitzer"
    L = p["n_elements"] * p["length_element"]
    W = p["n_elements"] * p["area_element"] / L
    f = permeance_factor(p["T"])
    A, B = p["A25"] * f, p["B25"] * f

    def rhs(x, y):
        Q, S, Qp, Sp, P = y
        J, Cm, Cp = local_flux(max(S / Q, 0.0), P - p["P_p"], A, B, p["k"], p["T"], pitzer)
        return [-J * W, -J * Cp * W, J * W, J * Cp * W, -p["dP_drop"] / L]

    y0 = [p["Q_f"], p["Q_f"] * p["C_f"], 0.0, 0.0, p["P_f"]]
    sol = solve_ivp(rhs, (0.0, L), y0, method="DOP853", t_eval=x_eval,
                    rtol=1e-12, atol=[1e-16, 1e-16, 1e-16, 1e-16, 1e-6])
    assert sol.success, sol.message
    Q, S, Qp, Sp, P = sol.y
    Cb = S / Q
    loc = [local_flux(c, pp - p["P_p"], A, B, p["k"], p["T"], pitzer) for c, pp in zip(Cb, P)]
    J = np.array([v[0] for v in loc])
    Cp = np.array([v[2] for v in loc])
    return {"x": sol.t, "Q": Q, "C_b": Cb, "P": P, "Q_p": Qp, "S_p": Sp, "J_w": J, "C_p": Cp,
            "nfev": sol.nfev}


def ideal_vessel_analytic(p, x_eval):
    """Closed-form Q(x) for B = 0, k = inf, no pressure drop, van't Hoff."""
    L = p["n_elements"] * p["length_element"]
    W = p["n_elements"] * p["area_element"] / L
    A = p["A25"] * permeance_factor(p["T"])
    dP = p["P_f"] - p["P_p"]
    pi_f = osmotic_pressure(p["C_f"], p["T"], False)
    Qf = p["Q_f"]
    K = pi_f * Qf / dP
    lhs0 = Qf + K * math.log(Qf - K)
    out = []
    for x in x_eval:
        target = lhs0 - A * dP * W * x
        out.append(brentq(lambda Q: Q + K * math.log(Q - K) - target, K * (1 + 1e-15), Qf,
                          xtol=1e-300, rtol=4 * np.finfo(float).eps))
    return np.array(out)
