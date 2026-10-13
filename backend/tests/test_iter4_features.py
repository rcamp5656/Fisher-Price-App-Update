"""Iteration 4 backend tests: stagger, record_no, overrides, comb, library, scan."""
import io
import os
from pathlib import Path

import pytest
import requests
import mido

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"
MIDI_PATH = "/app/tests/assets/sample_twinkle.mid"
BEATS = 86
FACTORY_TRACKS = [67, 72, 74, 76, 79, 81, 83, 84, 84, 86, 86, 88, 88,
                  89, 89, 91, 91, 93, 93, 95, 96, 98]


def _midi_bytes():
    with open(MIDI_PATH, "rb") as f:
        return f.read()


def _chord_midi():
    """Build a MIDI with a 3-note chord at t=0 and single notes after."""
    mid = mido.MidiFile()
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    # Chord C4 E4 G4 at t=0 (all 3 simultaneous)
    tr.append(mido.Message("note_on", note=72, velocity=90, time=0))
    tr.append(mido.Message("note_on", note=76, velocity=90, time=0))
    tr.append(mido.Message("note_on", note=79, velocity=90, time=0))
    tpb = mid.ticks_per_beat
    tr.append(mido.Message("note_off", note=72, velocity=0, time=tpb))
    tr.append(mido.Message("note_off", note=76, velocity=0, time=0))
    tr.append(mido.Message("note_off", note=79, velocity=0, time=0))
    # Then single notes
    for n in (72, 74, 76, 79):
        tr.append(mido.Message("note_on", note=n, velocity=90, time=0))
        tr.append(mido.Message("note_off", note=n, velocity=0, time=tpb))
    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


# ---------------- cleanup ----------------
@pytest.fixture(autouse=True)
def _restore_comb_after():
    yield
    # always restore factory comb after each test
    try:
        requests.delete(f"{API}/comb", timeout=10)
    except Exception:
        pass


