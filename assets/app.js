/* RO Desalination Explorer — browser glue.
 *
 * 1. Typesets the equations (KaTeX) right away; the theory needs no Python.
 * 2. Builds the input controls (slider + number box, kept in sync).
 * 3. Starts Pyodide, loads numpy, fetches ro_model.py and validation.py from
 *    this site and imports them. Inputs stay disabled until this is done.
 * 4. On every input change (debounced), calls ro_model.run_from_ui(json) and
 *    redraws the summary cards, warnings and Plotly charts.
 * 5. Shows the CI validation results (validation/results.json) and can re-run
 *    the same checks in the browser via validation.run_all_json().
 *
 * All physics lives in ro_model.py; this file only moves numbers around.
 */
"use strict";

const PYODIDE_VERSION = "314.0.7"; // keep in sync with requirements-dev.txt / tests/test_smoke.py
const PYODIDE_INDEX = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const DEBOUNCE_MS = 150;
const SWEEP_DEBOUNCE_MS = 600;

// ---------------------------------------------------------------- controls

// Each control: id (key sent to Python), label, unit, min, max, step, value.
// `scale` converts the displayed value to what Python expects (e.g. % -> fraction).
const VESSEL_CONTROLS = [
  { head: "Feed" },
  { id: "C_f", label: "Feed salinity", unit: "g/L NaCl", min: 0.5, max: 70, step: 0.5, value: 35 },
  { id: "P_f", label: "Feed pressure", unit: "bar", min: 5, max: 85, step: 0.5, value: 60 },
  { id: "Q_f", label: "Feed flow per vessel", unit: "m³/h", min: 2, max: 16, step: 0.1, value: 12 },
  { id: "T", label: "Temperature", unit: "°C", min: 5, max: 40, step: 0.5, value: 25 },
  { head: "Membrane (at 25 °C)" },
  { id: "A", label: "Water permeance A", unit: "LMH/bar", min: 0.3, max: 10, step: 0.05, value: 1.4 },
  { id: "B", label: "Salt permeance B", unit: "LMH", min: 0, max: 1, step: 0.005, value: 0.05 },
  { id: "k", label: "Mass-transfer coeff. k", unit: "LMH", min: 20, max: 2000, step: 5, value: 180 },
  { id: "n_elements", label: "Elements per vessel", unit: "× 40.9 m²", min: 1, max: 8, step: 1, value: 7 },
  { id: "dP_drop", label: "Pressure drop", unit: "bar / vessel", min: 0, max: 5, step: 0.1, value: 1.5 },
  { head: "Options" },
  { id: "pressure_drop_on", label: "Include pressure drop", toggle: true, value: true },
  { id: "pitzer", label: "Pitzer correction for π (NaCl, not full seawater)", toggle: true, value: false },
  { head: "Energy" },
  { id: "erd_on", label: "Energy recovery device (ERD)", toggle: true, value: true },
  { id: "eta_pump", label: "Pump efficiency", unit: "%", min: 50, max: 90, step: 1, value: 80, scale: 0.01 },
  { id: "eta_erd", label: "ERD efficiency", unit: "%", min: 80, max: 98, step: 0.5, value: 95, scale: 0.01 },
];

const ECON_CONTROLS = [
  { head: "Plant" },
  { id: "capacity", label: "Plant capacity", unit: "m³/day", min: 1000, max: 1000000, step: 1000, value: 100000 },
  { id: "availability", label: "Availability", unit: "%", min: 50, max: 100, step: 1, value: 95, scale: 0.01 },
  { head: "Prices" },
  { id: "electricity_price", label: "Electricity", unit: "$/kWh", min: 0.02, max: 0.3, step: 0.001, value: 0.096 },
  { id: "membrane_cost", label: "Membrane element", unit: "$ each", min: 200, max: 2000, step: 10, value: 1000 },
  { id: "vessel_cost", label: "Pressure vessel", unit: "$ each", min: 500, max: 5000, step: 50, value: 2700 },
  { id: "pump_erd_cost", label: "HP pump + ERD", unit: "$/kW", min: 100, max: 3000, step: 50, value: 400 },
  { id: "other_multiplier", label: "Other-plant multiplier", unit: "×", min: 1, max: 20, step: 0.1, value: 12.5 },
  { head: "Finance & O&M" },
  { id: "interest", label: "Interest rate", unit: "%/yr", min: 0, max: 15, step: 0.25, value: 8 },
  { id: "plant_life", label: "Plant life", unit: "yr", min: 5, max: 40, step: 1, value: 25 },
  { id: "membrane_life", label: "Membrane life", unit: "yr", min: 2, max: 10, step: 0.5, value: 5 },
  { id: "om_fraction", label: "Fixed O&M", unit: "% of CAPEX/yr", min: 0, max: 8, step: 0.1, value: 4.5 },
];

