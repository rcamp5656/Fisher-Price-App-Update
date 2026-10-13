"""Iter13 tests: POST /api/render, SCAD pin shape, melody-scoring regressions."""
import io
import os
import re
import wave
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ASSETS = Path("/app/tests/assets")
BABY1 = ASSETS / "user" / "baby1.mid"
WHOSCHEATING = ASSETS / "user" / "whoscheating.mid"
TWINKLE = ASSETS / "sample_twinkle.mid"


# ---------- /api/render ----------

class TestRender:
    def _post(self, path: Path, **form):
        files = {"file": (path.name, path.read_bytes(), "audio/midi")}
        data = {k: str(v) for k, v in form.items()}
        return requests.post(f"{API}/render", files=files, data=data, timeout=120)

    def _wav_meta(self, body: bytes):
        with wave.open(io.BytesIO(body), "rb") as w:
            return {
                "rate": w.getframerate(),
                "nchannels": w.getnchannels(),
                "sampwidth": w.getsampwidth(),
                "nframes": w.getnframes(),
                "duration": w.getnframes() / float(w.getframerate()),
            }

    def test_render_baby_track7(self):
        r = self._post(BABY1, tracks="7")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("audio/wav")
        assert r.headers["X-Sample-Rate"] == "8000"
        sides = int(r.headers["X-Sides"])
        notes = int(r.headers["X-Notes"])
        assert sides >= 1
        assert notes > 0
        meta = self._wav_meta(r.content)
        assert meta["rate"] == 8000
        assert meta["nchannels"] == 1
        assert meta["sampwidth"] == 2
        expected = sides * (25 + 0.6) + 1.5
        assert abs(meta["duration"] - expected) <= 2.0, \
            f"duration {meta['duration']} not within 2s of expected {expected}"

    def test_render_twinkle_default(self):
        r = self._post(TWINKLE)
        assert r.status_code == 200, r.text
        assert int(r.headers["X-Sides"]) == 1
        assert int(r.headers["X-Notes"]) > 0

    def test_render_non_midi(self):
        files = {"file": ("foo.txt", b"not a midi", "text/plain")}
        r = requests.post(f"{API}/render", files=files, data={}, timeout=30)
        assert 400 <= r.status_code < 500, f"expected 4xx got {r.status_code}"

    def test_render_drums_only(self):
        r = self._post(BABY1, tracks="12")
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"
        assert "no playable notes" in r.text.lower() or "no " in r.text.lower()


# ---------- SCAD pin shape ----------

class TestPinScad:
    def test_press_scad_has_pin_params(self):
        a = requests.post(
            f"{API}/analyze",
            files={"file": (TWINKLE.name, TWINKLE.read_bytes(), "audio/midi")},
            data={"duration": 25.0, "start": 0.0, "auto_transpose": "true", "manual_offset": 0},
            timeout=60,
        ).json()
        r = requests.post(
            f"{API}/press",
            json={"title": "TEST_Iter13_Pin", "partition": a["partition"]},
            timeout=240,
        )
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec.get("mesh_check", {}).get("ok", False) is True
        pin_count = rec["pin_count"]
        s = requests.get(f"{API}/conversions/{rec['id']}/scad", timeout=30)
        assert s.status_code == 200
        txt = s.text
        assert "pinBase = 1.6" in txt
        assert "pinSink = 0.5" in txt
        assert "sqrt(3)" not in txt
        # 3-pin partition sanity: analyze returned partition pin count == rec pin_count
        n_from_part = sum(1 for row in a["partition"] for v in row if v)
        assert pin_count == n_from_part, f"pin_count {pin_count} != partition pins {n_from_part}"


# ---------- Melody scoring regressions ----------

class TestScanMelody:
    def test_whoscheating_not_bass(self):
        files = {"file": (WHOSCHEATING.name, WHOSCHEATING.read_bytes(), "audio/midi")}
        r = requests.post(f"{API}/scan", files=files, data={}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["suggested"] != 2, f"suggested should not be bass track 2, got {data['suggested']}"
        assert data["suggested"] == 3, f"expected suggested=3, got {data['suggested']}"

    def test_baby_suggested_exact(self):
        files = {"file": (BABY1.name, BABY1.read_bytes(), "audio/midi")}
        r = requests.post(f"{API}/scan", files=files, data={}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert data["suggested"] == 5, f"got {data['suggested']}"
