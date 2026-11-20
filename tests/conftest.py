"""Shared pytest setup.

1. Make the repo root importable (`import ro_model`, `import validation`).
2. After the run, write validation/results.json: every test with its outcome
   and duration, plus the measured numbers of every validation check. CI
   publishes this file with the site, and the Validation section displays it.
"""

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_reports = []


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _reports.append(report)


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        return repr(v)


def pytest_sessionfinish(session, exitstatus):
    import numpy

    tests, checks = [], []
    for r in _reports:
        props = {k: _jsonable(v) for k, v in r.user_properties}
        if "check" in props:
            checks.append(props.pop("check"))
        tests.append({"name": r.nodeid, "outcome": r.outcome,
                      "duration_s": round(r.duration, 4), "values": props})
    counts = {o: sum(t["outcome"] == o for t in tests) for o in ("passed", "failed", "skipped")}
    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": os.environ.get("GITHUB_SHA", ""),
        "run_url": (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
                    f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                    if os.environ.get("GITHUB_RUN_ID") else ""),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "exit_status": int(exitstatus),
        "counts": counts,
        "checks": sorted(checks, key=lambda c: c["id"]),
        "tests": tests,
    }
    path = ROOT / "validation" / "results.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