const PRESETS = {
  seawater: { C_f: 35, P_f: 60, Q_f: 12, T: 25, A: 1.4, B: 0.05, k: 180, n_elements: 7, dP_drop: 1.5,
              pressure_drop_on: true },
  brackish: { C_f: 3, P_f: 15, Q_f: 12, T: 25, A: 3.0, B: 0.2, k: 180, n_elements: 7, dP_drop: 1.5,
              pressure_drop_on: true },
  // ideal membrane, almost no polarisation, low pressure and flow: the vessel pinches
  pinch: { C_f: 35, P_f: 40, Q_f: 2, T: 25, A: 1.0, B: 0, k: 2000, n_elements: 7, dP_drop: 0,
           pressure_drop_on: false },
};

const inputs = {}; // id -> { spec, range, number } or { spec, check }

function buildControls(container, specs) {
  for (const s of specs) {
    if (s.head) {
      const h = document.createElement("h4");
      h.textContent = s.head;
      container.appendChild(h);
      continue;
    }
    if (s.toggle) {
      const lab = document.createElement("label");
      lab.className = "toggle";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = s.value;
      cb.disabled = true;
      cb.id = `in-${s.id}`;
      cb.addEventListener("change", () => onInput(s.id));
      lab.append(cb, document.createTextNode(s.label));
      container.appendChild(lab);
      inputs[s.id] = { spec: s, check: cb };
      continue;
    }
    const wrap = document.createElement("div");
    wrap.className = "ctl";
    const id = `in-${s.id}`;
    wrap.innerHTML =
      `<div class="ctl-head"><label for="${id}">${s.label}</label><span class="unit">${s.unit}</span></div>` +
      `<div class="ctl-row"><input type="range" aria-label="${s.label} slider"><input type="number" id="${id}"></div>`;
    const [range, number] = wrap.querySelectorAll("input");
    for (const el of [range, number]) {
      el.min = s.min; el.max = s.max; el.step = s.step; el.value = s.value; el.disabled = true;
    }
    range.addEventListener("input", () => { number.value = range.value; onInput(s.id); });
    number.addEventListener("change", () => {
      let v = parseFloat(number.value);
      if (!Number.isFinite(v)) v = s.value;
      v = Math.min(s.max, Math.max(s.min, v)); // clamp typed values to the allowed range
      number.value = v; range.value = v;
      onInput(s.id);
    });
    container.appendChild(wrap);
    inputs[s.id] = { spec: s, range, number };
  }
}

function setValue(id, v) {
  const c = inputs[id];
  if (!c) return;
  if (c.check) c.check.checked = Boolean(v);
  else { c.range.value = v; c.number.value = v; }
}

function readParams() {
  const p = {};
  for (const [id, c] of Object.entries(inputs)) {
    if (c.check) p[id] = c.check.checked;
    else p[id] = parseFloat(c.number.value) * (c.spec.scale ?? 1);
  }
  // economics inputs in % that Python expects in % (interest, om_fraction) are not scaled;
  // availability is a fraction (scale 0.01 above).
  return p;
}

function setEnabled(on) {
  for (const c of Object.values(inputs)) {
    if (c.check) c.check.disabled = !on;
    else { c.range.disabled = !on; c.number.disabled = !on; }
  }
  document.querySelectorAll("[data-preset]").forEach((b) => (b.disabled = !on));
  document.getElementById("rerun").disabled = !on;
}

// ---------------------------------------------------------------- scheduling

