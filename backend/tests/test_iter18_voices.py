"""Iter18: voices (simple chords) — backend behaviour on analyze, press, render."""
import os
import pathlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
BABY1 = pathlib.Path("/app/tests/assets/user/baby1.mid")


def _analyze(voices, chords=True, start=18.7, duration=25):
    with BABY1.open("rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/analyze",
            files={"file": ("baby1.mid", f, "audio/midi")},
            data={
                "start": str(start),
                "duration": str(duration),
                "tracks": "",
                "chords": str(chords).lower(),
                "voices": str(voices),
                "auto_transpose": "true",
                "roll": "before",
                "rev_seconds": "25",
            },
            timeout=120,
        )
    assert r.status_code == 200, r.text
    return r.json()


def _max_pins_per_beat(partition):
    cols = len(partition[0])
    return max(sum(row[b] for row in partition) for b in range(cols))


def _total_pins(partition):
    return sum(sum(row) for row in partition)


@pytest.mark.parametrize("voices,expected_max", [(1, 1), (2, 2), (3, 3)])
def test_analyze_voices_limits_max_pins_per_beat(voices, expected_max):
    data = _analyze(voices)
    partition = data["partition"]
    assert _max_pins_per_beat(partition) <= expected_max
    pins = _total_pins(partition)
    assert pins + data["merged"] + data["dropped"] == data["note_count"], (
        f"voices={voices} pins={pins} merged={data['merged']} dropped={data['dropped']} nc={data['note_count']}"
    )


def test_analyze_voices_16_allows_fat_chords():
    data = _analyze(16, chords=True)
    assert _max_pins_per_beat(data["partition"]) > 3
    pins = _total_pins(data["partition"])
    assert pins + data["merged"] + data["dropped"] == data["note_count"]


def test_press_voices_422_bounds():
    # minimal valid partition — 16 x 86
    partition = [[False] * 86 for _ in range(16)]
    partition[5][10] = True
    body = {"title": "T", "partition": partition, "voices": 0}
    r = requests.post(f"{BASE_URL}/api/press", json=body, timeout=30)
    assert r.status_code == 422
    body["voices"] = 17
    r = requests.post(f"{BASE_URL}/api/press", json=body, timeout=30)
    assert r.status_code == 422


def test_press_4note_chord_voices_2_keeps_top_and_bottom():
    """4-note chord at beat 10 at tones 1,3,5,7; voices=2 keeps 7 (top) and 1 (bottom)."""
    partition = [[False] * 86 for _ in range(16)]
    for tone in (1, 3, 5, 7):
        partition[tone][10] = True
    body = {
        "title": "ChordTest",
        "partition": partition,
        "voices": 2,
        "chords": True,
        "roll": "before",
    }
    r = requests.post(f"{BASE_URL}/api/press", json=body, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["voices"] == 2
    assert data["chords"] is True
    assert data["mesh_check"]["ok"] is True
    p = data["partition"]
    # beat 10 keeps top (7) and bottom (1); max 2 pins at that beat
    assert p[7][10] is True, "top note (tone 7) must stay on beat 10"
    assert p[1][10] is True, "bottom note (tone 1) must stay on beat 10"
    beat10_pins = sum(row[10] for row in p)
    assert beat10_pins == 2
    # extra notes (tones 3 and 5) land on beats 6..14 or are dropped
    for tone in (3, 5):
        on_beats = [b for b in range(86) if p[tone][b]]
        for b in on_beats:
            assert 6 <= b <= 14, f"tone {tone} ended up at beat {b}"


def test_press_4note_chord_voices_3_keeps_three():
    partition = [[False] * 86 for _ in range(16)]
    for tone in (1, 3, 5, 7):
        partition[tone][10] = True
    body = {"title": "V3", "partition": partition, "voices": 3, "chords": True}
    r = requests.post(f"{BASE_URL}/api/press", json=body, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["voices"] == 3
    beat10_pins = sum(row[10] for row in data["partition"])
    assert beat10_pins == 3


def test_press_4note_chord_voices_1_rolls_to_one_per_beat():
    partition = [[False] * 86 for _ in range(16)]
    for tone in (1, 3, 5, 7):
        partition[tone][10] = True
    body = {"title": "V1", "partition": partition, "voices": 1, "chords": False}
    r = requests.post(f"{BASE_URL}/api/press", json=body, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["voices"] == 1
    assert _max_pins_per_beat(data["partition"]) == 1


def test_render_voices_2_returns_wav_8khz():
    with BABY1.open("rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/render",
            files={"file": ("baby1.mid", f, "audio/midi")},
            data={"tracks": "", "voices": "2", "chords": "true"},
            timeout=180,
        )
    assert r.status_code == 200, r.text[:200]
    assert r.headers["content-type"].startswith("audio/wav")
    assert r.headers.get("X-Sample-Rate") == "8000"
