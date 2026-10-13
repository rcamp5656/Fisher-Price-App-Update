"""Iteration 6: half-A/half-B STL downloads + pin_radius param."""
import io
import os
import zipfile
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
MIDI_PATH = "/app/tests/assets/sample_twinkle.mid"


def _analyze():
    with open(MIDI_PATH, "rb") as f:
        r = requests.post(f"{API}/analyze",
                          files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
                          data={"duration": 25.0, "start": 0.0,
                                "auto_transpose": "true", "manual_offset": 0},
                          timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def two_sided_rec():
    ana = _analyze()
    payload = {
        "title": "TEST_Halves2S",
        "partition": ana["partition"],
        "partition_b": ana["partition"],
        "title_b": "TEST_Halves2S B",
        "thickness": 5.0,
        "pin_radius": 0.5,
        "filename": "sample_twinkle.mid",
        "duration": 25.0,
        "offset": ana["offset"],
        "exact": ana["exact"],
        "adjusted": ana["adjusted"],
        "merged": ana["merged"],
    }
    r = requests.post(f"{API}/press", json=payload, timeout=180)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def single_sided_rec():
    ana = _analyze()
    payload = {
        "title": "TEST_Halves1S",
        "partition": ana["partition"],
        "thickness": 3.0,
        "pin_radius": 0.9,
        "filename": "sample_twinkle.mid",
        "duration": 25.0,
        "offset": ana["offset"],
        "exact": ana["exact"],
        "adjusted": ana["adjusted"],
        "merged": ana["merged"],
    }
    r = requests.post(f"{API}/press", json=payload, timeout=180)
    assert r.status_code == 200, r.text
    return r.json()


# ----------------- half STLs -----------------
def test_two_sided_half_a_download(two_sided_rec):
    r = requests.get(f"{API}/conversions/{two_sided_rec['id']}/stl",
                     params={"part": "half-a"}, timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "model/stl"
    assert "halfA.stl" in r.headers.get("content-disposition", "")
    assert len(r.content) > 100 * 1024


def test_two_sided_half_b_download(two_sided_rec):
    r = requests.get(f"{API}/conversions/{two_sided_rec['id']}/stl",
                     params={"part": "half-b"}, timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "model/stl"
    assert "halfB.stl" in r.headers.get("content-disposition", "")
    assert len(r.content) > 100 * 1024


def test_two_sided_full_download_still_works(two_sided_rec):
    r = requests.get(f"{API}/conversions/{two_sided_rec['id']}/stl", timeout=30)
    assert r.status_code == 200
    assert len(r.content) > 100 * 1024


def test_single_sided_half_a_returns_404(single_sided_rec):
    r = requests.get(f"{API}/conversions/{single_sided_rec['id']}/stl",
                     params={"part": "half-a"}, timeout=30)
    assert r.status_code == 404


def test_single_sided_half_b_returns_404(single_sided_rec):
    r = requests.get(f"{API}/conversions/{single_sided_rec['id']}/stl",
                     params={"part": "half-b"}, timeout=30)
    assert r.status_code == 404


# ----------------- pack contents -----------------
def test_pack_two_sided_contains_halves(two_sided_rec):
    r = requests.get(f"{API}/conversions/{two_sided_rec['id']}/pack", timeout=30)
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert "TEST_Halves2S-halfA.stl" in names
    assert "TEST_Halves2S-halfB.stl" in names
    # size sanity
    assert len(z.read("TEST_Halves2S-halfA.stl")) > 50 * 1024
    assert len(z.read("TEST_Halves2S-halfB.stl")) > 50 * 1024


def test_pack_single_sided_no_halves(single_sided_rec):
    r = requests.get(f"{API}/conversions/{single_sided_rec['id']}/pack", timeout=30)
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert "TEST_Halves1S-halfA.stl" not in names
    assert "TEST_Halves1S-halfB.stl" not in names


# ----------------- pin_radius -----------------
def test_pin_radius_persisted(two_sided_rec):
    r = requests.get(f"{API}/conversions/{two_sided_rec['id']}", timeout=10)
    assert r.status_code == 200
    assert r.json().get("pin_radius") == 0.5


def test_pin_radius_default_in_single(single_sided_rec):
    r = requests.get(f"{API}/conversions/{single_sided_rec['id']}", timeout=10)
    assert r.status_code == 200
    assert r.json().get("pin_radius") == 0.9


def test_pin_radius_too_small_rejected():
    ana = _analyze()
    r = requests.post(f"{API}/press", json={
        "title": "TEST_PinTooSmall",
        "partition": ana["partition"],
        "pin_radius": 0.1,
    }, timeout=30)
    assert r.status_code == 422


def test_pin_radius_too_large_rejected():
    ana = _analyze()
    r = requests.post(f"{API}/press", json={
        "title": "TEST_PinTooLarge",
        "partition": ana["partition"],
        "pin_radius": 1.5,
    }, timeout=30)
    assert r.status_code == 422


# ----------------- part fallback -----------------
def test_unknown_part_falls_back_to_full(two_sided_rec):
    r = requests.get(f"{API}/conversions/{two_sided_rec['id']}/stl",
                     params={"part": "bogus"}, timeout=30)
    # Server falls back to full STL for unknown parts
    assert r.status_code == 200
    assert r.headers["content-type"] == "model/stl"
