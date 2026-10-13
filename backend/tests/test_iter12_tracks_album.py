"""Iteration 12 tests: track picker scan, analyze/autofit/press with tracks+skyline, and ALBUM end-to-end."""
import io
import os
import time
import zipfile

import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip("/") + "/api"


BASE = _load_backend_url()
BABY = "/app/tests/assets/user/baby1.mid"
TWINKLE = "/app/tests/assets/sample_twinkle.mid"


@pytest.fixture(scope="module")
def baby_bytes():
    with open(BABY, "rb") as f:
        return f.read()


@pytest.fixture(scope="module")
def twinkle_bytes():
    with open(TWINKLE, "rb") as f:
        return f.read()


# ===== /api/scan =====
class TestScan:
    def test_scan_baby_tracks_structure(self, baby_bytes):
        r = requests.post(f"{BASE}/scan", files={"file": ("baby1.mid", baby_bytes, "audio/midi")})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "events" in data and "tracks" in data and "total" in data and "suggested" in data
        assert len(data["tracks"]) == 13, f"expected 13 tracks got {len(data['tracks'])}"
        assert data["suggested"] == 5, f"suggested should be 5 (Tenor Sax) got {data['suggested']}"
        assert abs(data["total"] - 176.4) < 2.0, f"total ~176.4 got {data['total']}"
        # drum tracks 12 and 13 by index
        drum_tracks = [t for t in data["tracks"] if t["drums"]]
        drum_indices = sorted(t["index"] for t in drum_tracks)
        assert 12 in drum_indices and 13 in drum_indices, f"drum indices {drum_indices}"
        for t in drum_tracks:
            assert t["instrument"] == "Drums"
        # every event triple; no drum tracks present
        assert all(isinstance(e, list) and len(e) == 3 for e in data["events"])
        tracks_in_events = {e[2] for e in data["events"]}
        assert 12 not in tracks_in_events and 13 not in tracks_in_events

    def test_scan_twinkle(self, twinkle_bytes):
        r = requests.post(f"{BASE}/scan", files={"file": ("twinkle.mid", twinkle_bytes, "audio/midi")})
        assert r.status_code == 200
        data = r.json()
        assert len(data["tracks"]) >= 1
        assert all(len(e) == 3 for e in data["events"])
        assert abs(data["total"] - 12) < 3.0


# ===== /api/analyze with tracks/skyline =====
class TestAnalyzeTracks:
    def test_analyze_single_track(self, baby_bytes):
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        r = requests.post(f"{BASE}/analyze", files=files,
                          data={"duration": "25", "start": "18.7", "tracks": "5"})
        assert r.status_code == 200, r.text
        data = r.json()
        nc = data["note_count"]
        assert 25 <= nc <= 45, f"expected 25-45 notes got {nc}"
        assert data["dropped"] == 0
        # 1 pin per beat max
        for row in data["partition"]:
            # row is list[bool]; max per column = 1 is checked across tones
            pass
        beat_counts = [sum(1 for row in data["partition"] if row[b]) for b in range(len(data["partition"][0]))]
        assert max(beat_counts) <= 1, f"max pins per beat {max(beat_counts)}"

    def test_analyze_all_tracks_more_notes(self, baby_bytes):
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        r_one = requests.post(f"{BASE}/analyze", files=files,
                              data={"duration": "25", "start": "18.7", "tracks": "5"})
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        r_all = requests.post(f"{BASE}/analyze", files=files,
                              data={"duration": "25", "start": "18.7", "tracks": ""})
        assert r_all.status_code == 200
        assert r_all.json()["note_count"] > r_one.json()["note_count"] + 20

    def test_analyze_skyline_reduces(self, baby_bytes):
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        r_no = requests.post(f"{BASE}/analyze", files=files,
                             data={"duration": "25", "start": "18.7", "tracks": "4", "skyline": "false"})
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        r_sky = requests.post(f"{BASE}/analyze", files=files,
                              data={"duration": "25", "start": "18.7", "tracks": "4", "skyline": "true"})
        assert r_no.status_code == 200 and r_sky.status_code == 200
        assert r_sky.json()["note_count"] <= r_no.json()["note_count"]


