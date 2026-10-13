"""Iteration 11: /api/autofit endpoint behaviour."""
import os
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
MIDI_PATH = Path("/app/tests/assets/sample_twinkle.mid")


def _post_autofit(**form):
    data = {"start": 0.0, "rev_seconds": 25.0, "auto_transpose": "true", "roll": "before"}
    data.update(form)
    with open(MIDI_PATH, "rb") as f:
        return requests.post(
            f"{API}/autofit",
            files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
            data=data,
            timeout=180,
        )


def _post_analyze(**form):
    data = {"duration": 25.0, "start": 0.0, "auto_transpose": "true", "roll": "before"}
    data.update(form)
    with open(MIDI_PATH, "rb") as f:
        return requests.post(
            f"{API}/analyze",
            files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
            data=data,
            timeout=60,
        )


def test_autofit_sample_twinkle_200_and_shape():
    r = _post_autofit()
    assert r.status_code == 200, r.text
    data = r.json()
    fit = data["fit"]
    # tries budget
    assert 1000 <= fit["tries"] <= 12000, fit
    # duration within ±35% of 25 s
    assert 16.25 <= fit["duration"] <= 33.75, fit
    # response.duration / start reflect fit
    assert abs(data["duration"] - fit["duration"]) < 1e-6
    assert abs(data["start"] - fit["start"]) < 1e-6
    # events present
    events = data["events"]
    assert isinstance(events, list) and len(events) > 0
    for ev in events:
        assert isinstance(ev, list) and len(ev) == 2
        t, n = ev
        assert 0.0 <= t < fit["duration"] + 1e-6, (t, fit["duration"])
        assert isinstance(n, (int, float))
    # partition sanity: one pin per beat max, dropped==0
    assert data["dropped"] == 0, data
    part = data["partition"]
    beats = len(part[0])
    for b in range(beats):
        col = sum(1 for row in part if row[b])
        assert col <= 1, f"beat {b} has {col} pins"


def test_autofit_beats_analyze_score():
    af = _post_autofit().json()
    an = _post_analyze(duration=25.0).json()
    assert af["fit"]["score"] >= an["fit"]["score"] - 0.5, (af["fit"], an["fit"])


def test_autofit_max_tries_budget():
    r = _post_autofit(max_tries=500)
    assert r.status_code == 200, r.text
    assert r.json()["fit"]["tries"] <= 500


def test_autofit_out_of_range_422():
    r = _post_autofit(start=999.0)
    assert r.status_code == 422, r.text


@pytest.fixture(scope="module", autouse=True)
def _restore_numbering():
    yield
    try:
        requests.put(f"{API}/numbering", json={"start": 6}, timeout=10)
    except Exception:
        pass