let py = null; // { model, validation }
let runTimer = null;
let sweepTimer = null;
let lastResult = null;
let lastSweep = null;
const ECON_IDS = new Set(ECON_CONTROLS.filter((s) => s.id).map((s) => s.id));

function onInput(id) {
  clearTimeout(runTimer);
  runTimer = setTimeout(runModel, DEBOUNCE_MS);
  if (!ECON_IDS.has(id) && !["eta_pump", "eta_erd", "erd_on"].includes(id)) {
    clearTimeout(sweepTimer);
    sweepTimer = setTimeout(runSweep, SWEEP_DEBOUNCE_MS);
  }
}

function runModel() {
  if (!py) return;
  const status = document.getElementById("run-status");
  try {
    const t0 = performance.now();
    lastResult = JSON.parse(py.model.run_from_ui(JSON.stringify(readParams())));
    const ms = performance.now() - t0;
    const s = lastResult.summary;
    status.textContent = `Solved in ${ms.toFixed(0)} ms · RK4 ${s.converged ? "converged" : "NOT converged"} at N = ${s.N} steps`;
    renderAll();
  } catch (err) {
    status.textContent = `Model error: ${err.message ?? err}`;
    console.error(err);
  }
}

function runSweep() {
  if (!py) return;
  try {
    lastSweep = JSON.parse(py.model.pressure_sweep(JSON.stringify(readParams())));
    renderSweep();
  } catch (err) {
    console.error(err);
  }
}

// ---------------------------------------------------------------- formatting

const fmt = (v, d = 2) => (v === null || v === undefined || !Number.isFinite(v) ? "–" : v.toFixed(d));
const fmtInt = (v) => Math.round(v).toLocaleString("en-US");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function card(k, v, s = "") {
  return `<div class="card"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`;
}

// ---------------------------------------------------------------- plotting

function themeColors() {
  const cs = getComputedStyle(document.documentElement);
  const g = (n) => cs.getPropertyValue(n).trim();
  return { text: g("--text"), muted: g("--muted"), grid: g("--plot-grid"),
           c: [g("--plot-1"), g("--plot-2"), g("--plot-3"), g("--plot-4"), g("--plot-5")] };
}

function hexA(hex, a) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((x) => x + x).join("") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function baseLayout(xTitle, yTitle, extra = {}) {
  const t = themeColors();
  const axis = (title) => ({ title: { text: title, font: { size: 12 } }, gridcolor: t.grid, zerolinecolor: t.grid,
                             linecolor: t.grid, tickfont: { size: 11 } });
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: t.text, family: "Inter, system-ui, sans-serif", size: 12 },
    margin: { l: 56, r: 56, t: 10, b: 96 },
    xaxis: axis(xTitle), yaxis: axis(yTitle),
    legend: { orientation: "h", y: -0.2, yanchor: "top", x: 0, font: { size: 11 } },
    hovermode: "x unified",
    ...extra,
  };
}

const PLOT_CONFIG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

function pinchShapes(layout) {
  const s = lastResult.summary;
  if (s.x_pinch === null) return;
  const t = themeColors();
  const xs = lastResult.profiles.x;
  layout.shapes = [{ type: "rect", xref: "x", yref: "paper", x0: s.x_pinch, x1: xs[xs.length - 1], y0: 0, y1: 1,
                     fillcolor: hexA(t.c[1], 0.12), line: { width: 0 }, layer: "below" }];
  layout.annotations = [{ x: s.x_pinch, y: 1, xref: "x", yref: "paper", text: "pinch", showarrow: false,
                          xanchor: "left", yanchor: "top", font: { color: t.c[1], size: 11 } }];
}

function y2(title) {
  const t = themeColors();
  return { title: { text: title, font: { size: 12 } }, overlaying: "y", side: "right", gridcolor: "rgba(0,0,0,0)",
           tickfont: { size: 11 }, zerolinecolor: t.grid };
}

