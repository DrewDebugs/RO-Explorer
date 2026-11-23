# RO Desalination Explorer

[![CI / Pages](https://github.com/DrewDebugs/RO-Explorer/actions/workflows/pages.yml/badge.svg)](https://github.com/DrewDebugs/RO-Explorer/actions/workflows/pages.yml)

An interactive, single-page educational site about **reverse osmosis (RO) desalination**,
built for a Separation Processes course. It explains the theory, industrial context and
economics of RO, and includes a 1D model of an RO pressure vessel written in Python that
runs in your browser through [Pyodide](https://pyodide.org/) (WebAssembly), with no server.

**Live site:** https://drewdebugs.github.io/RO-Explorer/

> **This is an AI project.** The code and page content are drafted by Claude (Anthropic)
> in Claude Code and checked by a human. The whole AI process (plan, critique, decisions,
> implementation comparison, prompts) is recorded in [`docs/ai-log/`](docs/ai-log/).

## Status

| Milestone | What | State |
|---|---|---|
| M0 | Repo setup, plan, README, CI skeleton | ✅ done |
| M1 | Properties: units, osmotic pressure (van’t Hoff + Pitzer), TCF, SEC_min | ✅ done |
| M2 | Local solution–diffusion + film-model solver | ✅ done |
| M3 | 1D RK4 vessel model, convergence check, pinch detection | ✅ done |
| M4 | Energy (SEC, ERD) and economics | ✅ done |
| M5 | Independent SciPy reference implementation | ✅ done |
| M6 | Validation results file for the page | ✅ done |
| M7 | Page content and sources | ✅ done |
| M8 | Interactive app (Pyodide + Plotly) | ✅ done |
| M9 | Validation section with in-browser re-run | ✅ done |
| M10 | AI log and presentation sections, deploy | ✅ done (live) |

Full plan: [`docs/ai-log/01-plan.md`](docs/ai-log/01-plan.md). Every number and its source:
[`docs/sources-checklist.md`](docs/sources-checklist.md). Changes made since the plan
was approved: [`docs/ai-log/03-decisions.md`](docs/ai-log/03-decisions.md).

## Repository layout

```
index.html          the single page (9 sections)
assets/             app.js (Pyodide + Plotly glue), style.css
ro_model.py         the RO model: pure Python + numpy, the same file the tests check
validation.py       checks shared by pytest and the in-browser validation panel
tests/              pytest suite, including an independent SciPy reference solver
docs/ai-log/        plan, critique, decisions, implementation comparison, prompts
```

## Run the tests locally

Python 3.14 is used to match the Python version inside the pinned Pyodide release.

```bash
python3.14 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements-dev.txt
```

```bash
.venv/bin/pytest -q
```

## Run the site locally

Run the tests first (they write `validation/results.json`, which the Validation section shows), then serve the folder:

```bash
.venv/bin/pytest -q
```

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000/. The page loads Pyodide, Plotly and KaTeX from cdn.jsdelivr.net, so it needs an internet connection.

## Still to do (by the student)

- `docs/ai-log/02-critique.md`: critique of the plan by a second AI model, then the accept/reject table in `03-decisions.md`.
- `docs/ai-log/prompts/`: the prompts, verbatim.
- ~~`docs/sources-checklist.md`: tick off every number~~ (done: all 48 verified or labelled as assumptions).
- §8 Presentation: put the YouTube video ID in `data-youtube-id` in `index.html` and the transcript in `docs/transcript.md`.

## License

- **Code** (Python, JavaScript, CSS, workflows): [MIT](LICENSE).
- **Written content** (page text, figures, docs): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Third-party libraries (Pyodide, numpy, Plotly.js, KaTeX) keep their own licenses and are
credited on the site.
