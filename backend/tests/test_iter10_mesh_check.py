"""Iteration 10: whole-disc one-pin-per-beat rule, dropped==0 (unless disc full),
mesh_check panel in /api/press and GET /api/conversions/{id}."""
import io
import os
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

SINGLE_TINE = set(list(range(0, 7)) + list(range(13, 16)))


# ---------- helpers --------------------------------------------------------
def _midi_bytes(events):
    """events = [(midi_pitch, start_sec, dur_sec)] -> raw MIDI bytes."""
    mid = mido.MidiFile(ticks_per_beat=480)
    tempo = 500000  # 120 bpm, 480 tpb -> 1 sec = 960 ticks? No: 480 tpb * (1_000_000/tempo) ticks/sec
    # 1 beat = 0.5s so 1 sec = 960 ticks
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    # Build absolute-time list of on/off, then delta
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


def _no_column_double(partition):
    beats = len(partition[0])
    for b in range(beats):
        col = sum(1 for row in partition if row[b])
        assert col <= 1, f"beat {b} has {col} pins across rows"


def _no_consecutive_single_tines(partition):
    beats = len(partition[0])
    for t in SINGLE_TINE:
        row = partition[t]
        for b in range(beats - 1):
            assert not (row[b] and row[b + 1]), f"single-tine {t} consecutive at {b}"


# ---------- /api/analyze --------------------------------------------------
def test_analyze_chord_at_zero_then_singles_no_drops():
    """Chord of 3 notes at t=0 followed by single notes should stagger >=2
    and drop 0. No beat column > 1 pin across all rows."""
    # Twinkle factory tones C D E G A map to MIDI 60 62 64 67 69 (middle=60)
    events = [
        (60, 0.0, 0.3), (64, 0.0, 0.3), (67, 0.0, 0.3),  # chord of 3
        (62, 0.5, 0.3), (64, 1.0, 0.3), (65, 1.5, 0.3),
        (67, 2.0, 0.3), (69, 2.5, 0.3), (71, 3.0, 0.3),
    ]
    midi = _midi_bytes(events)
    r = requests.post(
        f"{API}/analyze",
        files={"file": ("test.mid", midi, "audio/midi")},
        data={"duration": 25.0, "start": 0.0, "auto_transpose": "true"},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dropped"] == 0, f"dropped should be 0, got {data['dropped']}"
    assert data["staggered"] >= 2, f"staggered should be >=2, got {data['staggered']}"
    _no_column_double(data["partition"])


def test_analyze_dense_same_pitch_single_tine_no_drops():
    """Dense same-pitch repeats on a single-tine pitch (MIDI 72 == C5) every 0.15s
    for 3s. With dropped==0 and single-tine spacing >=2 beats."""
    events = [(72, i * 0.15, 0.1) for i in range(20)]  # 20 strikes
    midi = _midi_bytes(events)
    r = requests.post(
        f"{API}/analyze",
        files={"file": ("test.mid", midi, "audio/midi")},
        data={"duration": 25.0, "start": 0.0, "auto_transpose": "false"},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dropped"] == 0, f"dropped should be 0, got {data['dropped']}"
    assert data["staggered"] > 0
    _no_column_double(data["partition"])
    # On any single-tine row, consecutive beats forbidden (gap>=2)
    _no_consecutive_single_tines(data["partition"])


# ---------- /api/press -----------------------------------------------------
def _empty(tones=16, beats=86):
    return [[False] * beats for _ in range(tones)]


def test_press_chord_slide_mesh_check_ok():
    """Chord on beat 10 (tones 1,3,5), tone 4 on 30+31 (single-tine clash),
    twin tone 7 on 40+41 (twin may repeat). Expect toy_fixes==3, mesh_check.ok."""
    part = _empty()
    part[1][10] = True
    part[3][10] = True
    part[5][10] = True   # chord: 2 rolls needed
    part[4][30] = True
    part[4][31] = True   # single-tine consecutive: 1 slide
    part[7][40] = True
    part[7][41] = True   # twin tines: untouched
    r = requests.post(
        f"{API}/press",
        json={"title": "TEST_Iter10_MeshOK", "partition": part},
        timeout=240,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["toy_fixes"] == 3, f"toy_fixes expected 3 got {rec['toy_fixes']}"
    _no_column_double(rec["partition"])
    _no_consecutive_single_tines(rec["partition"])
    # twin tone 7 unchanged
    assert rec["partition"][7][40] and rec["partition"][7][41]
    mc = rec.get("mesh_check")
    assert mc is not None, "mesh_check missing"
    assert mc.get("ok") is True, mc
    assert mc.get("watertight") is True, mc
    assert mc.get("winding_consistent") is True, mc
    assert mc.get("open_edges_after") == 0, mc
    assert mc.get("faces", 0) > 0
    assert mc.get("volume_mm3", 0) > 0
    # GET /api/conversions/{id} echoes mesh_check
    g = requests.get(f"{API}/conversions/{rec['id']}", timeout=20).json()
    assert g.get("mesh_check") == mc


def test_press_two_sided_mesh_halves_ok():
    """Two-sided (partition_b supplied, thickness 5) -> halves_ok True, echoed."""
    part_a = _empty()
    part_b = _empty()
    for i, b in enumerate(range(0, 80, 8)):
        part_a[i % 16][b] = True
        part_b[(i + 2) % 16][b] = True
    r = requests.post(
        f"{API}/press",
        json={
            "title": "TEST_Iter10_HalvesA",
            "title_b": "TEST_Iter10_HalvesB",
            "partition": part_a,
            "partition_b": part_b,
            "thickness": 5.0,
        },
        timeout=240,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    mc = rec["mesh_check"]
    assert mc.get("halves_ok") is True, mc
    assert mc.get("ok") is True, mc
    g = requests.get(f"{API}/conversions/{rec['id']}", timeout=20).json()
    assert g["mesh_check"] == mc


@pytest.fixture(scope="module", autouse=True)
def restore_numbering_at_end():
    yield
    requests.put(f"{API}/numbering", json={"start": 6}, timeout=10)