function renderProfiles() {
  const r = lastResult, p = r.profiles, t = themeColors();
  const line = (c, dash) => ({ color: c, width: 2, dash });

  // 1. flux + local rejection (J_w = A x NDP, so NDP itself is shown as the gap in plot 3)
  const rej = p.C_p.map((cp, i) => (cp === null || p.C_b[i] === null ? null : 100 * (1 - cp / p.C_b[i])));
  let lay = baseLayout("x along vessel (m)", "J<sub>w</sub> (LMH)", { yaxis2: y2("local rejection (%)") });
  lay.yaxis.rangemode = "tozero";
  pinchShapes(lay);
  Plotly.react("plot-flux", [
    { x: p.x, y: p.J_w, name: "Water flux J<sub>w</sub> = A·NDP", line: line(t.c[0]),
      hovertemplate: "J<sub>w</sub> %{y:.2f} LMH<extra></extra>" },
    { x: p.x, y: rej, name: "Local rejection 1 − C<sub>p</sub>/C<sub>b</sub> (right)", yaxis: "y2", line: line(t.c[2], "dash"),
      hovertemplate: "rejection %{y:.2f} %<extra></extra>" },
  ], lay, PLOT_CONFIG);

  // 2. concentrations
  lay = baseLayout("x along vessel (m)", "C<sub>b</sub>, C<sub>m</sub> (g/L)", { yaxis2: { ...y2("local permeate C<sub>p</sub> (g/L)"), rangemode: "tozero" } });
  pinchShapes(lay);
  Plotly.react("plot-conc", [
    { x: p.x, y: p.C_b, name: "Bulk C<sub>b</sub>", line: line(t.c[0]) },
    { x: p.x, y: p.C_m, name: "Membrane surface C<sub>m</sub>", line: line(t.c[1]) },
    { x: p.x, y: p.C_p, name: "Local permeate C<sub>p</sub> (right)", yaxis: "y2", line: line(t.c[2], "dot") },
  ], lay, PLOT_CONFIG);

  // 3. pressure vs osmotic pressures; shaded gap = NDP
  lay = baseLayout("x along vessel (m)", "pressure (bar)");
  pinchShapes(lay);
  Plotly.react("plot-pressure", [
    { x: p.x, y: p.pi_m, name: "π at the membrane, π<sub>m</sub>", line: line(t.c[1]) },
    { x: p.x, y: p.P, name: "Feed pressure P (shaded gap ≈ NDP)", line: line(t.c[0]), fill: "tonexty", fillcolor: hexA(t.c[0], 0.12) },
    { x: p.x, y: p.pi_b, name: "π of the bulk brine, π<sub>b</sub>", line: line(t.c[2], "dash") },
  ], lay, PLOT_CONFIG);

  // 4. CP factor
  lay = baseLayout("x along vessel (m)", "C<sub>m</sub> / C<sub>b</sub>");
  pinchShapes(lay);
  Plotly.react("plot-cp", [{ x: p.x, y: p.cp, name: "CP factor", line: line(t.c[3]) }], lay, PLOT_CONFIG);

  // 5. SEC bars
  const e = r.energy;
  const bars = [
    ["Pump, no ERD", e.no_erd, t.c[4]],
    ["Pump + ERD", e.erd, t.c[0]],
    ["Single-stage bound π<sub>b,out</sub>", e.single_stage, t.c[2]],
    ["Minimum, ideal rejection", e.min_ideal, t.c[3]],
    ["Minimum, actual separation", e.min_actual, t.c[1]],
  ];
  lay = baseLayout("", "kWh per m³ permeate", { hovermode: "closest", margin: { l: 56, r: 16, t: 24, b: 96 }, showlegend: false });
  lay.xaxis.tickangle = -20;
  Plotly.react("plot-sec", [{
    type: "bar", x: bars.map((b) => b[0]), y: bars.map((b) => b[1]), marker: { color: bars.map((b) => b[2]) },
    text: bars.map((b) => fmt(b[1], 2)), textposition: "outside", cliponaxis: false,
    hovertemplate: "%{x}: %{y:.3f} kWh/m³<extra></extra>",
  }], lay, PLOT_CONFIG);
}

