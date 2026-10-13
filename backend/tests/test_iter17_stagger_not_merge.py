"""Iter17: verify same-pitch collisions are STAGGERED (not merged) in events_to_record.

User bug: dense same-pitch notes were being merged (counted as 4904 lost). Fix:
when a second note of the same pitch lands on a used beat, try to place it on
the nearest free beat (reach +/- 8) following the one-pin-per-beat rule. Only
count `merged` when truly no room is available.
"""
import os
import pytest
import requests
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ASSETS = "/app/tests/assets"
BABY = f"{ASSETS}/user/baby1.mid"


def _build_midi(path, events, total_sec=25.0, bpm=120):
    """events: list of (start_time_sec, pitch, dur_sec)"""
    mid = MidiFile(ticks_per_beat=480)
    tempo = bpm2tempo(bpm)
    tps = 480 * 1_000_000 / tempo  # ticks per second
    tr = MidiTrack()
    mid.tracks.append(tr)
    tr.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    # Build timed on/off list
    msgs = []
    for t, pitch, d in events:
        msgs.append((t, "on", pitch))
        msgs.append((t + d, "off", pitch))
    msgs.sort(key=lambda x: (x[0], 0 if x[1] == "off" else 1))
    last = 0.0
    for t, kind, pitch in msgs:
        delta_ticks = max(0, int(round((t - last) * tps)))
        tr.append(Message("note_on" if kind == "on" else "note_off",
                          note=pitch, velocity=80 if kind == "on" else 0,
                          time=delta_ticks))
        last = t
    # pad to total_sec
    pad = max(0, int(round((total_sec - last) * tps)))
    tr.append(MetaMessage("end_of_track", time=pad))
    mid.save(path)


# ---------- 1) 4 same-pitch within 0.1s -> stagger not merge ----------
def test_same_pitch_four_in_a_row_staggered(tmp_path):
    midi = tmp_path / "same4.mid"
    _build_midi(midi, [(5.0 + i * 0.025, 72, 0.05) for i in range(4)], total_sec=25.0)
    with open(midi, "rb") as f:
        r = requests.post(f"{API}/analyze",
                          files={"file": ("same4.mid", f, "audio/midi")},
                          data={"duration": 25.0, "auto_transpose": "false"})
    assert r.status_code == 200, r.text
    j = r.json()
    stats = j.get("stats", j)
    assert stats["note_count"] == 4, stats
    assert stats["merged"] == 0, f"expected merged=0, got {stats['merged']}"
    assert stats["dropped"] == 0
    assert stats["staggered"] >= 3, f"expected staggered>=3, got {stats['staggered']}"
    # count pins actually placed in the partition
    partition = j.get("partition") or j.get("sides", [{}])[0].get("partition")
    assert partition is not None
    total_pins = sum(sum(1 for v in row if v) for row in partition)
    assert total_pins == 4, f"expected 4 distinct pins placed, got {total_pins}"
    # One pin per beat (mono)
    beats = len(partition[0])
    per_beat_counts = [sum(row[b] for row in partition) for b in range(beats)]
    assert max(per_beat_counts) == 1


# ---------- 2) Dense 250 notes -> accounting is tight ----------
def test_dense_same_pitch_accounting(tmp_path):
    midi = tmp_path / "dense.mid"
    events = [(0.1 * i, 72, 0.05) for i in range(250)]
    _build_midi(midi, events, total_sec=25.0)
    with open(midi, "rb") as f:
        r = requests.post(f"{API}/analyze",
                          files={"file": ("dense.mid", f, "audio/midi")},
                          data={"duration": 25.0, "auto_transpose": "false"})
    assert r.status_code == 200, r.text
    j = r.json()
    stats = j.get("stats", j)
    partition = j.get("partition") or j.get("sides", [{}])[0].get("partition")
    pins = sum(sum(1 for v in row if v) for row in partition)
    assert pins <= 86, f"pins exceeds beats-per-rev: {pins}"
    assert stats["note_count"] == 250
    assert stats["staggered"] > 0
    # accounting: pins + merged + dropped == note_count
    assert pins + stats["merged"] + stats["dropped"] == 250, (
        f"accounting mismatch pins={pins} merged={stats['merged']} dropped={stats['dropped']}")
    # One pin per beat
    beats = len(partition[0])
    per_beat_counts = [sum(row[b] for row in partition) for b in range(beats)]
    assert max(per_beat_counts) == 1


# ---------- 3) baby1 full disc + skyline: staggered fills instead of merging ----------
def test_baby1_skyline_fills_by_staggering():
    with open(BABY, "rb") as f:
        r = requests.post(f"{API}/analyze",
                          files={"file": ("baby1.mid", f, "audio/midi")},
                          data={"start": 18.7, "duration": 25.0, "tracks": "",
                                "skyline": "true"})
    assert r.status_code == 200, r.text
    j = r.json()
    stats = j.get("stats", j)
    nc = stats["note_count"]
    partition = j.get("partition") or j.get("sides", [{}])[0].get("partition")
    pins = sum(sum(1 for v in row if v) for row in partition)
    assert stats["merged"] < nc / 2, f"too many merged: {stats['merged']}/{nc}"
    assert pins >= 80, f"pins too low: {pins}"


def test_baby1_chords_true_pins_many():
    with open(BABY, "rb") as f:
        r = requests.post(f"{API}/analyze",
                          files={"file": ("baby1.mid", f, "audio/midi")},
                          data={"start": 18.7, "duration": 25.0, "tracks": "",
                                "chords": "true"})
    assert r.status_code == 200, r.text
    j = r.json()
    stats = j.get("stats", j)
    partition = j.get("partition") or j.get("sides", [{}])[0].get("partition")
    pins = sum(sum(1 for v in row if v) for row in partition)
    assert pins > 300, f"expected pins>300 with chords, got {pins}"
    assert pins + stats["merged"] + stats["dropped"] == stats["note_count"], (
        f"accounting pins={pins} m={stats['merged']} d={stats['dropped']} nc={stats['note_count']}")


# ---------- 4) baby1 melody-only track -> clean ----------
def test_baby1_melody_only_clean():
    with open(BABY, "rb") as f:
        r = requests.post(f"{API}/analyze",
                          files={"file": ("baby1.mid", f, "audio/midi")},
                          data={"tracks": "5"})
    assert r.status_code == 200, r.text
    j = r.json()
    stats = j.get("stats", j)
    assert stats["merged"] == 0, f"melody-only should not merge: {stats['merged']}"
    assert stats["dropped"] == 0, f"melody-only should not drop: {stats['dropped']}"
