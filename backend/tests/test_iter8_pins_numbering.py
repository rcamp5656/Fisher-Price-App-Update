"""Iteration 8: equilateral triangle pins, playable rule relaxation, numbering start."""
import io
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
MIDI_PATH = "/app/tests/assets/sample_twinkle.mid"


# ----------------- /api/analyze (relaxed playable rule) -----------------
def test_analyze_twinkle_duration_25_no_drops():
    with open(MIDI_PATH, "rb") as f:
        r = requests.post(f"{API}/analyze",
                          files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
                          data={"duration": 25.0, "start": 0.0,
                                "auto_transpose": "true", "manual_offset": 0},
                          timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dropped"] == 0, f"expected 0 dropped, got {data['dropped']}"
    assert data["note_count"] == 28, f"expected 28 notes, got {data['note_count']}"
    partition = data["partition"]
    beats = len(partition[0])
    # one note per beat column
    for b in range(beats):
        col = sum(1 for row in partition for v in [row[b]] if v)
        assert col <= 1, f"beat {b} has {col} notes"
    # single-tine rows: tones 0-6 and 13-15 — no consecutive beats
    single_tone_idxs = list(range(0, 7)) + list(range(13, 16))
    for t in single_tone_idxs:
        row = partition[t]
        for b in range(beats):
            if row[b] and row[(b + 1) % beats]:
                pytest.fail(f"single tine {t} has consecutive beats at {b}")
    # partition_midi should contain 28 note cells
    pm = data["partition_midi"]
    pm_cnt = sum(1 for row in pm for v in row if v)
    assert pm_cnt == 28, f"partition_midi expected 28, got {pm_cnt}"


def test_analyze_dense_repeat_drops_and_spaces():
    # Build a MIDI with same single pitch repeated every 0.15s for 3s
    import mido
    mid = mido.MidiFile()
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tempo = mido.bpm2tempo(120)
    tr.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    ticks_per_beat = mid.ticks_per_beat
    # 0.15 s per note at 120 bpm. beat = 0.5 s => 0.15s = 0.3 beat = 0.3*480 = 144 ticks
    pitch = 72  # C5
    dt = int(0.15 * (ticks_per_beat * 2))  # 2 beats/sec at 120bpm
    for i in range(20):
        tr.append(mido.Message("note_on", note=pitch, velocity=90, time=0 if i else 0))
        tr.append(mido.Message("note_off", note=pitch, velocity=0, time=dt))
    buf = io.BytesIO()
    mid.save(file=buf)
    buf.seek(0)
    r = requests.post(f"{API}/analyze",
                      files={"file": ("dense.mid", buf.read(), "audio/midi")},
                      data={"duration": 25.0, "start": 0.0,
                            "auto_transpose": "true", "manual_offset": 0},
                      timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dropped"] == 0, f"notes slide to free beats, never dropped; got {data['dropped']}"
    assert data["staggered"] > 0, "dense repeats must be staggered apart"
    partition = data["partition"]
    beats = len(partition[0])
    for b in range(beats):
        assert sum(1 for row in partition if row[b]) <= 1, f"beat {b} holds more than one pin"
    for row in partition:
        hits = [b for b, v in enumerate(row) if v]
        if len(hits) >= 2:
            for i in range(len(hits) - 1):
                assert hits[i + 1] - hits[i] >= 2, f"single tine strikes on consecutive beats {hits[i]},{hits[i + 1]}"
            break


# ----------------- /api/numbering -----------------
@pytest.fixture(scope="module")
def restore_numbering():
    yield
    requests.put(f"{API}/numbering", json={"start": 6}, timeout=10)


def test_numbering_put_get(restore_numbering):
    r = requests.put(f"{API}/numbering", json={"start": 150}, timeout=10)
    assert r.status_code == 200
    assert r.json()["start"] == 150
    r = requests.get(f"{API}/numbering", timeout=10)
    assert r.status_code == 200
    assert r.json()["start"] == 150


def test_next_record_no_uses_numbering_start(restore_numbering):
    requests.put(f"{API}/numbering", json={"start": 150}, timeout=10)
    r = requests.get(f"{API}/next-record-no",
                     params={"title": "TEST_NeverUsedTitleXYZ"}, timeout=10)
    assert r.status_code == 200
    # should be >=150
    assert r.json()["record_no"] >= 150


def test_press_without_record_no_uses_numbering(restore_numbering):
    requests.put(f"{API}/numbering", json={"start": 150}, timeout=10)
    with open(MIDI_PATH, "rb") as f:
        a = requests.post(f"{API}/analyze",
                         files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
                         data={"duration": 25.0, "start": 0.0,
                               "auto_transpose": "true", "manual_offset": 0},
                         timeout=30).json()
    r1 = requests.post(f"{API}/press", json={
        "title": "TEST_Iter8_Num1",
        "partition": a["partition"],
    }, timeout=180)
    assert r1.status_code == 200, r1.text
    rec1 = r1.json()
    assert rec1["record_no"] >= 150
    first_no = rec1["record_no"]
    r2 = requests.post(f"{API}/press", json={
        "title": "TEST_Iter8_Num2",
        "partition": a["partition"],
    }, timeout=180)
    assert r2.status_code == 200
    assert r2.json()["record_no"] == first_no + 1


def test_numbering_bounds():
    r = requests.put(f"{API}/numbering", json={"start": 0}, timeout=10)
    assert r.status_code == 422
    r = requests.put(f"{API}/numbering", json={"start": 1000}, timeout=10)
    assert r.status_code == 422


# ----------------- /api/press pin_radius default & SCAD -----------------
def test_press_default_pin_radius_is_0_8():
    with open(MIDI_PATH, "rb") as f:
        a = requests.post(f"{API}/analyze",
                         files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
                         data={"duration": 25.0, "start": 0.0,
                               "auto_transpose": "true", "manual_offset": 0},
                         timeout=30).json()
    r = requests.post(f"{API}/press", json={
        "title": "TEST_Iter8_PinDefault",
        "partition": a["partition"],
    }, timeout=180)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec.get("pin_radius") == 0.8, f"default pin_radius should be 0.8, got {rec.get('pin_radius')}"
    # SCAD contains pinDepth = 0.8 and sqrt(3)
    scad = requests.get(f"{API}/conversions/{rec['id']}/scad", timeout=20).text
    assert "pinDepth = 0.8" in scad
    assert "sqrt(3)" in scad


def test_press_pin_radius_0_3_rejected():
    with open(MIDI_PATH, "rb") as f:
        a = requests.post(f"{API}/analyze",
                         files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
                         data={"duration": 25.0, "start": 0.0,
                               "auto_transpose": "true", "manual_offset": 0},
                         timeout=30).json()
    r = requests.post(f"{API}/press", json={
        "title": "TEST_Iter8_PinTooLow",
        "partition": a["partition"],
        "pin_radius": 0.3,
    }, timeout=30)
    assert r.status_code == 422
