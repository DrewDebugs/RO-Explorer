# Sources checklist

Every number the model or the page relies on, where it comes from, and whether a
human has checked it against the source. **TODO-VERIFY** means Claude could not
confirm the value against the primary source and it must be checked before it is
presented as fact.

Columns: **Where** = file/section that uses it. **Verified?** = filled in by the user.

## M1: properties and SEC_min

| # | Quantity | Value used | Source | Where | Status | Verified? |
|---|---|---|---|---|---|---|
| S1 | Gas constant R | 8.314462618 J mol⁻¹ K⁻¹ | CODATA / 2019 SI definition (exact: N_A·k_B) | `ro_model.R_GAS` | Standard constant; verified by the student | ☑ |
| S2 | Molar mass NaCl | 58.44 g/mol | Standard atomic weights (Na 22.990 + Cl 35.45) | `ro_model.M_NACL` | Standard constant; verified by the student | ☑ |
| S3 | Density of water, 25 °C | 997.05 kg/m³ | Standard reference tables (e.g., CRC Handbook) | `ro_model.RHO_WATER` (molality estimate only) | Standard value; verified by the student | ☑ |
| S4 | Pitzer NaCl parameters, 25 °C | β⁰ = 0.0765, β¹ = 0.2664, C^φ = 0.00127 | Pitzer, K. S. & Mayorga, G. (1973). *J. Phys. Chem.* 77(19), 2300–2308. doi:10.1021/j100638a009 | `ro_model.PITZER_*` | Verified by the student against Pitzer & Mayorga (1973) | ☑ |
| S5 | Debye–Hückel A_φ, 25 °C; b = 1.2; α = 2.0 | 0.392; 1.2; 2.0 kg^½ mol^-½ | Pitzer (1973) / Pitzer & Mayorga (1973) | `ro_model.PITZER_APHI`, `PITZER_B`, `PITZER_ALPHA` | Verified by the student against Pitzer & Mayorga (1973) | ☑ |
| S6 | NaCl osmotic coefficients, 25 °C (test reference) | φ = 0.932 (0.1 m), 0.921 (0.5), 0.936 (1.0), 0.983 (2.0), 1.045 (3.0) | Robinson, R. A. & Stokes, R. H. (1959). *Electrolyte Solutions*, 2nd ed., Appendix 8.10 | `tests/test_properties.py` | Verified by the student against the tabulated NaCl data | ☑ |
| S7 | TCF constants for A and B | 2640 K (T ≥ 25 °C), 3020 K (T < 25 °C) | Membrane manufacturer design manual (FilmTec/DuPont Water Solutions technical manual, temperature correction factor) | `ro_model.TCF_K_ABOVE/BELOW` | **TODO-VERIFY** (exact constants, and whether B uses the same factor) | ☐ |
| S8 | Minimum energy, 35 g/L at 50 % recovery | 1.06 kWh/m³ | Elimelech, M. & Phillip, W. A. (2011). The future of seawater desalination: energy, technology, and the environment. *Science* 333(6043), 712–717. doi:10.1126/science.1200488 | `tests/test_properties.py::test_sec_min_seawater_50pct` | Verified by the student against Elimelech & Phillip (2011) | ☑ |

### Model results that depend on these (computed, for cross-checking)

| Result | Value | Check |
|---|---|---|
| π(35 g/L, 25 °C), van’t Hoff | 29.69 bar | 2 × (35/58.44) mol/L × R × 298.15 K |
| π(35 g/L, 25 °C), Pitzer | 27.41 bar | φ(0.601 mol/kg) = 0.923 |
| SEC_min(35 g/L, r = 0.5), van’t Hoff | 1.143 kWh/m³ | π_f · ln 2 / 0.5 / 36 |
| SEC_min(35 g/L, r = 0.5), Pitzer | 1.065 kWh/m³ | vs 1.06 in S8 (0.5 % apart) |

## M2–M4: model defaults and thresholds