# ===== /api/autofit =====
class TestAutofit:
    def test_autofit_baby_track5(self, baby_bytes):
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        r = requests.post(f"{BASE}/autofit", files=files,
                          data={"start": "18.5", "tracks": "5"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["fit"]["score"] >= 95, f"score {data['fit']['score']}"
        assert data["fit"]["tries"] > 1000
        assert len(data["events"]) > 0


# ===== /api/press with tracks/skyline =====
class TestPressTracks:
    def test_press_tracks_echo(self, baby_bytes):
        # need a tiny partition — grab from analyze
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        a = requests.post(f"{BASE}/analyze", files=files,
                         data={"duration": "15", "start": "18.7", "tracks": "5"}).json()
        body = {
            "partition": a["partition"],
            "title": "TEST_Iter12_PressTracks",
            "thickness": 3.0,
            "tracks": [5],
            "skyline": False,
        }
        r = requests.post(f"{BASE}/press", json=body)
        assert r.status_code == 200, r.text
        resp = r.json()
        assert resp.get("tracks") == [5]
        assert resp.get("skyline") is False
        # verify persistence
        got = requests.get(f"{BASE}/conversions/{resp['id']}").json()
        assert got.get("tracks") == [5]
        assert got.get("skyline") is False


# ===== Album end-to-end =====
def _poll_album(album_id, timeout=240, interval=3):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(f"{BASE}/album/{album_id}")
        assert r.status_code == 200
        last = r.json()
        if last["status"] in ("done", "error"):
            return last
        time.sleep(interval)
    return last


class TestAlbum:
    def test_album_404(self):
        r = requests.get(f"{BASE}/album/does-not-exist")
        assert r.status_code == 404

    def test_album_bad_file(self):
        r = requests.post(f"{BASE}/album",
                          files={"file": ("notmidi.txt", b"hello world", "text/plain")},
                          data={"title": "TEST_Iter12_Bad"})
        assert 400 <= r.status_code < 500

    def test_album_twinkle_single_sided(self, twinkle_bytes):
        files = {"file": ("twinkle.mid", twinkle_bytes, "audio/midi")}
        data = {"title": "TEST_Iter12_TwinkleAlbum", "two_sided": "false",
                "thickness": "3", "duration": "0"}
        r = requests.post(f"{BASE}/album", files=files, data=data)
        assert r.status_code == 200, r.text
        a0 = r.json()
        assert a0["status"] == "running"
        album_id = a0["id"]
        final = _poll_album(album_id, timeout=240)
        assert final["status"] == "done", f"status={final['status']} error={final.get('error')}"
        assert final["total_sides"] == final["total_discs"]
        assert final["total_discs"] >= 1
        for d in final["discs"]:
            assert d["id"] and d["record_no"] and d["sides"]
            assert d["mesh_ok"] is True
            # resolve each disc
            conv = requests.get(f"{BASE}/conversions/{d['id']}").json()
            assert conv.get("album_id") == album_id
            assert conv.get("album_count") == final["total_discs"]

        # ZIP download
        z = requests.get(f"{BASE}/album/{album_id}/zip")
        assert z.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(z.content))
        names = zf.namelist()
        stls = [n for n in names if n.endswith(".stl") and "/" not in n]
        assert len(stls) == final["total_discs"], f"{len(stls)} stls vs {final['total_discs']} discs"
        assert "README.txt" in names
        readme = zf.read("README.txt").decode()
        assert "Play order" in readme

    def test_album_baby_two_sided_starts(self, baby_bytes):
        """Verify two-sided album starts and progresses; do not wait for completion."""
        files = {"file": ("baby1.mid", baby_bytes, "audio/midi")}
        data = {"title": "TEST_Iter12_BabyAlbum", "tracks": "5", "two_sided": "true",
                "thickness": "5", "duration": "0"}
        r = requests.post(f"{BASE}/album", files=files, data=data)
        assert r.status_code == 200, r.text
        a0 = r.json()
        album_id = a0["id"]
        assert a0["status"] == "running"
        # wait up to 90s for 'done' counter to increase from 0 or planning to complete
        deadline = time.time() + 120
        progressed = False
        last = a0
        while time.time() < deadline:
            r2 = requests.get(f"{BASE}/album/{album_id}")
            last = r2.json()
            if last["status"] == "error":
                pytest.fail(f"album errored: {last.get('error')}")
            if last["total_discs"] > 0 or last["done"] > 0:
                progressed = True
                break
            time.sleep(3)
        assert progressed, f"album never progressed: {last}"
