"""Iteration 11: chord roll direction (before/after), mesh-check.txt in pack."""
import io
import os
import zipfile
from pathlib import Path

import mido
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"


def _empty(tones=16, beats=86):
    return [[False] * beats for _ in range(tones)]


def _midi_bytes(events):
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    msgs = []
    for pitch, start, dur in events:
        msgs.append((start, "note_on", pitch))
        msgs.append((start + dur, "note_off", pitch))
    msgs.sort(key=lambda x: (x[0], 0 if x[1] == "note_off" else 1))
    prev = 0.0
    for t, typ, pitch in msgs:
        delta_sec = max(0.0, t - prev)
        ticks = int(round(delta_sec * 960))
        track.append(mido.Message(typ, note=pitch, velocity=80, time=ticks))
        prev = t
    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


# ---------- /api/press roll ------------------------------------------------
def test_press_chord_roll_after():
    part = _empty()
    part[1][10] = True
    part[3][10] = True
    part[5][10] = True  # top note = tone 5
    r = requests.post(
        f"{API}/press",
        json={"title": "TEST_Iter11_RollAfter", "partition": part, "roll": "after"},
        timeout=240,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["roll"] == "after"
    p = rec["partition"]
    # tone 5 stays on 10
    assert p[5][10] is True
    # tones 1 and 3 land on beats > 10
    def beat_of(row):
        return next((b for b, v in enumerate(row) if v), None)
    b1, b3 = beat_of(p[1]), beat_of(p[3])
    assert b1 is not None and b1 > 10, f"tone1 landed at {b1}"
    assert b3 is not None and b3 > 10, f"tone3 landed at {b3}"
    # echoed by GET
    g = requests.get(f"{API}/conversions/{rec['id']}", timeout=20).json()
    assert g["roll"] == "after"


def test_press_chord_roll_before():
    part = _empty()
    part[1][10] = True
    part[3][10] = True
    part[5][10] = True
    r = requests.post(
        f"{API}/press",
        json={"title": "TEST_Iter11_RollBefore", "partition": part, "roll": "before"},
        timeout=240,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["roll"] == "before"
    p = rec["partition"]
    assert p[5][10] is True
    def beat_of(row):
        return next((b for b, v in enumerate(row) if v), None)
    b1, b3 = beat_of(p[1]), beat_of(p[3])
    assert b1 is not None and b1 < 10, f"tone1 landed at {b1}"
    assert b3 is not None and b3 < 10, f"tone3 landed at {b3}"


def test_press_invalid_roll_422():
    part = _empty()
    part[0][0] = True
    r = requests.post(
        f"{API}/press",
        json={"title": "TEST_Iter11_bad", "partition": part, "roll": "sideways"},
        timeout=30,
    )
    assert r.status_code == 422, r.text


# ---------- /api/analyze roll ----------------------------------------------
def test_analyze_chord_middle_roll_before_after():
    # 3 simultaneous notes at t=5s, duration 25s
    events = [(72, 5.0, 0.3), (76, 5.0, 0.3), (79, 5.0, 0.3)]
    midi = _midi_bytes(events)
    for roll in ("before", "after"):
        r = requests.post(
            f"{API}/analyze",
            files={"file": ("test.mid", midi, "audio/midi")},
            data={"duration": 25.0, "start": 0.0, "auto_transpose": "true", "roll": roll},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["staggered"] == 2, f"roll={roll} staggered={data['staggered']}"
        assert data["dropped"] == 0, f"roll={roll} dropped={data['dropped']}"
        p = data["partition"]
        # Locate the three placed notes (should be on 3 different tones)
        placed = [(t, b) for t in range(len(p)) for b in range(len(p[0])) if p[t][b]]
        assert len(placed) == 3
        # top (highest tone index) note stays at its beat
        placed_sorted_by_tone = sorted(placed, key=lambda x: x[0])
        top_tone, top_beat = placed_sorted_by_tone[-1]
        others = placed_sorted_by_tone[:-1]
        if roll == "before":
            for _, b in others:
                assert b <= top_beat, f"before: {b} > top {top_beat}"
        else:
            for _, b in others:
                assert b >= top_beat, f"after: {b} < top {top_beat}"


# ---------- /api/conversions/{id}/pack mesh-check.txt + README -------------
def test_pack_contains_mesh_check_txt():
    part = _empty()
    part[0][0] = True
    part[2][20] = True
    part[4][40] = True
    r = requests.post(
        f"{API}/press",
        json={"title": "TEST_Iter11_Pack", "partition": part},
        timeout=240,
    )
    assert r.status_code == 200, r.text
    rec_id = r.json()["id"]
    pr = requests.get(f"{API}/conversions/{rec_id}/pack", timeout=60)
    assert pr.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(pr.content))
    names = z.namelist()
    assert "mesh-check.txt" in names, names
    mc_txt = z.read("mesh-check.txt").decode()
    assert "Verdict: PRINT READY" in mc_txt, mc_txt
    assert "watertight (no holes) ............ yes" in mc_txt, mc_txt
    readme = z.read("README.txt").decode()
    assert "mesh-check.txt" in readme


@pytest.fixture(scope="module", autouse=True)
def restore_numbering_at_end():
    yield
    try:
        requests.put(f"{API}/numbering", json={"start": 6}, timeout=10)
    except Exception:
        pass
