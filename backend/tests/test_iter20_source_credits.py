"""Iter20: /api/source.zip + credits-header in generated SCAD and pack mesh-check.txt"""
import io
import os
import re
import time
import zipfile
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
SAMPLE_MID = Path("/app/tests/assets/sample_twinkle.mid")


# ---------- /api/source.zip ----------
class TestSourceZip:
    def test_source_zip_headers_and_content(self):
        r = requests.get(f"{API}/source.zip", timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/zip")
        cd = r.headers.get("content-disposition", "")
        assert "fisher-price-record-maker-source.zip" in cd

        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()

        required = [
            "fisher-price-record-maker/backend/server.py",
            "fisher-price-record-maker/backend/fisher_price.py",
            "fisher-price-record-maker/frontend/src/App.js",
            "fisher-price-record-maker/frontend/src/components/Splash.js",
            "fisher-price-record-maker/frontend/build/index.html",
            "fisher-price-record-maker/standalone/splash.html",
            "fisher-price-record-maker/README.txt",
            "fisher-price-record-maker/LICENSE.txt",
        ]
        for req in required:
            assert req in names, f"Missing in zip: {req}"

        # No forbidden paths
        for n in names:
            assert ".env" not in n, f"Forbidden .env in zip: {n}"
            assert "node_modules" not in n, f"Forbidden node_modules in zip: {n}"
            assert "/.git/" not in n and not n.endswith("/.git"), f"Forbidden .git in zip: {n}"

        # README/LICENSE contain credits
        readme = z.read("fisher-price-record-maker/README.txt").decode("utf-8", "ignore")
        license_ = z.read("fisher-price-record-maker/LICENSE.txt").decode("utf-8", "ignore")
        assert "Russ Campbell" in readme
        assert "Russ Campbell" in license_

        # main.*.js built bundle contains "Russ Campbell"
        main_js = [n for n in names if re.search(r"frontend/build/static/js/main\..*\.js$", n)]
        assert main_js, f"No main.*.js in build: {[n for n in names if 'build/static/js' in n]}"
        content = z.read(main_js[0]).decode("utf-8", "ignore")
        assert "Russ Campbell" in content


# ---------- press -> SCAD + pack mesh-check credits ----------
@pytest.fixture(scope="module")
def pressed_id():
    # Use /api/testdisc to get a pressed conversion id without constructing a Partition
    r = requests.post(f"{API}/testdisc", data={"thickness": "3", "pin_radius": "0.8", "engrave": "true"}, timeout=120)
    assert r.status_code == 200, r.text[:400]
    cid = r.json()["id"]
    time.sleep(0.3)
    return cid


class TestCreditsInArtifacts:
    def test_scad_first_line_has_credits(self, pressed_id):
        r = requests.get(f"{API}/conversions/{pressed_id}/scad", timeout=60)
        assert r.status_code == 200
        first = r.text.splitlines()[0]
        assert "Copyright 2026 Russ Campbell" in first, f"SCAD first line: {first!r}"

    def test_pack_mesh_check_first_line_has_credits(self, pressed_id):
        r = requests.get(f"{API}/conversions/{pressed_id}/pack", timeout=120)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/zip")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        mc_names = [n for n in z.namelist() if n.endswith("mesh-check.txt")]
        assert mc_names, f"mesh-check.txt not in pack: {z.namelist()}"
        text = z.read(mc_names[0]).decode("utf-8", "ignore")
        first = text.splitlines()[0]
        assert "Russ Campbell" in first, f"mesh-check first line: {first!r}"
