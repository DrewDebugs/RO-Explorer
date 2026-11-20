"""Toolchain guard: CI must run the same Python and numpy as the browser (Pyodide).

If the Pyodide pin in assets/app.js changes, update these values and
requirements-dev.txt together.
"""

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]

# Pyodide 314.0.7 bundles Python 3.14 and numpy 2.4.6 (from its pyodide-lock.json).
PYODIDE_PYTHON = (3, 14)
PYODIDE_NUMPY = "2.4.6"


def test_python_matches_pyodide():
    assert sys.version_info[:2] == PYODIDE_PYTHON


def test_numpy_matches_pyodide():
    assert np.__version__ == PYODIDE_NUMPY


def test_plan_is_saved():
    assert (REPO / "docs" / "ai-log" / "01-plan.md").is_file()
