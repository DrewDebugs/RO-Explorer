"""Run every shared validation check (the same ones the page can re-run in the browser)."""

import pytest

import validation

IDS = [c[0] for c in validation.CHECKS]


@pytest.mark.parametrize("check_id", IDS)
def test_check(check_id, record_property):
    cid, title, cat, fn = next(c for c in validation.CHECKS if c[0] == check_id)
    r = fn(False)
    record_property("check", {"id": cid, "title": title, "category": cat, **r})
    assert r["passed"], r


def test_fast_mode_also_passes():
    assert all(r["passed"] for r in validation.run_all(fast=True))
