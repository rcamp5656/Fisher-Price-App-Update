"""Iteration 9: /api/press enforces factory stagger server-side; toy_fixes counts fixes;
echoed partition is the fixed one; pin_radius default 0.8."""
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

# tones 0-6, 13-15 are single-tine on factory comb (indexes into the 16 unique pitches)
SINGLE_TINE = set(list(range(0, 7)) + list(range(13, 16)))


def _empty_partition(tones=16, beats=86):
    return [[False] * beats for _ in range(tones)]


def _press(title, partition, **extra):
    body = {"title": title, "partition": partition}
    body.update(extra)
    return requests.post(f"{API}/press", json=body, timeout=180)


def _assert_fixed(partition):
    beats = len(partition[0])
    # at most one pin per beat within each groove (two walls)
    TINES = [[1], [2], [3], [4], [5], [6], [7], [8, 9], [10, 11], [12, 13], [14, 15], [16, 17], [18, 19], [20], [21], [22]]
    grooves = {}
    for tone, tr in enumerate(TINES):
        for t in tr:
            grooves.setdefault((t - 1) // 2, set()).add(tone)
    for b in range(beats):
        for g, tones in grooves.items():
            col = sum(1 for t in tones if partition[t][b])
            assert col <= 1, f"beat {b} groove {g} has {col} notes"
    # no consecutive beats on single-tine rows
    for t in SINGLE_TINE:
        row = partition[t]
        for b in range(beats - 1):
            assert not (row[b] and row[b + 1]), f"single tine {t} has consecutive at {b}"


def test_press_chord_and_single_tine_repeat_fixed():
    """Partition with a chord (2 tones on beat 10) and single-tine repeat
    (tone 4 beats 30 and 31). Expect toy_fixes >= 2 and partition fixed."""
    part = _empty_partition()
    part[4][10] = True
    part[5][10] = True  # same-groove clash: G5 (track 5) and A5 (track 6) share groove 3
    part[4][30] = True
    part[4][31] = True  # single-tine consecutive
    r = _press("TEST_Iter9_StagChord", part)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec.get("toy_fixes", 0) >= 2, f"toy_fixes should be >=2, got {rec.get('toy_fixes')}"
    assert rec["partition"] is not None
    _assert_fixed(rec["partition"])
    # GET conversion echoes same fixed partition and toy_fixes
    rec2 = requests.get(f"{API}/conversions/{rec['id']}", timeout=20).json()
    assert rec2["toy_fixes"] == rec["toy_fixes"]
    assert rec2["partition"] == rec["partition"]


def test_press_default_pin_radius_is_0_8():
    """pin_radius default should be 0.8 (iter9 fix)."""
    part = _empty_partition()
    # 10 well-spaced notes on different tones
    for i, b in enumerate(range(0, 80, 8)):
        part[i % 16][b] = True
    r = _press("TEST_Iter9_PinDefault", part)
    assert r.status_code == 200, r.text
    assert r.json().get("pin_radius") == 0.8


def test_press_echo_fixed_partition_matches_rules():
    """Even a well-formed partition should round-trip (toy_fixes may be 0)."""
    part = _empty_partition()
    for b in range(0, 86, 3):
        part[(b // 3) % 16][b] = True
    r = _press("TEST_Iter9_Clean", part)
    assert r.status_code == 200, r.text
    rec = r.json()
    _assert_fixed(rec["partition"])


@pytest.fixture(scope="module", autouse=True)
def restore_numbering_at_end():
    yield
    requests.put(f"{API}/numbering", json={"start": 6}, timeout=10)
