"""Iter14 — user bug: 'same Fisher-Price song for every MIDI'.
Verifies melody-track auto-pick demotes bass lines and prefers real melody
tracks (Tenor Sax for baby1, Jazz Gt. lead for whoscheating, single track for twinkle)."""
import os
from pathlib import Path

import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
ASSETS = Path("/app/tests/assets")
BABY1 = ASSETS / "user" / "baby1.mid"
WHOSCHEATING = ASSETS / "user" / "whoscheating.mid"
TWINKLE = ASSETS / "sample_twinkle.mid"


def _scan(path: Path) -> dict:
    r = requests.post(
        f"{API}/scan",
        files={"file": (path.name, path.read_bytes(), "audio/midi")},
        data={},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    return r.json()


class TestBaby1BassPenalty:
    def test_suggested_is_tenor_sax(self):
        data = _scan(BABY1)
        assert data["suggested"] == 5, f"expected 5 (Tenor Sax), got {data['suggested']}"

    def test_tenor_sax_has_highest_score(self):
        data = _scan(BABY1)
        best = max(data["tracks"], key=lambda t: t["melody_score"])
        assert best["index"] == 5
        assert best["instrument"] == "Tenor Sax"

    def test_pick_bass_track_demoted(self):
        data = _scan(BABY1)
        bass = next(t for t in data["tracks"] if t["index"] == 1)
        assert bass["instrument"] == "Pick Bass"
        assert bass["melody_score"] < 50, f"bass should be <50, got {bass['melody_score']}"

    def test_drum_tracks_score_zero(self):
        data = _scan(BABY1)
        drums = [t for t in data["tracks"] if t["drums"]]
        assert drums, "expected at least one drum track in baby1"
        for t in drums:
            assert t["melody_score"] == 0.0, f"drum track {t['index']} score={t['melody_score']}"


class TestWhosCheatingBassPenalty:
    def test_suggested_is_jazz_lead(self):
        data = _scan(WHOSCHEATING)
        assert data["suggested"] == 3, f"expected 3 (Jazz Gt. lead), got {data['suggested']}"

    def test_acbass_track_demoted(self):
        data = _scan(WHOSCHEATING)
        bass = next(t for t in data["tracks"] if t["index"] == 2)
        assert "Bass" in bass["name"] or "bass" in bass["name"].lower()
        assert bass["melody_score"] < 40, f"Ac.Bass should be <40, got {bass['melody_score']}"


class TestTwinkleSingleTrack:
    def test_suggested_is_zero(self):
        data = _scan(TWINKLE)
        assert data["suggested"] == 0, f"expected 0, got {data['suggested']}"