# --------------- bug: stagger ---------------
def test_analyze_staggers_chord():
    files = {"file": ("chord.mid", _chord_midi(), "audio/midi")}
    r = requests.post(f"{API}/analyze", files=files,
                      data={"duration": "25", "start": "0",
                            "auto_transpose": "false", "manual_offset": "0"},
                      timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["staggered"] >= 2, f"expected staggered>=2, got {j['staggered']}"
    # No beat column contains more than one True
    part = j["partition"]
    beats = len(part[0])
    for b in range(beats):
        col = sum(1 for t in range(len(part)) if part[t][b])
        assert col <= 1, f"beat {b} has {col} simultaneous notes"


def test_analyze_twinkle_unchanged():
    files = {"file": ("sample_twinkle.mid", _midi_bytes(), "audio/midi")}
    r = requests.post(f"{API}/analyze", files=files,
                      data={"duration": "25", "start": "0",
                            "auto_transpose": "true", "manual_offset": "0"},
                      timeout=60)
    assert r.status_code == 200
    j = r.json()
    assert j["staggered"] == 0
    assert j["note_count"] == 28


# --------------- press record_no + overrides ---------------
@pytest.fixture(scope="module")
def twinkle_analysis():
    files = {"file": ("sample_twinkle.mid", _midi_bytes(), "audio/midi")}
    data = {"duration": "25", "start": "0", "auto_transpose": "true", "manual_offset": "0"}
    r = requests.post(f"{API}/analyze", files=files, data=data, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def test_press_with_record_no_42(twinkle_analysis):
    payload = {
        "title": "TEST_RN42",
        "partition": twinkle_analysis["partition"],
        "record_no": 42,
    }
    r = requests.post(f"{API}/press", json=payload, timeout=180)
    assert r.status_code == 200, r.text
    assert r.json()["record_no"] == 42


def test_press_auto_record_no(twinkle_analysis):
    payload = {
        "title": "TEST_AutoRN_unique_xyz",
        "partition": twinkle_analysis["partition"],
    }
    r = requests.post(f"{API}/press", json=payload, timeout=180)
    assert r.status_code == 200, r.text
    rn = r.json()["record_no"]
    assert rn >= 6


def test_press_with_overrides_echo(twinkle_analysis):
    # Find a beat where tone 7 has a note (twin tone)
    part = twinkle_analysis["partition"]
    tone = 7
    beat = next((b for b, on in enumerate(part[tone]) if on), None)
    if beat is None:
        pytest.skip("no tone-7 note in Twinkle sample")
    overrides = {f"{tone}-{beat}": 1}
    payload = {
        "title": "TEST_Over",
        "partition": part,
        "overrides": overrides,
    }
    r = requests.post(f"{API}/press", json=payload, timeout=180)
    assert r.status_code == 200, r.text
    assert r.json().get("overrides") == overrides


def test_next_record_no_endpoint():
    r = requests.get(f"{API}/next-record-no", params={"title": ""}, timeout=10)
    assert r.status_code == 200
    assert "record_no" in r.json()


# --------------- comb ---------------
def test_get_factory_comb():
    r = requests.get(f"{API}/comb", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["factory"] is True
    assert len(j["tracks"]) == 22
    assert len(j["notes"]) == 16


def test_put_comb_recomputes_tones():
    tracks = FACTORY_TRACKS.copy()
    # Replace a 95 with 96 → 15 unique notes
    tracks[19] = 96  # was 95
    r = requests.put(f"{API}/comb", json={"tracks": tracks}, timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["notes"]) == 15
    assert j["factory"] is False
    # Analyze now returns 15-row partition
    files = {"file": ("sample_twinkle.mid", _midi_bytes(), "audio/midi")}
    ra = requests.post(f"{API}/analyze", files=files,
                      data={"duration": "25", "start": "0",
                            "auto_transpose": "true", "manual_offset": "0"},
                      timeout=60)
    assert ra.status_code == 200
    assert len(ra.json()["partition"]) == 15
    # Press with 16 rows -> 400
    bad = [[False] * BEATS for _ in range(16)]
    bad[0][0] = True
    rp = requests.post(f"{API}/press", json={"title": "x", "partition": bad}, timeout=30)
    assert rp.status_code == 400


def test_put_comb_unsorted_rejected():
    tracks = FACTORY_TRACKS.copy()
    tracks[0], tracks[1] = tracks[1], tracks[0]  # make unsorted
    r = requests.put(f"{API}/comb", json={"tracks": tracks}, timeout=10)
    assert r.status_code == 400


def test_put_comb_wrong_length_rejected():
    r = requests.put(f"{API}/comb", json={"tracks": FACTORY_TRACKS[:21]}, timeout=10)
    assert r.status_code in (400, 422)


def test_delete_comb_restores_factory():
    # Mutate first
    tracks = FACTORY_TRACKS.copy()
    tracks[19] = 96
    requests.put(f"{API}/comb", json={"tracks": tracks}, timeout=10)
    r = requests.delete(f"{API}/comb", timeout=10)
    assert r.status_code == 200
    assert r.json()["factory"] is True
    # Confirm
    r2 = requests.get(f"{API}/comb", timeout=10)
    assert r2.json()["tracks"] == FACTORY_TRACKS


# --------------- library ---------------
def test_library_returns_10_tunes():
    r = requests.get(f"{API}/library", timeout=60)
    assert r.status_code == 200
    tunes = r.json()
    assert len(tunes) == 10
    for t in tunes:
        assert "title" in t
        assert "analysis" in t
        part = t["analysis"]["partition"]
        assert len(part) == 16
        assert len(part[0]) == BEATS


# --------------- scan ---------------
def test_scan_twinkle():
    files = {"file": ("sample_twinkle.mid", _midi_bytes(), "audio/midi")}
    r = requests.post(f"{API}/scan", files=files, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert len(j["events"]) == 28
    assert 10 < j["total"] < 15  # ~12s


def test_scan_rejects_non_midi():
    files = {"file": ("foo.txt", b"not midi", "text/plain")}
    r = requests.post(f"{API}/scan", files=files, timeout=10)
    assert r.status_code == 400