| # | Quantity | Value used | Source | Where | Status | Verified? |
|---|---|---|---|---|---|---|
| S9 | 8-inch SWRO element: active area, length | 440 ft² = 40.9 m²; 40 in = 1.016 m | DuPont FilmTec SW30HRLE-440 Product Data Sheet, Form No. 45-D00969-en, Rev. 3 (Nov 2019): active area 440 ft² (41 m²), length 40.0 in (1,016 mm), fits an 8-inch pressure vessel | `VesselInputs.area_element`, `length_element` | Verified by the student (datasheet p. 1 and p. 2) | ☑ |
| S10 | Maximum element pressure | 83 bar (1,200 psi) | DuPont FilmTec SW30HRLE-440 Product Data Sheet, Form No. 45-D00969-en, Rev. 3 (Nov 2019): maximum operating pressure 1,200 psig (83 bar) | `ELEMENT_MAX_PRESSURE_BAR` warning | Verified by the student (datasheet p. 2) | ☑ |
| S11 | TCF constants | 2640 K above 25 °C, 3020 K below | FilmTec design equations (Lenntech copy): `TCF = exp[3020(1/298 − 1/T)]` for T ≤ 25 °C, 2640 above | `TCF_K_ABOVE/BELOW` | Verified by the student: FilmTec design equations (Dow Form No. 609-02057-604) Eq. 16a,b gives exactly these constants (model and document agree to 0.05 %); Eq. 19 applies the same TCF to salt passage | ☑ |
| S12 | Water permeance A (seawater default) | 1.0 LMH/bar (range 0.3–10) | Werber, Osuji & Elimelech (2016) *Nat. Rev. Mater.* 1, 16018; a 2024 review states commercial TFC RO is “~ or > 1 L m⁻² h⁻¹ bar⁻¹” | `UI_DEFAULTS["A"]` | Datasheet check (student-supplied datasheet, fitted with this model to its test: 32 g/L NaCl, 55.2 bar, 25 °C, 8 % recovery, 30.2 m³/d, 99.80 % rejection): A = 1.06–1.42 LMH/bar and B = 0.050–0.059 LMH depending on π model and k. Default A = 1.0 is the right magnitude (slightly conservative); default B = 0.10 is about 2× this premium element. Also FilmTec design equations (Dow Form No. 609-02057-604) Eq. 28 (FT30 membrane): A ≈ 3.0 LMH/bar at brackish 3 g/L (matches the brackish preset exactly) and ≈ 1.24 LMH/bar at seawater 35 g/L | ☐ |
| S13 | Salt permeance B | 0.10 LMH (range 0–1) | Werber et al. 2016 | `UI_DEFAULTS["B"]` | Datasheet check (student-supplied datasheet, fitted with this model to its test: 32 g/L NaCl, 55.2 bar, 25 °C, 8 % recovery, 30.2 m³/d, 99.80 % rejection): A = 1.06–1.42 LMH/bar and B = 0.050–0.059 LMH depending on π model and k. Default A = 1.0 is the right magnitude (slightly conservative); default B = 0.10 is about 2× this premium element | ☐ |
| S14 | Mass-transfer coefficient k | 180 LMH (5×10⁻⁵ m/s) | Chosen so the CP factor at the vessel inlet is ~1.15, below the ~1.2 design guideline | `UI_DEFAULTS["k"]` | Checked against FilmTec design equations (Dow Form No. 609-02057-604) Eq. 17, pf = exp(0.7·Y_i): ≈ 1.06 for the default vessel vs the model’s mean CP of 1.08 (1.15 inlet, 1.03 outlet). Consistent | ☑ |
| S15 | Feed flow per vessel | 9 m³/h | Not tuned: gives 44.6 % recovery with the other defaults, inside the plan's 40–45 % target | `UI_DEFAULTS["Q_f"]` | **TODO-VERIFY** within the element feed-flow limits on the datasheet | ☐ |
| S16 | Pressure drop | 1.5 bar per vessel | Design manual order of magnitude | `UI_DEFAULTS["dP_drop"]` | Checked against FilmTec design equations (Dow Form No. 609-02057-604) Eq. 27c, ΔP = 0.01·n·q^1.7 psi: 1.64 bar for the default vessel vs 1.5 bar used (correlation is for BW30 8-inch elements). Datasheet limit 1.0 bar/element | ☑ |
| S17 | Pump efficiency | 80 % | Engineering assumption | `UI_DEFAULTS["eta_pump"]` | Assumption (stated) | ☐ |
| S18 | ERD (pressure exchanger) efficiency | 95 % default (slider 80–98 %) | Review: isobaric devices ~95–97 % (Frontiers in Sustainable Cities 2020, doi:10.3389/frsc.2020.00009); vendor guarantees 96.8–97.2 % (Energy Recovery Inc.) | `UI_DEFAULTS["eta_erd"]` | Confirmed range; **TODO-VERIFY** review authors | ☐ |
| S19 | Brine warning threshold | 70 g/L | Teaching threshold (twice seawater) | `BRINE_GUIDELINE_GL` | Assumption (stated on page) | ☐ |
| S20 | CP warning threshold | 1.2 | Design guideline (FilmTec manual) | `CP_GUIDELINE` | The “keep below ~1.2” design guideline was NOT in the FilmTec design equations (Dow Form No. 609-02057-604); the page now cites its Eq. 17 correlation instead, and 1.2 is kept only as a labelled teaching threshold for the warning | ☑ |

