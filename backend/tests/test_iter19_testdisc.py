"""Iter19: chord test disc endpoint /api/testdisc."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def test_disc_response():
    r = requests.post(f"{API}/testdisc", data={"thickness": 3}, timeout=180)
    assert r.status_code == 200, r.text
    return r.json()


class TestChordTestDisc:
    def test_200_and_title(self, test_disc_response):
        assert test_disc_response["title"] == "CHORD TEST 1-2-3"

    def test_voices_and_chords(self, test_disc_response):
        assert test_disc_response["voices"] == 3
        assert test_disc_response["chords"] is True

    def test_mesh_check_ok(self, test_disc_response):
        assert test_disc_response["mesh_check"]["ok"] is True

    def test_pin_count_36(self, test_disc_response):
        # 6 single + 6*2 + 6*3 = 36
        assert test_disc_response["pin_count"] == 36

    def test_record_no_assigned(self, test_disc_response):
        assert isinstance(test_disc_response.get("record_no"), int)
        assert test_disc_response["record_no"] >= 1

    def test_get_by_id_returns_it(self, test_disc_response):
        rid = test_disc_response["id"]
        r = requests.get(f"{API}/conversions/{rid}", timeout=30)
        assert r.status_code == 200
        got = r.json()
        assert got["title"] == "CHORD TEST 1-2-3"
        assert got["voices"] == 3

    def test_partition_column_counts(self, test_disc_response):
        rid = test_disc_response["id"]
        r = requests.get(f"{API}/conversions/{rid}", timeout=30)
        data = r.json()
        partition = data.get("partition")
        assert partition and isinstance(partition, list)
        # column counts
        beats = len(partition[0])
        col = [sum(bool(row[b]) for row in partition) for b in range(beats)]
        for b in [2, 4, 6, 8, 10, 12]:
            assert col[b] == 1, f"beat {b}: expected 1, got {col[b]}"
        for b in [30, 32, 34, 36, 38, 40]:
            assert col[b] == 2, f"beat {b}: expected 2, got {col[b]}"
        for b in [58, 60, 62, 64, 66, 68]:
            assert col[b] == 3, f"beat {b}: expected 3, got {col[b]}"
        used_beats = set([2,4,6,8,10,12,30,32,34,36,38,40,58,60,62,64,66,68])
        for b in range(beats):
            if b not in used_beats:
                assert col[b] == 0, f"beat {b} should be 0 but is {col[b]}"

    def test_thickness_clamp_no_500(self):
        r = requests.post(f"{API}/testdisc", data={"thickness": 9}, timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["title"] == "CHORD TEST 1-2-3"
