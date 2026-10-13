"""Iter16: verify chords option (no staggering) and autofit transposition tries budget."""
import io
import os
import struct
import wave

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ASSETS = "/app/tests/assets"
BABY = f"{ASSETS}/user/baby1.mid"

TONES = 16
BEATS = 86


def _empty_partition():
    return [[False] * BEATS for _ in range(TONES)]


def _press_payload(partition, chords):
    return {
        "title": "ChordTest",
        "partition": partition,
        "filename": "chord.mid",
        "duration": 25.0,
        "offset": 0,
        "chords": chords,
    }


# ---------- /api/press chord preserved when chords=true ----------
def test_press_chords_true_keeps_chord_pins():
    p = _empty_partition()
    # chord at beat 10 on tones 1, 3, 5 (indices)
    for t in (1, 3, 5):
        p[t][10] = True
    r = requests.post(f"{API}/press", json=_press_payload(p, True), timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chords"] is True
    assert body["toy_fixes"] == 0
    assert body["mesh_check"]["ok"] is True
    out = body["partition"]
    assert out[1][10] is True
    assert out[3][10] is True
    assert out[5][10] is True
    # Total of 3 pins still, nothing rolled elsewhere
    total = sum(sum(1 for v in row if v) for row in out)
    assert total == 3


def test_press_chords_false_rolls_chord_pins():
    p = _empty_partition()
    for t in (1, 3, 5):
        p[t][10] = True
    r = requests.post(f"{API}/press", json=_press_payload(p, False), timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    out = body["partition"]
    # Collect beats of pins
    beats_at_each_tone = {t: [b for b, v in enumerate(out[t]) if v] for t in (1, 3, 5)}
    all_beats = [bs[0] for bs in beats_at_each_tone.values() if bs]
    # With rolling, beats differ (at most one at beat 10)
    assert len(set(all_beats)) > 1, f"Expected rolled beats, got {beats_at_each_tone}"


# ---------- /api/analyze with a crafted chord MIDI ----------
def _build_chord_midi(path):
    """Minimal single-track MIDI: 3-note chord-on at t=5s (and off at ~5.5s)."""
    import mido
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    # tempo 500000 us/beat = 120 bpm -> 1 beat = 0.5 s -> 5 s = 10 beats = 4800 ticks
    tr.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    tr.append(mido.Message("note_on", note=60, velocity=90, time=4800))
    tr.append(mido.Message("note_on", note=64, velocity=90, time=0))
    tr.append(mido.Message("note_on", note=67, velocity=90, time=0))
    tr.append(mido.Message("note_off", note=60, velocity=0, time=240))
    tr.append(mido.Message("note_off", note=64, velocity=0, time=0))
    tr.append(mido.Message("note_off", note=67, velocity=0, time=0))
    mid.save(path)


@pytest.fixture(scope="module")
def chord_midi(tmp_path_factory):
    p = tmp_path_factory.mktemp("iter16") / "chord.mid"
    _build_chord_midi(str(p))
    return str(p)


def _analyze(midi_path, chords):
    with open(midi_path, "rb") as f:
        r = requests.post(
            f"{API}/analyze",
            files={"file": ("chord.mid", f.read(), "audio/midi")},
            data={"start": 0.0, "duration": 10.0, "chords": "true" if chords else "false"},
            timeout=120,
        )
    return r


def test_analyze_chords_true_keeps_three_pins_same_beat(chord_midi):
    r = _analyze(chord_midi, True)
    assert r.status_code == 200, r.text
    body = r.json()
    part = body["partition"]
    # Find the beat with the chord: should be beat where 3 tones are True
    beats_count = [sum(1 for row in part if row[b]) for b in range(BEATS)]
    max_beat_hits = max(beats_count)
    assert max_beat_hits == 3, f"expected 3 pins on one beat, got {max_beat_hits} ({beats_count})"
    assert body.get("staggered", 0) == 0


def test_analyze_chords_false_rolls_chord(chord_midi):
    r = _analyze(chord_midi, False)
    assert r.status_code == 200, r.text
    body = r.json()
    part = body["partition"]
    beats_count = [sum(1 for row in part if row[b]) for b in range(BEATS)]
    assert max(beats_count) <= 1, f"with chords=false expected at most 1 pin/beat, got {max(beats_count)}"


# ---------- /api/autofit transposition offset + budget ----------
def test_autofit_baby_offset_and_budget():
    with open(BABY, "rb") as f:
        data = f.read()
    r = requests.post(
        f"{API}/autofit",
        files={"file": ("baby1.mid", data, "audio/midi")},
        data={"start": 18.5, "tracks": "5", "melody_fill": "true"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    fit = r.json()["fit"]
    assert isinstance(fit["offset"], int)
    assert fit["score"] >= 90, fit
    assert fit["tries"] <= 12000


def test_autofit_baby_respects_max_tries():
    with open(BABY, "rb") as f:
        data = f.read()
    r = requests.post(
        f"{API}/autofit",
        files={"file": ("baby1.mid", data, "audio/midi")},
        data={"start": 18.5, "tracks": "5", "melody_fill": "true", "max_tries": "500"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    fit = r.json()["fit"]
    assert fit["tries"] <= 500


# ---------- /api/render with chords=true ----------
def test_render_chords_true_8khz_mono():
    with open(BABY, "rb") as f:
        r = requests.post(
            f"{API}/render",
            files={"file": ("baby1.mid", f.read(), "audio/midi")},
            data={"tracks": "5", "chords": "true"},
            timeout=180,
        )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/wav")
    assert r.headers.get("X-Sample-Rate") == "8000"
    wf = wave.open(io.BytesIO(r.content))
    try:
        assert wf.getframerate() == 8000
        assert wf.getnchannels() == 1
    finally:
        wf.close()