## Economics defaults (teaching model)

| # | Quantity | Value used | Source / reasoning | Status | Verified? |
|---|---|---|---|---|---|
| S21 | Electricity price | $0.08/kWh | Illustrative industrial price | **TODO-VERIFY** (EIA/IEA industrial average) | ☐ |
| S22 | Membrane element | $600 each | Illustrative | **TODO-VERIFY** (Voutchkov 2018 or vendor quotes) | ☐ |
| S23 | Pressure vessel | $1,500 each | Illustrative | **TODO-VERIFY** | ☐ |
| S24 | HP pump + ERD | $1,000 per kW | Illustrative | **TODO-VERIFY** | ☐ |
| S25 | Other-plant multiplier | 7 | Chosen so total CAPEX ≈ $1,080 per m³/day, within the range implied by real plants (Sorek ≈ $880, Carlsbad ≈ $5,300 per m³/day from reported totals) and the learning-curve average (Caldera & Breyer 2017, *Water Resour. Res.*, projects ~$1,340–1,580 per m³/day by 2030) | **TODO-VERIFY** Caldera & Breyer reference and plant cost totals | ☐ |
| S26 | Fixed O&M | 2 % of CAPEX per year | Illustrative | **TODO-VERIFY** | ☐ |
| S27 | Interest / plant life / membrane life | 8 % / 25 yr / 5 yr | Engineering-economics assumptions (stated) | Assumption | ☐ |
| S28 | Reported water cost of large SWRO | $0.50–1.00/m³ | Ghaffour, Missimer & Amy (2013) *Desalination* 309, 197–207 (“below US$0.50/m³ … in other locations 50 % higher (US$1.00/m³)”) | Verified by the student against the paper’s abstract (“below US$0.50/m³ … 50% higher (US$1.00/m³)”) | ☑ |

## Page §2: industrial significance

