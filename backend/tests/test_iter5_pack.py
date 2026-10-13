"""Iteration 5: Print pack endpoint tests."""
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
MIDI_PATH = "/app/tests/assets/sample_twinkle.mid"


def _analyze_and_press(two_sided: bool, title: str):
    with open(MIDI_PATH, "rb") as f:
        r = requests.post(f"{BASE_URL}/api/analyze",
                          files={"file": ("sample_twinkle.mid", f.read(), "audio/midi")},
                          data={"duration": 25.0, "start": 0.0, "auto_transpose": "true", "manual_offset": 0},
                          timeout=30)
    assert r.status_code == 200, r.text
    ana = r.json()
    payload = {
        "title": title,
        "partition": ana["partition"],
        "thickness": 5.0 if two_sided else 3.0,
        "filename": "sample_twinkle.mid",
        "duration": 25.0,
        "offset": ana["offset"],
        "exact": ana["exact"],
        "adjusted": ana["adjusted"],
        "merged": ana["merged"],
    }
    if two_sided:
        payload["partition_b"] = ana["partition"]
        payload["title_b"] = title + " B"
    r = requests.post(f"{BASE_URL}/api/press", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


class TestPackEndpoint:
    def test_pack_single_sided(self):
        rec = _analyze_and_press(False, "TEST_PackSingle")
        r = requests.get(f"{BASE_URL}/api/conversions/{rec['id']}/pack", timeout=30)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        cd = r.headers.get("content-disposition", "")
        assert "-print-pack.zip" in cd
        assert "TEST_PackSingle" in cd

        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        assert "TEST_PackSingle.stl" in names
        assert "TEST_PackSingle.scad" in names
        assert "TEST_PackSingle.fpr" in names
        assert "TEST_PackSingle-label.svg" in names
        assert "README.txt" in names
        assert "TEST_PackSingle-sideB.fpr" not in names

        svg = z.read("TEST_PackSingle-label.svg").decode()
        assert "TEST_PackSingle" in svg
        assert "RECORD #" in svg

        readme = z.read("README.txt").decode()
        assert str(rec["record_no"]) in readme

    def test_pack_two_sided(self):
        rec = _analyze_and_press(True, "TEST_PackTwo")
        r = requests.get(f"{BASE_URL}/api/conversions/{rec['id']}/pack", timeout=30)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        assert "TEST_PackTwo.stl" in names
        assert "TEST_PackTwo.scad" in names
        assert "TEST_PackTwo.fpr" in names
        assert "TEST_PackTwo-sideB.fpr" in names
        assert "TEST_PackTwo-label.svg" in names
        assert "README.txt" in names

        svg = z.read("TEST_PackTwo-label.svg").decode()
        assert "TEST_PackTwo" in svg
        assert "RECORD #" in svg
        readme = z.read("README.txt").decode()
        assert str(rec["record_no"]) in readme

    def test_pack_unknown_id(self):
        r = requests.get(f"{BASE_URL}/api/conversions/does-not-exist-xyz/pack", timeout=10)
        assert r.status_code == 404
