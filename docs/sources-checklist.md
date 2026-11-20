# Sources checklist

Every number the model or the page relies on, where it comes from, and whether a
human has checked it against the source. **TODO-VERIFY** means Claude could not
confirm the value against the primary source and it must be checked before it is
presented as fact.

Columns: **Where** = file/section that uses it. **Verified?** = filled in by the user.

## M1: properties and SEC_min

| # | Quantity | Value used | Source | Where | Status | Verified? |
|---|---|---|---|---|---|---|
| S1 | Gas constant R | 8.314462618 J mol⁻¹ K⁻¹ | CODATA / 2019 SI definition (exact: N_A·k_B) | `ro_model.R_GAS` | Standard constant | ☐ |
| S2 | Molar mass NaCl | 58.44 g/mol | Standard atomic weights (Na 22.990 + Cl 35.45) | `ro_model.M_NACL` | Standard constant | ☐ |
| S3 | Density of water, 25 °C | 997.05 kg/m³ | Standard reference tables (e.g., CRC Handbook) | `ro_model.RHO_WATER` (molality estimate only) | Standard value | ☐ |
| S4 | Pitzer NaCl parameters, 25 °C | β⁰ = 0.0765, β¹ = 0.2664, C^φ = 0.00127 | Pitzer, K. S. & Mayorga, G. (1973). *J. Phys. Chem.* 77(19), 2300–2308. doi:10.1021/j100638a009 | `ro_model.PITZER_*` | From the plan; values match the commonly quoted table. **TODO-VERIFY** against the paper | ☐ |
| S5 | Debye–Hückel A_φ, 25 °C; b = 1.2; α = 2.0 | 0.392; 1.2; 2.0 kg^½ mol^-½ | Pitzer (1973) / Pitzer & Mayorga (1973) | `ro_model.PITZER_APHI`, `PITZER_B`, `PITZER_ALPHA` | **TODO-VERIFY** (A_φ is quoted as 0.391–0.392 in the literature) | ☐ |
| S6 | NaCl osmotic coefficients, 25 °C (test reference) | φ = 0.932 (0.1 m), 0.921 (0.5), 0.936 (1.0), 0.983 (2.0), 1.045 (3.0) | Robinson, R. A. & Stokes, R. H. (1959). *Electrolyte Solutions*, 2nd ed., Appendix 8.10 | `tests/test_properties.py` | **TODO-VERIFY** (values recalled, not read from the book) | ☐ |
| S7 | TCF constants for A and B | 2640 K (T ≥ 25 °C), 3020 K (T < 25 °C) | Membrane manufacturer design manual (FilmTec/DuPont Water Solutions technical manual, temperature correction factor) | `ro_model.TCF_K_ABOVE/BELOW` | **TODO-VERIFY** (exact constants, and whether B uses the same factor) | ☐ |
| S8 | Minimum energy, 35 g/L at 50 % recovery | 1.06 kWh/m³ | Elimelech, M. & Phillip, W. A. (2011). The future of seawater desalination: energy, technology, and the environment. *Science* 333(6043), 712–717. doi:10.1126/science.1200488 | `tests/test_properties.py::test_sec_min_seawater_50pct` | **TODO-VERIFY** (value and the exact conditions it refers to) | ☐ |

### Model results that depend on these (computed, for cross-checking)

| Result | Value | Check |
|---|---|---|
| π(35 g/L, 25 °C), van’t Hoff | 29.69 bar | 2 × (35/58.44) mol/L × R × 298.15 K |
| π(35 g/L, 25 °C), Pitzer | 27.41 bar | φ(0.601 mol/kg) = 0.923 |
| SEC_min(35 g/L, r = 0.5), van’t Hoff | 1.143 kWh/m³ | π_f · ln 2 / 0.5 / 36 |
| SEC_min(35 g/L, r = 0.5), Pitzer | 1.065 kWh/m³ | vs 1.06 in S8 (0.5 % apart) |