function renderSweep() {
  if (!lastSweep) return;
  const s = lastSweep, t = themeColors();
  const lay = baseLayout("feed pressure (bar)", "recovery (%)", { yaxis2: { ...y2("observed rejection (%)") } });
  lay.yaxis.rangemode = "tozero";
  const traces = [
    { x: s.P, y: s.r_max.map((v) => 100 * v), name: "Limit r<sub>max</sub> (ideal membrane)", line: { color: t.c[1], width: 2, dash: "dash" } },
    { x: s.P, y: s.recovery.map((v) => 100 * v), name: "This vessel", line: { color: t.c[0], width: 2.5 } },
    { x: s.P, y: s.rejection.map((v) => 100 * v), name: "Rejection (right)", yaxis: "y2", line: { color: t.c[2], width: 1.5, dash: "dot" } },
  ];
  if (lastResult) {
    const p = readParams();
    traces.push({ x: [p.P_f], y: [100 * lastResult.summary.recovery], name: "Current setting", mode: "markers",
                  marker: { color: t.c[0], size: 10, line: { color: t.text, width: 1 } } });
  }
  lay.shapes = [{ type: "line", x0: s.pi_f, x1: s.pi_f, yref: "paper", y0: 0, y1: 1, line: { color: t.muted, width: 1, dash: "dot" } }];
  lay.annotations = [{ x: s.pi_f, y: 1, yref: "paper", text: "π<sub>f</sub>", showarrow: false, xanchor: "left", yanchor: "top", font: { color: t.muted, size: 11 } }];
  Plotly.react("plot-sweep", traces, lay, PLOT_CONFIG);
}

function renderCards() {
  const s = lastResult.summary, e = lastResult.energy;
  const erdOn = inputs.erd_on.check.checked;
  const sec = erdOn ? e.erd : e.no_erd;
  document.getElementById("cards").innerHTML = [
    card("Recovery", `${fmt(100 * s.recovery, 1)} %`, `limit r<sub>max</sub> ≈ ${fmt(100 * s.r_max, 1)} %`),
    card("Permeate", `${fmt(s.permeate_m3h, 2)} m³/h`, `avg. flux ${fmt(s.avg_flux_lmh, 1)} LMH`),
    card("Permeate salinity", `${fmtInt(1000 * s.C_p_mixed)} mg/L`, `rejection ${fmt(100 * s.rejection, 2)} %`),
    card("Brine", `${fmt(s.C_b_out, 1)} g/L`, `leaves at ${fmt(s.P_out_bar, 1)} bar`),
    card("Energy (SEC)", `${fmt(sec, 2)} kWh/m³`, erdOn ? "with ERD" : "no ERD"),
    card("Feed osmotic pressure", `${fmt(s.pi_f_bar, 1)} bar`, `${inputs.pitzer.check.checked ? "Pitzer" : "van’t Hoff"}; A at T: ${fmt(s.A_T, 2)} LMH/bar`),
  ].join("");
  const levels = { error: "Error", warn: "Warning", info: "Note" };
  document.getElementById("warnings").innerHTML = lastResult.warnings
    .map((w) => `<div class="warning ${w.level}"><strong>${levels[w.level]}:</strong> ${esc(w.text)}</div>`).join("");
}

function renderEconomics() {
  const ec = lastResult.economics, cards = document.getElementById("econ-cards");
  const table = document.getElementById("econ-table");
  if (!ec) {
    cards.innerHTML = card("Water cost", "–", "the vessel produces no water");
    table.innerHTML = "";
    Plotly.purge("plot-cost");
    return;
  }
  cards.innerHTML = [
    card("Water cost", `$${fmt(ec.total, 2)}/m³`, "teaching model"),
    card("Pressure vessels", fmtInt(ec.n_vessels), `${fmtInt(ec.n_elements)} elements`),
    card("Total CAPEX", `$${fmt(ec.capex_total / 1e6, 1)} M`, `$${fmtInt(ec.capex_per_m3d)} per m³/day`),
    card("Pump power", `${fmt(ec.power_kw / 1000, 2)} MW`, `CRF ${fmt(ec.crf, 4)}`),
  ].join("");
  const t = themeColors();
  const parts = [
    ["Capital", ec.parts.capital, t.c[0]],
    ["Energy", ec.parts.energy, t.c[1]],
    ["Membrane replacement", ec.parts.membrane_replacement, t.c[2]],
    ["Fixed O&M", ec.parts.fixed_om, t.c[3]],
  ];
  const lay = baseLayout("", "$ per m³", { barmode: "stack", hovermode: "closest", margin: { l: 56, r: 16, t: 24, b: 96 } });
  lay.shapes = [{ type: "rect", xref: "paper", x0: 0, x1: 1, y0: 0.5, y1: 1.0, fillcolor: hexA(t.c[4], 0.12), line: { width: 0 }, layer: "below" }];
  lay.annotations = [{ xref: "paper", x: 1, y: 1.0, text: "reported range for large SWRO [15]", showarrow: false,
                       xanchor: "right", yanchor: "bottom", font: { size: 10, color: t.muted } }];
  Plotly.react("plot-cost", parts.map(([n, v, c]) => ({
    type: "bar", x: ["This plant"], y: [v], name: n, marker: { color: c },
    hovertemplate: `${n}: $%{y:.3f}/m³<extra></extra>`,
  })), lay, PLOT_CONFIG);
  table.innerHTML = `<table><thead><tr><th>Component</th><th class="num">$/m³</th><th class="num">share</th></tr></thead><tbody>` +
    parts.map(([n, v]) => `<tr><td>${n}</td><td class="num">${fmt(v, 3)}</td><td class="num">${fmt(100 * v / ec.total, 0)} %</td></tr>`).join("") +
    `<tr><th>Total</th><th class="num">${fmt(ec.total, 3)}</th><th class="num">100 %</th></tr></tbody></table>`;
}

