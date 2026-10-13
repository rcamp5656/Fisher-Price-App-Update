"""Iter15: verify 8 kHz mono render, scan title field, and melody_fill behaviour."""
import io
import os
import wave

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ASSETS = "/app/tests/assets"
BABY = f"{ASSETS}/user/baby1.mid"
WHO = f"{ASSETS}/user/whoscheating.mid"
TWINKLE = f"{ASSETS}/sample_twinkle.mid"


def _upload(path):
    with open(path, "rb") as f:
        return ("midi", (os.path.basename(path), f.read(), "audio/midi"))


# ---------- /api/render returns 8 kHz mono WAV ----------
def test_render_baby_is_8khz_mono():
    with open(BABY, "rb") as f:
        r = requests.post(
            f"{API}/render",
            files={"file": ("baby1.mid", f.read(), "audio/midi")},
            data={"tracks": "5"},
            timeout=180,
        )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/wav")
    assert r.headers.get("X-Sample-Rate") == "8000"
    wf = wave.open(io.BytesIO(r.content))
    try:
        assert wf.getframerate() == 8000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
    finally:
        wf.close()


# ---------- /api/scan title field ----------
def test_scan_title_whoscheating():
    with open(WHO, "rb") as f:
        r = requests.post(f"{API}/scan", files={"file": ("whoscheating.mid", f.read(), "audio/midi")}, timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert data.get("title") == "Who's Cheatin Who"


def test_scan_title_baby_empty():
    with open(BABY, "rb") as f:
        r = requests.post(f"{API}/scan", files={"file": ("baby1.mid", f.read(), "audio/midi")}, timeout=60)
    assert r.status_code == 200
    assert r.json().get("title") == ""


def test_scan_title_twinkle_is_string():
    with open(TWINKLE, "rb") as f:
        r = requests.post(f"{API}/scan", files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")}, timeout=60)
    assert r.status_code == 200
    assert isinstance(r.json().get("title"), str)


# ---------- /api/analyze melody_fill behaviour ----------
def _analyze(path, tracks, melody_fill, start=18.7, duration=25):
    with open(path, "rb") as f:
        data = {"start": str(start), "duration": str(duration),
                "tracks": tracks, "melody_fill": "true" if melody_fill else "false"}
        r = requests.post(
            f"{API}/analyze",
            files={"file": (os.path.basename(path), f.read(), "audio/midi")},
            data=data,
            timeout=120,
        )
    assert r.status_code == 200, r.text
    return r.json()


def test_analyze_melody_fill_increases_notes():
    off = _analyze(BABY, "5", False)
    on = _analyze(BABY, "5", True)
    n0 = off["note_count"]
    n1 = on["note_count"]
    print(f"baby1 tracks=5 off={n0} on={n1}")
    assert n0 > 0
    assert n1 > n0, f"expected fill to add notes: off={n0} on={n1}"
    assert on.get("dropped", 0) == 0


def test_analyze_melody_fill_noop_when_all_tracks():
    off = _analyze(BABY, "", False)
    on = _analyze(BABY, "", True)
    assert on["note_count"] == off["note_count"], (on["note_count"], off["note_count"])


# ---------- /api/render X-Notes increases with fill ----------
def test_render_whoscheating_fill_adds_notes():
    with open(WHO, "rb") as f:
        payload = f.read()
    r_off = requests.post(
        f"{API}/render",
        files={"file": ("whoscheating.mid", payload, "audio/midi")},
        data={"tracks": "3", "melody_fill": "false"},
        timeout=180,
    )
    r_on = requests.post(
        f"{API}/render",
        files={"file": ("whoscheating.mid", payload, "audio/midi")},
        data={"tracks": "3", "melody_fill": "true"},
        timeout=180,
    )
    assert r_off.status_code == 200 and r_on.status_code == 200
    n_off = int(r_off.headers.get("X-Notes", "0"))
    n_on = int(r_on.headers.get("X-Notes", "0"))
    print(f"whoscheating tracks=3 X-Notes off={n_off} on={n_on}")
    assert n_on > n_off, (n_off, n_on)
    assert r_off.headers.get("X-Sample-Rate") == "8000"
    assert r_on.headers.get("X-Sample-Rate") == "8000"
