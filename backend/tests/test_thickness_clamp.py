"""Tests for two-sided thickness clamp (>=4.5mm when partition_b given)."""
import os
import requests
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
TONES, BEATS = 16, 86


def _part(seed=0):
    p = [[False] * BEATS for _ in range(TONES)]
    for i in range(10):
        p[(i + seed) % TONES][(i * 5 + seed) % BEATS] = True
    return p


def test_two_sided_clamps_thickness_to_4_5():
    r = requests.post(f"{API}/press", json={
        "title": "TEST_ClampA", "title_b": "TEST_ClampB",
        "partition": _part(0), "partition_b": _part(1),
        "thickness": 3.0,
    }, timeout=180)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["two_sided"] is True
    assert j["thickness"] == 4.5, f"Expected 4.5 clamped, got {j['thickness']}"


def test_single_sided_keeps_3_0():
    r = requests.post(f"{API}/press", json={
        "title": "TEST_SingleThick", "partition": _part(0), "thickness": 3.0,
    }, timeout=180)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["two_sided"] is False
    assert j["thickness"] == 3.0, f"Expected 3.0, got {j['thickness']}"