function renderAll() {
  if (!lastResult || typeof Plotly === "undefined") return;
  renderCards();
  renderProfiles();
  renderEconomics();
  renderSweep();
}

// ---------------------------------------------------------------- validation

let ciResults = null;

async function loadCiResults() {
  const meta = document.getElementById("ci-meta");
  try {
    const res = await fetch("validation/results.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    ciResults = await res.json();
    const c = ciResults.counts;
    const sha = ciResults.git_sha ? ` · commit <code>${esc(ciResults.git_sha.slice(0, 7))}</code>` : "";
    const run = ciResults.run_url ? ` · <a href="${esc(ciResults.run_url)}">CI run</a>` : "";
    meta.innerHTML = `Last automated run: ${esc(ciResults.generated_utc)} · Python ${esc(ciResults.python)}, numpy ${esc(ciResults.numpy)}` +
      ` · <strong>${c.passed} passed</strong>, ${c.failed} failed${sha}${run}`;
    document.getElementById("tests-table").innerHTML =
      `<table><thead><tr><th>Test</th><th>Result</th><th class="num">time (s)</th></tr></thead><tbody>` +
      ciResults.tests.map((t) => `<tr><td><code>${esc(t.name)}</code></td><td>${badge(t.outcome === "passed")}</td><td class="num">${fmt(t.duration_s, 3)}</td></tr>`).join("") +
      `</tbody></table>`;
  } catch (err) {
    meta.textContent = "No CI results file found (it is generated by the automated tests; run pytest locally to create it).";
  }
  renderValidation(null);
}

function badge(ok) {
  if (ok === null || ok === undefined) return `<span class="badge na">–</span>`;
  return ok ? `<span class="badge pass">pass</span>` : `<span class="badge fail">fail</span>`;
}

function renderValidation(browser) {
  const ci = new Map((ciResults?.checks ?? []).map((c) => [c.id, c]));
  const br = new Map((browser ?? []).map((c) => [c.id, c]));
  const ids = [...new Set([...ci.keys(), ...br.keys()])].sort();
  if (!ids.length) { document.getElementById("validation-table").innerHTML = ""; return; }
  const rows = ids.map((id) => {
    const a = ci.get(id), b = br.get(id), x = a ?? b;
    return `<tr><td>${id}</td><td>${esc(x.category)}</td><td>${esc(x.title)}</td><td>${esc(x.expected)}</td>` +
      `<td>${a ? esc(a.measured) + " " + badge(a.passed) : "–"}</td>` +
      `<td>${b ? esc(b.measured) + " " + badge(b.passed) : "–"}</td></tr>`;
  });
  document.getElementById("validation-table").innerHTML =
    `<table><thead><tr><th>ID</th><th>Area</th><th>Check</th><th>Expected</th><th>CI (GitHub)</th><th>Your browser</th></tr></thead>` +
    `<tbody>${rows.join("")}</tbody></table>`;
}

function rerunValidation() {
  const btn = document.getElementById("rerun"), status = document.getElementById("rerun-status");
  btn.disabled = true;
  status.textContent = " Running…";
  // let the browser paint the status before the (blocking) Python call
  setTimeout(() => {
    try {
      const t0 = performance.now();
      const res = JSON.parse(py.validation.run_all_json(true));
      const ok = res.filter((r) => r.passed).length;
      status.textContent = ` ${ok}/${res.length} checks passed in your browser (${((performance.now() - t0) / 1000).toFixed(1)} s).`;
      renderValidation(res);
    } catch (err) {
      status.textContent = ` Error: ${err.message ?? err}`;
    } finally {
      btn.disabled = false;
    }
  }, 30);
}

// ---------------------------------------------------------------- video / transcript

function setupVideo() {
  const box = document.getElementById("video");
  const id = (box.dataset.youtubeId || "").trim();
  if (/^[\w-]{6,20}$/.test(id)) {
    box.innerHTML = `<iframe src="https://www.youtube-nocookie.com/embed/${id}" title="Project presentation" ` +
      `allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe>`;
  }
}

async function loadTranscript() {
  try {
    const res = await fetch("transcript.md", { cache: "no-cache" });
    if (!res.ok) return;
    const text = (await res.text()).trim();
    if (!text || text.includes("TRANSCRIPT-PLACEHOLDER")) return;
    const paras = text.replace(/^#.*$/gm, "").split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
    document.getElementById("transcript").innerHTML = paras.map((p) => `<p>${esc(p)}</p>`).join("");
  } catch { /* keep placeholder */ }
}

// ---------------------------------------------------------------- Pyodide boot

function progress(pct, msg) {
  document.getElementById("loader-bar").style.width = `${pct}%`;
  document.getElementById("loader-msg").textContent = msg;
}

async function bootPython() {
  if (typeof loadPyodide === "undefined") {
    progress(0, "Could not load Pyodide from the CDN. Check your connection or ad-blocker and reload.");
    return;
  }
  try {
    progress(10, "Loading the Python runtime (first visit downloads ~10 MB; later visits are cached)…");
    const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX });
    progress(60, "Loading numpy…");
    await pyodide.loadPackage("numpy");
    progress(85, "Loading the RO model…");
    for (const f of ["ro_model.py", "validation.py"]) {
      const res = await fetch(f, { cache: "no-cache" });
      if (!res.ok) throw new Error(`could not fetch ${f} (HTTP ${res.status})`);
      pyodide.FS.writeFile(f, await res.text());
    }
    pyodide.runPython("import sys; sys.path.insert(0, '.'); import ro_model, validation");
    py = { model: pyodide.pyimport("ro_model"), validation: pyodide.pyimport("validation") };
    progress(100, `Ready: Python ${pyodide.runPython("import sys; sys.version.split()[0]")} running in your browser (Pyodide ${PYODIDE_VERSION}).`);
    setEnabled(true);
    runModel();
    runSweep();
    setTimeout(() => document.getElementById("loader").setAttribute("hidden", ""), 2500);
  } catch (err) {
    progress(0, `Failed to start Python: ${err.message ?? err}`);
    console.error(err);
  }
}

// ---------------------------------------------------------------- start

function typesetMath() {
  if (typeof renderMathInElement !== "function") return;
  renderMathInElement(document.body, {
    // only \( \) and \[ \] so that dollar signs in prices stay as text
    delimiters: [
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false },
    ],
    throwOnError: false,
  });
}

document.addEventListener("DOMContentLoaded", () => {
  typesetMath();
  buildControls(document.getElementById("ctl-vessel"), VESSEL_CONTROLS);
  buildControls(document.getElementById("ctl-econ"), ECON_CONTROLS);
  document.querySelectorAll("[data-preset]").forEach((b) =>
    b.addEventListener("click", () => {
      for (const [k, v] of Object.entries(PRESETS[b.dataset.preset])) setValue(k, v);
      onInput("preset");
    }));
  document.getElementById("rerun").addEventListener("click", rerunValidation);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderAll);
  setupVideo();
  loadTranscript();
  loadCiResults();
  bootPython();
});
