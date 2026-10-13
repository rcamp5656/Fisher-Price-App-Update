"""Backend tests for the new /api/analyze -> /api/press flow and two-sided discs."""
import os
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"
MIDI_PATH = "/app/tests/assets/sample_twinkle.mid"
TONES = 16
BEATS = 86


def _midi_bytes():
    with open(MIDI_PATH, "rb") as f:
        return f.read()


# --------------------- /api/analyze ---------------------
@pytest.fixture(scope="module")
def analysis():
    files = {"file": ("sample_twinkle.mid", _midi_bytes(), "audio/midi")}
    data = {"duration": "25", "start": "0", "auto_transpose": "true", "manual_offset": "0"}
    r = requests.post(f"{API}/analyze", files=files, data=data, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def test_analyze_shape(analysis):
    j = analysis
    assert j["beats"] == BEATS
    assert len(j["partition"]) == TONES
    for row in j["partition"]:
        assert len(row) == BEATS
        assert all(isinstance(x, bool) for x in row)
    assert j["note_count"] > 0
    assert j["duration"] == 25.0
    assert j["start"] == 0.0
    assert "offset" in j and "exact" in j and "adjusted" in j and "merged" in j
    assert isinstance(j["notes_used"], list) and len(j["notes_used"]) > 0


def test_analyze_empty_window_returns_422():
    files = {"file": ("sample_twinkle.mid", _midi_bytes(), "audio/midi")}
    data = {"duration": "25", "start": "25", "auto_transpose": "true", "manual_offset": "0"}
    r = requests.post(f"{API}/analyze", files=files, data=data, timeout=60)
    assert r.status_code == 422
    assert "No playable notes" in r.text


def test_analyze_rejects_non_midi():
    files = {"file": ("foo.txt", b"nope", "text/plain")}
    r = requests.post(f"{API}/analyze", files=files, timeout=30)
    assert r.status_code == 400


# --------------------- /api/press ---------------------
@pytest.fixture(scope="module")
def pressed(analysis):
    payload = {
        "title": "TEST_PressA",
        "partition": analysis["partition"],
        "thickness": 3.0,
        "engrave": True,
        "filename": "sample_twinkle.mid",
        "duration": 25.0,
        "offset": analysis["offset"],
        "exact": analysis["exact"],
        "adjusted": analysis["adjusted"],
        "merged": analysis["merged"],
    }
    r = requests.post(f"{API}/press", json=payload, timeout=180)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def pressed_two_sided(analysis):
    # Side B: shift the partition one beat to create a different pattern
    part_b = [[False] * BEATS for _ in range(TONES)]
    for t, row in enumerate(analysis["partition"]):
        for b, on in enumerate(row):
            if on:
                part_b[t][(b + 3) % BEATS] = True
    payload = {
        "title": "TEST_SideA",
        "title_b": "TEST_SideB",
        "partition": analysis["partition"],
        "partition_b": part_b,
        "thickness": 3.0,
        "engrave": True,
        "filename": "sample_twinkle.mid",
        "duration": 25.0,
        "offset": 0, "exact": 0, "adjusted": 0, "merged": 0,
    }
    r = requests.post(f"{API}/press", json=payload, timeout=240)
    assert r.status_code == 200, r.text
    return r.json()


def test_press_summary(pressed, analysis):
    j = pressed
    assert j["id"]
    assert j["two_sided"] is False
    assert j["title_b"] is None
    assert j["pin_count"] > 0
    assert j["triangles"] > 0
    assert j["beats"] == BEATS
    assert len(j["partition"]) == TONES
    assert j["partition_b"] is None


def test_press_two_sided_summary(pressed_two_sided):
    j = pressed_two_sided
    assert j["two_sided"] is True
    assert j["title_b"] == "TEST_SideB"
    assert j["partition_b"] is not None
    assert len(j["partition_b"]) == TONES


def test_press_bad_partition_shape(analysis):
    bad = analysis["partition"][:15]  # 15 rows instead of 16
    r = requests.post(f"{API}/press", json={"title": "x", "partition": bad}, timeout=30)
    assert r.status_code == 400


def test_press_empty_partition():
    empty = [[False] * BEATS for _ in range(TONES)]
    r = requests.post(f"{API}/press", json={"title": "x", "partition": empty}, timeout=30)
    assert r.status_code == 400


# --------------------- downloads for new press ---------------------
def test_stl_download_size(pressed):
    r = requests.get(f"{API}/conversions/{pressed['id']}/stl", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("model/stl")
    assert len(r.content) > 100_000


def test_scad_has_glyph_lines(pressed):
    r = requests.get(f"{API}/conversions/{pressed['id']}/scad", timeout=30)
    assert r.status_code == 200
    txt = r.text
    assert "glyph(" in txt  # curved label letters
    assert "twoSided = false" in txt


def test_scad_two_sided(pressed_two_sided):
    r = requests.get(f"{API}/conversions/{pressed_two_sided['id']}/scad", timeout=30)
    assert r.status_code == 200
    txt = r.text
    assert "twoSided = true" in txt
    assert ",true)" in txt  # pin(...,true) lines for side B


def test_fpr_sides(pressed, pressed_two_sided):
    r = requests.get(f"{API}/conversions/{pressed['id']}/fpr", timeout=30)
    assert r.status_code == 200
    lines = r.text.strip("\n").split("\n")
    assert len(lines) >= 17
    for ln in lines[:16]:
        assert len(ln) == BEATS
        assert set(ln) <= {"+", "-"}
    # side=b on single-sided -> 404
    r2 = requests.get(f"{API}/conversions/{pressed['id']}/fpr?side=b", timeout=30)
    assert r2.status_code == 404

    # Two-sided has side B
    rb = requests.get(f"{API}/conversions/{pressed_two_sided['id']}/fpr?side=b", timeout=30)
    assert rb.status_code == 200
    linesb = rb.text.strip("\n").split("\n")
    assert len(linesb) >= 17


# --------------------- legacy /api/convert still works ---------------------
def test_legacy_convert_includes_partition():
    files = {"file": ("sample_twinkle.mid", _midi_bytes(), "audio/midi")}
    data = {"duration": "25", "thickness": "3", "auto_transpose": "true"}
    r = requests.post(f"{API}/convert", files=files, data=data, timeout=180)
    assert r.status_code == 200
    j = r.json()
    assert j["partition"] is not None
    assert len(j["partition"]) == TONES


def test_list_no_leaks():
    r = requests.get(f"{API}/conversions", timeout=30)
    assert r.status_code == 200
    for d in r.json():
        for k in ("stl_b64", "scad", "fpr", "fpr_b", "_id"):
            assert k not in d