| # | Fact on page | Value | Source | Status | Verified? |
|---|---|---|---|---|---|
| S29 | Operational desalination plants | 15,906 | Jones et al. (2019) *Sci. Total Environ.* 657, 1343–1356 (abstract) | Confirmed in abstract | ☐ |
| S30 | Global desalinated water production | ~95 million m³/day | Jones et al. (2019) | Confirmed in abstract | ☐ |
| S31 | Share produced in Middle East & North Africa | 48 % | Jones et al. (2019) | Confirmed in abstract | ☐ |
| S32 | Global brine production | ~142 million m³/day | Jones et al. (2019) | Confirmed in abstract | ☐ |
| S33 | Membrane (RO) share of global capacity | ~69 % | UN Third World Ocean Assessment, Ch. 8: “Membrane desalination technology (involving reverse osmosis) accounts for approximately 85% of total worldwide desalination plants and generates approximately 69% of global desalination capacity” (the chapter cites its own refs 26 and 31) | Verified by the student against the WOA chapter text. Not found in the Jones 2019 abstract, so cited to the WOA | ☑ |
| S34 | Taweelah capacity | 909,200 m³/day (200 MIGD) | ACWA Power project page; EWEC announcements | Confirmed (operator) | ☐ |
| S35 | Sorek 2 capacity | ≈ 670,000 m³/day (IDE project page says 672,000) | IDE press release, 18 March 2025 | Confirmed (operator) | ☐ |
| S36 | Sorek capacity | 624,000 m³/day, opened 2013 | IDE / WaterWorld | Confirmed | ☐ |
| S37 | Carlsbad capacity | 50 million US gal/day ≈ 189,000 m³/day | San Diego County Water Authority | Confirmed | ☐ |
| S38 | Carlsbad energy recovery | 144 pressure exchangers; −46 % RO energy; ~146 million kWh/yr saved | San Diego County Water Authority (an earlier 2013 estimate was 116 million kWh/yr) | Confirmed; note the two figures | ☐ |
| S39 | Minimum energy, 35 g/L, 50 % recovery | 1.06 kWh/m³ | Elimelech & Phillip (2011) *Science* 333, 712 | Verified by the student (same as S8) | ☑ |
| S40 | Element size | 8 in × 40 in, 440 ft² | DuPont FilmTec SW30HRLE-440 Product Data Sheet, Form No. 45-D00969-en, Rev. 3 (Nov 2019) | Verified by the student (see S9) | ☑ |
| S41 | Membrane suppliers | DuPont (FilmTec), Toray (Taweelah order), Nitto/Hydranautics, LG Chem | Company documents and WaterWorld (Toray Taweelah order) | Presence confirmed; no market-share claims made | ☐ |
| S42 | Standard seawater salinity | ~35 g/kg (Reference-Composition Salinity 35.16504 g/kg) | Millero et al. (2008) *Deep-Sea Res. I* 55, 50–72 | **TODO-VERIFY** | ☐ |

## Page §2: industry examples

| # | Fact on page | Value | Source | Status | Verified? |
|---|---|---|---|---|---|
| S43 | Taweelah solar share | ≥ 30 % of electricity from a ~69 MW solar park within eight years; target 55 % | pv magazine, 23 June 2022 (quoting ACWA Power) | Verified by the student against pv magazine (quoting ACWA): at least 30 % within eight years, target 55 %; solar park ≈ 69 MW per ACWA. Page wording updated to match | ☑ |
| S44 | Sorek membrane arrangement | 16-inch elements in vertical vessels; ~4.3× the flow of an 8-inch element | WaterWorld, “Sorek stands tall” (IDE figures) | Company-reported | ☐ |
| S45 | Orange County GWRS capacity | 130 million US gal/day (492,000 m³/day), largest indirect potable reuse plant; final expansion 2023 | Orange County Water District; CA State Water Board press release 14 Apr 2023 | Confirmed (operator) | ☐ |
| S46 | NEWater process and share | MF/UF → RO → UV; up to 40 % of Singapore’s demand | US EPA summary of Singapore’s reuse regulation; PUB “Our Water Story” | Confirmed | ☐ |
| S47 | Perth (Kwinana) wind offset | 80 MW Emu Downs wind farm, 48 turbines | Government of Western Australia media statement, 26 July 2005 | Confirmed (other sources say 83 MW) | ☐ |
| S48 | Semiconductor ultrapure water | RO then ion exchange/EDI; a 200 mm fab at 20,000 wafers/month uses up to 3,000 m³/day of UPW | MKS Instruments | Verified by the student against the MKS page (based on ITRS 2011: 7 L/cm² per wafer out). MKS says UPW is made with RO followed by deionising resin beds; page wording updated to match | ☑ |
