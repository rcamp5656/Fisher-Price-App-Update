from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import math
import os
import base64
import io
import logging
import re
import zipfile
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone

import fisher_price as fp

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

MAX_UPLOAD = 2 * 1024 * 1024
HIDDEN = {"_id": 0, "stl_b64": 0, "stl_half_a_b64": 0, "stl_half_b_b64": 0, "fpr": 0, "fpr_b": 0, "scad": 0}

Partition = List[List[bool]]


class ConversionSummary(BaseModel):
    id: str
    filename: str
    title: str
    title_b: Optional[str] = None
    two_sided: bool = False
    record_no: Optional[int] = None
    pin_radius: Optional[float] = None
    ded_height: Optional[float] = None
    ded_b: Optional[bool] = None
    toy_fixes: int = 0
    mesh_check: Optional[dict] = None
    roll: Optional[str] = None
    tracks: Optional[List[int]] = None
    skyline: bool = False
    chords: bool = False
    voices: int = 16
    album_id: Optional[str] = None
    album_index: Optional[int] = None
    album_count: Optional[int] = None
    created_at: str
    note_count: int
    exact: int
    adjusted: int
    merged: int = 0
    offset: int
    pin_count: int
    duration: float
    thickness: float
    beats: int
    triangles: int
    notes_used: List[dict]
    partition: Optional[Partition] = None
    partition_b: Optional[Partition] = None
    overrides: Optional[dict] = None
    overrides_b: Optional[dict] = None


class Analysis(BaseModel):
    partition: Partition
    offset: int
    exact: int
    adjusted: int
    merged: int
    staggered: int = 0
    dropped: int = 0
    partition_midi: Optional[Partition] = None
    note_count: int
    notes_used: List[dict]
    duration: float
    start: float
    beats: int
    events: List[List[float]] = []
    fit: Optional[dict] = None


class PressRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=40)
    partition: Partition
    partition_b: Optional[Partition] = None
    title_b: Optional[str] = Field(None, max_length=40)
    thickness: float = 3.0
    engrave: bool = True
    filename: str = "record.mid"
    duration: float = 25.0
    offset: int = 0
    exact: int = 0
    adjusted: int = 0
    merged: int = 0
    record_no: Optional[int] = Field(None, ge=1, le=999)
    pin_radius: float = Field(0.8, ge=0.4, le=1.0)
    ded_height: float = Field(2.4, ge=2.0, le=3.5)
    ded_b: bool = True
    overrides: Optional[dict] = None
    overrides_b: Optional[dict] = None
    roll: str = Field("before", pattern="^(before|after)$")
    tracks: Optional[List[int]] = None
    skyline: bool = False
    chords: bool = False
    voices: int = Field(16, ge=1, le=16)


class CombRequest(BaseModel):
    tracks: List[int] = Field(..., min_length=22, max_length=22)


async def _comb() -> fp.Comb:
    doc = await db.settings.find_one({"_id": "comb"})
    try:
        return fp.Comb(doc["tracks"]) if doc else fp.DEFAULT_COMB
    except Exception:
        return fp.DEFAULT_COMB


def _check_partition(p: Optional[Partition], name: str, comb: fp.Comb):
    if p is None:
        return
    if len(p) != comb.tones or any(len(r) != fp.MAX_BEAT for r in p):
        raise HTTPException(400, f"{name} must be {comb.tones} x {fp.MAX_BEAT}")


@api_router.get("/comb")
async def get_comb():
    return (await _comb()).to_dict()


@api_router.put("/comb")
async def put_comb(req: CombRequest):
    if any(t < 36 or t > 108 for t in req.tracks):
        raise HTTPException(400, "tine pitches must be MIDI 36..108")
    if req.tracks != sorted(req.tracks):
        raise HTTPException(400, "tines must be listed low to high (track 1 = innermost)")
    await db.settings.update_one({"_id": "comb"}, {"$set": {"tracks": req.tracks}}, upsert=True)
    return fp.Comb(req.tracks).to_dict()


@api_router.delete("/comb")
async def reset_comb():
    await db.settings.delete_one({"_id": "comb"})
    return fp.DEFAULT_COMB.to_dict()


@api_router.get("/library")
async def get_library(duration: float = 25.0):
    comb = await _comb()
    return await run_in_threadpool(fp.library, max(5.0, min(60.0, duration)), comb)


@api_router.get("/next-record-no")
async def next_record_no(title: str = ""):
    return {"record_no": await _record_no(title.strip())}


FIRST_RECORD_NO = 6


async def _numbering_start() -> int:
    doc = await db.settings.find_one({"_id": "numbering"})
    return int(doc["start"]) if doc else FIRST_RECORD_NO


class NumberingRequest(BaseModel):
    start: int = Field(..., ge=1, le=999)


@api_router.get("/numbering")
async def get_numbering():
    return {"start": await _numbering_start()}


@api_router.put("/numbering")
async def put_numbering(req: NumberingRequest):
    await db.settings.update_one({"_id": "numbering"}, {"$set": {"start": req.start}}, upsert=True)
    return {"start": req.start}


class DefaultsRequest(BaseModel):
    voices: int = Field(..., ge=1, le=16)
    note: str = Field("", max_length=400)


# "notes at once" default learned from the printed chord test disc
@api_router.get("/defaults")
async def get_defaults():
    doc = await db.settings.find_one({"_id": "defaults"}, {"_id": 0})
    return doc or {"voices": None, "note": "", "tested_at": None}


@api_router.put("/defaults")
async def put_defaults(req: DefaultsRequest):
    voices = req.voices if req.voices in (1, 2, 3, 16) else 1
    doc = {"voices": voices, "note": req.note.strip(), "tested_at": datetime.now(timezone.utc).isoformat()}
    await db.settings.update_one({"_id": "defaults"}, {"$set": doc}, upsert=True)
    return doc


async def _record_no(title: str) -> int:
    """Reuse the number of an earlier pressing with the same title, else the
    next free number at or above the user's numbering start."""
    same = None
    if title:
        same = await db.conversions.find_one(
            {"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}, "record_no": {"$ne": None}},
            {"_id": 0, "record_no": 1}, sort=[("created_at", -1)])
    if same:
        return same["record_no"]
    start = await _numbering_start()
    top = await db.conversions.find_one({"record_no": {"$ne": None}}, {"_id": 0, "record_no": 1},
                                        sort=[("record_no", -1)])
    return max(start, top["record_no"] + 1) if top else start


async def _read_midi(file: UploadFile) -> bytes:
    if not file.filename.lower().endswith((".mid", ".midi")):
        raise HTTPException(status_code=400, detail="Please upload a .mid or .midi file")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="MIDI file too large (max 2 MB)")
    return raw


@api_router.get("/")
async def root():
    return {"message": "Fisher-Price Music Box Record Creator API"}


def _tracks(raw: str) -> Optional[List[int]]:
    vals = [int(x) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]
    return vals or None


@api_router.post("/scan")
async def scan(file: UploadFile = File(...)):
    """Whole-song overview: every pitched note-on as [seconds, midi, track],
    per-track summaries for the track picker and the suggested melody track."""
    raw = await _read_midi(file)
    try:
        info = await run_in_threadpool(fp.scan_tracks, raw)
        total = await run_in_threadpool(fp.midi_length, raw)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read MIDI: {e}")
    info["total"] = max(info["total"], total)
    return info


@api_router.post("/analyze", response_model=Analysis)
async def analyze(
    file: UploadFile = File(...),
    duration: float = Form(25.0),
    start: float = Form(0.0),
    auto_transpose: bool = Form(True),
    manual_offset: int = Form(0),
    roll: str = Form("before"),
    rev_seconds: float = Form(25.0),
    tracks: str = Form(""),
    skyline: bool = Form(False),
    melody_fill: bool = Form(False),
    chords: bool = Form(False),
    voices: int = Form(16),
):
    raw = await _read_midi(file)
    comb = await _comb()
    try:
        rec = await run_in_threadpool(
            fp.analyze, raw,
            duration=max(1.0, min(60.0, duration)),
            start=max(0.0, start),
            auto_transpose=auto_transpose,
            manual_offset=manual_offset,
            comb=comb,
            roll="after" if roll == "after" else "before",
            rev_seconds=max(5.0, min(60.0, rev_seconds)),
            tracks=_tracks(tracks),
            skyline=skyline,
            melody_fill=melody_fill,
            chords=chords or voices < 16,
            voices=max(1, min(16, voices)),
        )
    except Exception as e:
        logging.exception("analysis failed")
        raise HTTPException(status_code=422, detail=f"Could not read MIDI: {e}")
    if rec["note_count"] == 0:
        raise HTTPException(
            status_code=422,
            detail="No playable notes found in that part of the MIDI file.",
        )
    return rec


@api_router.post("/autofit", response_model=Analysis)
async def autofit(
    file: UploadFile = File(...),
    start: float = Form(0.0),
    rev_seconds: float = Form(25.0),
    auto_transpose: bool = Form(True),
    manual_offset: int = Form(0),
    roll: str = Form("before"),
    max_tries: int = Form(12000),
    tracks: str = Form(""),
    skyline: bool = Form(False),
    melody_fill: bool = Form(False),
    chords: bool = Form(False),
    voices: int = Form(16),
):
    """Re-map the MIDI slice up to max_tries ways (tempo ±35 %, start ±0.5 s) and keep the closest match."""
    raw = await _read_midi(file)
    comb = await _comb()
    try:
        rec = await run_in_threadpool(
            fp.auto_fit, raw,
            start=max(0.0, start),
            rev_seconds=max(5.0, min(60.0, rev_seconds)),
            comb=comb,
            roll="after" if roll == "after" else "before",
            auto_transpose=auto_transpose,
            manual_offset=manual_offset,
            max_tries=max(100, min(12000, max_tries)),
            tracks=_tracks(tracks),
            skyline=skyline,
            melody_fill=melody_fill,
            chords=chords or voices < 16,
            voices=max(1, min(16, voices)),
        )
    except Exception as e:
        logging.exception("auto-fit failed")
        raise HTTPException(status_code=422, detail=f"Could not read MIDI: {e}")
    if rec["note_count"] == 0:
        raise HTTPException(status_code=422, detail="No playable notes found in that part of the MIDI file.")
    return fp._finish_analysis(rec, rec["fit"]["duration"], rec["fit"]["start"])


async def _store(doc_id, filename, title, out, meta, title_b=None,
                 partition=None, partition_b=None, record_no=None,
                 overrides=None, overrides_b=None, extra=None):
    stats = out["stats"]
    doc = {
        "id": doc_id,
        "filename": filename,
        "title": title,
        "title_b": title_b,
        "record_no": record_no,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stl_b64": base64.b64encode(out["stl"]).decode(),
        "stl_half_a_b64": base64.b64encode(out["stl_half_a"]).decode() if out.get("stl_half_a") else None,
        "stl_half_b_b64": base64.b64encode(out["stl_half_b"]).decode() if out.get("stl_half_b") else None,
        "fpr": out["fpr"],
        "fpr_b": out.get("fpr_b"),
        "scad": out["scad"],
        "partition": partition,
        "partition_b": partition_b,
        "overrides": overrides,
        "overrides_b": overrides_b,
        **meta,
        **{k: stats[k] for k in ("pin_count", "thickness", "beats", "triangles",
                                 "notes_used", "two_sided")},
        "pin_radius": stats.get("pin_radius"),
        "ded_height": stats.get("ded_height"),
        "ded_b": stats.get("ded_b"),
        "toy_fixes": stats.get("toy_fixes", 0),
        "mesh_check": stats.get("mesh_check"),
        "roll": stats.get("roll", "before"),
        **(extra or {}),
    }
    await db.conversions.insert_one(doc)
    for k in ("stl_b64", "stl_half_a_b64", "stl_half_b_b64", "fpr", "fpr_b", "scad", "_id"):
        doc.pop(k, None)
    return doc


@api_router.post("/press", response_model=ConversionSummary)
async def press(req: PressRequest):
    comb = await _comb()
    _check_partition(req.partition, "partition", comb)
    _check_partition(req.partition_b, "partition_b", comb)
    if not any(any(r) for r in req.partition):
        raise HTTPException(400, "Side A has no notes")
    title_b = (req.title_b or "Side B")[:40] if req.partition_b is not None else None
    min_thick = 4.5 if req.partition_b is not None else 1.5
    record_no = req.record_no or await _record_no(req.title.strip())
    try:
        out = await run_in_threadpool(
            fp.press, req.partition, req.title.strip(),
            max(min_thick, min(8.0, req.thickness)),
            req.partition_b, title_b or "", req.engrave, record_no, comb,
            req.overrides, req.overrides_b, req.pin_radius, req.roll, req.chords or req.voices < 16, req.voices,
            req.ded_height, req.ded_b,
        )
    except Exception as e:
        logging.exception("press failed")
        raise HTTPException(status_code=422, detail=f"Could not build the disc: {e}")
    meta = {
        "note_count": sum(sum(r) for r in req.partition)
        + (sum(sum(r) for r in req.partition_b) if req.partition_b else 0),
        "exact": req.exact, "adjusted": req.adjusted, "merged": req.merged,
        "offset": req.offset, "duration": req.duration,
    }
    return await _store(str(uuid.uuid4()), req.filename, req.title.strip(), out, meta,
                        title_b, req.partition, req.partition_b, record_no,
                        req.overrides, req.overrides_b, {"tracks": req.tracks, "skyline": req.skyline, "chords": req.chords or req.voices < 16, "voices": req.voices})


class AlbumDisc(BaseModel):
    id: str
    record_no: Optional[int] = None
    title: str
    title_b: Optional[str] = None
    two_sided: bool = False
    sides: List[int]
    note_count: int = 0
    mesh_ok: Optional[bool] = None


class Album(BaseModel):
    id: str
    title: str
    status: str
    created_at: str
    duration: float
    start: float
    offset: int = 0
    total_sides: int
    total_discs: int
    done: int = 0
    discs: List[AlbumDisc] = []
    tracks: Optional[List[int]] = None
    skyline: bool = False
    two_sided: bool = True
    fit: Optional[dict] = None
    error: Optional[str] = None


async def _build_album(album_id: str, raw: bytes, o: dict):
    """Background: slice the whole song into 86-beat sides, press every disc."""
    try:
        comb = await _comb()
        tracks, skyline = o["tracks"], o["skyline"]
        plan = await run_in_threadpool(fp.plan_song, raw, comb, tracks, skyline, o["duration"],
                                       o["rev_seconds"], o["roll"], o["auto_transpose"], o["manual_offset"],
                                       o.get("melody_fill", False), o.get("chords", False), o.get("voices", 16))
        sides, duration, start, offset, fit = plan["sides"], plan["duration"], plan["start"], plan["offset"], plan["fit"]
        n_sides = len(sides)
        per_disc = 2 if o["two_sided"] else 1
        n_discs = math.ceil(n_sides / per_disc)
        await db.albums.update_one({"id": album_id}, {"$set": {
            "duration": duration, "start": start, "offset": offset, "fit": fit,
            "total_sides": n_sides, "total_discs": n_discs}})
        base = o["title"][:30]
        for d in range(n_discs):
            a = sides[d * per_disc]
            b = sides[d * per_disc + 1] if per_disc == 2 and d * per_disc + 1 < n_sides else None
            title = f"{base} {d + 1}/{n_discs}"
            title_b = f"{base} {d + 1}/{n_discs} B" if b is not None else None
            if b is None and per_disc == 2:
                b = {"partition": [[False] * fp.MAX_BEAT for _ in range(comb.tones)], "note_count": 0}
                title_b = f"{base} {d + 1}/{n_discs} B (blank)"
            record_no = await _record_no(title)
            out = await run_in_threadpool(
                fp.press, a["partition"], title, o["thickness"],
                b["partition"] if b else None, title_b or "", o["engrave"], record_no, comb,
                None, None, o["pin_radius"], o["roll"], o.get("chords", False), o.get("voices", 16),
                o.get("ded_height", fp.DED_H), o.get("ded_b", True))
            meta = {"note_count": a["note_count"] + (b["note_count"] if b else 0),
                    "exact": a.get("exact", 0), "adjusted": a.get("adjusted", 0), "merged": a.get("merged", 0),
                    "offset": offset, "duration": duration}
            doc = await _store(str(uuid.uuid4()), o["filename"], title, out, meta, title_b,
                               a["partition"], b["partition"] if b else None, record_no, None, None,
                               {"tracks": tracks, "skyline": skyline, "album_id": album_id,
                                "album_index": d + 1, "album_count": n_discs})
            disc = {"id": doc["id"], "record_no": record_no, "title": title, "title_b": title_b,
                    "two_sided": b is not None, "sides": [d * per_disc + 1] + ([d * per_disc + 2] if b else []),
                    "note_count": meta["note_count"], "mesh_ok": (doc.get("mesh_check") or {}).get("ok")}
            await db.albums.update_one({"id": album_id}, {"$push": {"discs": disc}, "$inc": {"done": 1}})
        await db.albums.update_one({"id": album_id}, {"$set": {"status": "done"}})
    except Exception as e:
        logging.exception("album failed")
        await db.albums.update_one({"id": album_id}, {"$set": {"status": "error", "error": str(e)}})


def _song_opts(tracks, skyline, duration, rev_seconds, roll, auto_transpose, manual_offset, melody_fill=False, chords=False, voices=16) -> dict:
    return {
        "tracks": _tracks(tracks), "skyline": bool(skyline), "melody_fill": bool(melody_fill),
        "chords": bool(chords) or voices < 16, "voices": max(1, min(16, voices)),
        "duration": duration if duration <= 0 else max(5.0, min(60.0, duration)),
        "rev_seconds": max(5.0, min(60.0, rev_seconds)), "roll": "after" if roll == "after" else "before",
        "auto_transpose": bool(auto_transpose), "manual_offset": manual_offset,
    }


@api_router.post("/render")
async def render_song(
    file: UploadFile = File(...),
    tracks: str = Form(""),
    skyline: bool = Form(False),
    duration: float = Form(0.0),
    rev_seconds: float = Form(25.0),
    roll: str = Form("before"),
    auto_transpose: bool = Form(True),
    manual_offset: int = Form(0),
    melody_fill: bool = Form(False),
    chords: bool = Form(False),
    voices: int = Form(16),
):
    """Whole song as the toy will play it: 8 kHz mono WAV of Fisher-Price notes, for review."""
    raw = await _read_midi(file)
    comb = await _comb()
    o = _song_opts(tracks, skyline, duration, rev_seconds, roll, auto_transpose, manual_offset, melody_fill, chords, voices)
    try:
        plan = await run_in_threadpool(fp.plan_song, raw, comb, o["tracks"], o["skyline"], o["duration"],
                                       o["rev_seconds"], o["roll"], o["auto_transpose"], o["manual_offset"],
                                       o["melody_fill"], o["chords"], o["voices"])
        wav = await run_in_threadpool(fp.render_song, plan["sides"], o["rev_seconds"], comb)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logging.exception("render failed")
        raise HTTPException(status_code=422, detail=f"Could not render: {e}")
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(file.filename or "song").stem).strip("_") or "song"
    return Response(wav, media_type="audio/wav", headers={
        "Content-Disposition": f'attachment; filename="{name}-fisher-price-6kHz-mono.wav"',
        "X-Sides": str(len(plan["sides"])), "X-Notes": str(plan["note_count"]),
        "X-Duration": f"{plan['duration']:.2f}", "X-Start": f"{plan['start']:.2f}", "X-Offset": str(plan["offset"]),
        "X-Fit-Score": f"{plan['fit']['score']:.1f}" if plan.get("fit") else "",
        "X-Sample-Rate": str(fp.RENDER_RATE),
        "Access-Control-Expose-Headers": "X-Sides, X-Notes, X-Duration, X-Start, X-Offset, X-Fit-Score, X-Sample-Rate, Content-Disposition",
    })


@api_router.post("/album", response_model=Album)
async def make_album(
    file: UploadFile = File(...),
    title: str = Form("Album"),
    tracks: str = Form(""),
    skyline: bool = Form(False),
    duration: float = Form(0.0),
    rev_seconds: float = Form(25.0),
    two_sided: bool = Form(True),
    thickness: float = Form(5.0),
    engrave: bool = Form(True),
    pin_radius: float = Form(0.8),
    roll: str = Form("before"),
    auto_transpose: bool = Form(True),
    manual_offset: int = Form(0),
    melody_fill: bool = Form(False),
    chords: bool = Form(False),
    voices: int = Form(16),
    ded_height: float = Form(2.4),
    ded_b: bool = Form(True),
):
    """Cut the whole song onto as many discs as it takes (duration 0 = auto-fit the tempo)."""
    raw = await _read_midi(file)
    two = bool(two_sided)
    o = {
        "title": (title or Path(file.filename).stem or "Album").strip()[:30] or "Album",
        "filename": file.filename, "tracks": _tracks(tracks), "skyline": bool(skyline), "melody_fill": bool(melody_fill), "chords": bool(chords) or voices < 16, "voices": max(1, min(16, voices)),
        "duration": duration if duration <= 0 else max(5.0, min(60.0, duration)),
        "rev_seconds": max(5.0, min(60.0, rev_seconds)), "two_sided": two,
        "thickness": max(4.5 if two else 1.5, min(8.0, thickness)), "engrave": bool(engrave),
        "pin_radius": max(0.4, min(1.0, pin_radius)), "roll": "after" if roll == "after" else "before",
        "auto_transpose": bool(auto_transpose), "manual_offset": manual_offset,
        "ded_height": max(2.0, min(3.5, ded_height)), "ded_b": bool(ded_b),
    }
    doc = {"id": str(uuid.uuid4()), "title": o["title"], "status": "running",
           "created_at": datetime.now(timezone.utc).isoformat(), "duration": o["duration"] or 0.0,
           "start": 0.0, "offset": 0, "total_sides": 0, "total_discs": 0, "done": 0, "discs": [],
           "tracks": o["tracks"], "skyline": o["skyline"], "two_sided": two, "fit": None, "error": None}
    await db.albums.insert_one(dict(doc))
    asyncio.create_task(_build_album(doc["id"], raw, o))
    return doc


@api_router.get("/album/{album_id}", response_model=Album)
async def get_album(album_id: str):
    doc = await db.albums.find_one({"id": album_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Album not found")
    return doc


@api_router.get("/album/{album_id}/zip")
async def album_zip(album_id: str):
    album = await db.albums.find_one({"id": album_id}, {"_id": 0})
    if not album:
        raise HTTPException(404, "Album not found")
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", album["title"]).strip("_") or "album"
    buf = io.BytesIO()
    lines = [f"{album['title']} — Fisher-Price record album", "=" * 50,
             f"{album['total_discs']} disc(s), {album['total_sides']} side(s) · {album['duration']:.2f} s of song per side · "
             f"transposed {album.get('offset', 0):+d} semitones · tracks {album.get('tracks') or 'all'}"
             f"{' · skyline (top note of chords)' if album.get('skyline') else ''}", "",
             "Play order:"]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for disc in album.get("discs", []):
            doc = await db.conversions.find_one({"id": disc["id"]})
            if not doc:
                continue
            stem = f"{name}-{disc['sides'][0]:02d}" + (f"-{disc['sides'][1]:02d}" if len(disc["sides"]) > 1 else "")
            z.writestr(f"{stem}.stl", base64.b64decode(doc["stl_b64"]))
            if doc.get("stl_half_a_b64"):
                z.writestr(f"halves/{stem}-half-A.stl", base64.b64decode(doc["stl_half_a_b64"]))
                z.writestr(f"halves/{stem}-half-B.stl", base64.b64decode(doc["stl_half_b_b64"]))
            z.writestr(f"scad/{stem}.scad", doc["scad"])
            z.writestr(f"fpr/{stem}.fpr", doc["fpr"])
            if doc.get("fpr_b"):
                z.writestr(f"fpr/{stem}-B.fpr", doc["fpr_b"])
            z.writestr(f"mesh-check/{stem}.txt", _mesh_report(doc))
            z.writestr(f"sleeves/{stem}-label.svg", _label_card(doc, (doc.get("album_index") or 0, doc.get("album_count") or 0) if doc.get("album_index") else None))
            side_txt = f"side {disc['sides'][0]}" + (f" (A) / side {disc['sides'][1]} (B)" if len(disc["sides"]) > 1 else "")
            lines.append(f"  Record #{disc.get('record_no') or '-'}  {stem}.stl  —  {side_txt}  —  {disc['note_count']} pins")
        _, docs = await _album_docs(album_id)
        z.writestr("sleeves/sleeve-sheet.html", _sleeve_sheet(album, docs))
        lines += ["", "sleeves/sleeve-sheet.html — open in a browser and print: numbered 100 x 60 mm sleeve labels (8 per A4 page) so the discs stay in order.",
                  "Each side is one revolution (86 beats). Flip two-sided discs to continue; load the next disc for the next part."]
        z.writestr("README.txt", "\n".join(lines) + "\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}-album.zip"'})


CREDITS = "Fisher-Price Record Maker - Dedicated To My Fiancee Barbara - Copyright 2026 Russ Campbell. All rights reserved."
_SRC_SKIP = {"node_modules", ".git", "build", "__pycache__", ".pytest_cache", "test_reports", ".emergent", "launchers", ".venv", "data"}
_LAUNCHERS = {"start-windows.bat": False, "start-mac.command": True, "BUILD-GUIDE.txt": False}
_SRC_README = """Fisher-Price Record Maker — complete project source
=====================================================
{credits}

ONE-CLICK START (no typing)
  Windows : double-click  start-windows.bat
  macOS   : double-click  start-mac.command
  Linux   : ./start-linux.sh
  Needs Python 3.10+, Node.js LTS and MongoDB Community installed once — see BUILD-GUIDE.txt.

What is inside
  backend/        FastAPI + Python geometry (fisher_price.py: MIDI -> 86-beat disc -> STL/SCAD/FPR, auto-fit, albums, 8 kHz review audio)
                  requirements-local.txt = the short, public-PyPI package list the start scripts install
  frontend/       React 19 app (HTML5 / CSS3 / JS): editor, 3D preview, track picker, album panel, splash screen
  frontend/build/ production build of the web app (static HTML5/CSS3/JS) when present
  standalone/     splash.html — the splash screen as a plain HTML5 / CSS3 / JS page
  tests/, backend/tests/   pytest suites and sample MIDI files
  memory/         product notes (PRD.md)

Run it by hand
  1. MongoDB running locally (or any MONGO_URL)
  2. backend:  cd backend && pip install -r requirements-local.txt
               create backend/.env with  MONGO_URL=mongodb://localhost:27017  and  DB_NAME=fisher_price
               uvicorn server:app --host 0.0.0.0 --port 8001
  3. frontend: cd frontend && npm install --legacy-peer-deps
               create frontend/.env with  REACT_APP_BACKEND_URL=http://localhost:8001
               npm start   (or  npm run build  for the static HTML5/CSS3/JS bundle in frontend/build)

Secrets (.env files) are NOT included on purpose — the start scripts create local ones.
"""


@api_router.get("/source.zip")
async def source_zip():
    """The whole project (source + static build if present) as a ZIP, with credits."""
    root = Path(__file__).resolve().parent.parent
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            rel = p.relative_to(root)
            parts = set(rel.parts)
            if p.is_dir() or parts & _SRC_SKIP or rel.name.startswith(".env") or rel.name == "yarn.lock" and "frontend" not in parts:
                continue
            if rel.parts[0] == "frontend" and "build" in rel.parts and not (root / "frontend" / "build" / "index.html").exists():
                continue
            if p.stat().st_size > 25 * 1024 * 1024:
                continue
            z.write(p, f"fisher-price-record-maker/{rel}")
        build = root / "frontend" / "build"
        if build.exists():
            for p in build.rglob("*"):
                if p.is_file():
                    z.write(p, f"fisher-price-record-maker/frontend/build/{p.relative_to(build)}")
        z.writestr("fisher-price-record-maker/README.txt", _SRC_README.format(credits=CREDITS))
        z.writestr("fisher-price-record-maker/LICENSE.txt", CREDITS + "\n")
        for fname, executable in _LAUNCHERS.items():
            data = (root / "launchers" / fname).read_bytes()
            targets = [fname] + (["start-linux.sh"] if fname == "start-mac.command" else [])
            for t in targets:
                info = zipfile.ZipInfo(f"fisher-price-record-maker/{t}")
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o755 if executable else 0o644) << 16
                z.writestr(info, data)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="fisher-price-record-maker-source.zip"'})


@api_router.post("/testdisc", response_model=ConversionSummary)
async def test_disc(thickness: float = Form(3.0), pin_radius: float = Form(0.8), engrave: bool = Form(True), ded_height: float = Form(2.4)):
    """Chord test disc: the same phrase as single notes, two-note chords and triads."""
    comb = await _comb()
    partition = fp.chord_test_partition(comb)
    title = "CHORD TEST 1-2-3"
    record_no = await _record_no(title)
    out = await run_in_threadpool(fp.press, partition, title, max(1.5, min(8.0, thickness)), None, "",
                                  bool(engrave), record_no, comb, None, None,
                                  max(0.4, min(1.0, pin_radius)), "before", True, 3, max(2.0, min(3.5, ded_height)))
    meta = {"note_count": sum(sum(r) for r in partition), "exact": 0, "adjusted": 0, "merged": 0,
            "offset": 0, "duration": 25.0}
    return await _store(str(uuid.uuid4()), "chord-test.mid", title, out, meta, None, partition, None,
                        record_no, None, None, {"tracks": None, "skyline": False, "chords": True, "voices": 3,
                                                 "test_disc": True})


@api_router.post("/convert", response_model=ConversionSummary)
async def convert(
    file: UploadFile = File(...),
    duration: float = Form(25.0),
    thickness: float = Form(3.0),
    auto_transpose: bool = Form(True),
    manual_offset: int = Form(0),
    title: Optional[str] = Form(None),
):
    raw = await _read_midi(file)
    disc_title = (title or Path(file.filename).stem)[:40]
    record_no = await _record_no(disc_title)
    try:
        out = await run_in_threadpool(
            fp.generate_stl, raw,
            duration=max(1.0, min(60.0, duration)),
            thickness=max(1.5, min(8.0, thickness)),
            auto_transpose=auto_transpose,
            manual_offset=manual_offset,
            title=disc_title,
            record_no=record_no,
        )
    except Exception as e:
        logging.exception("conversion failed")
        raise HTTPException(status_code=422, detail=f"Could not process MIDI: {e}")

    stats = out["stats"]
    if stats["note_count"] == 0:
        raise HTTPException(
            status_code=422,
            detail="No playable notes found in the first seconds of this MIDI file.",
        )
    meta = {k: stats[k] for k in ("note_count", "exact", "adjusted", "merged",
                                  "offset", "duration")}
    return await _store(str(uuid.uuid4()), file.filename, disc_title, out, meta,
                        partition=out["partition"], record_no=record_no)


@api_router.get("/conversions", response_model=List[ConversionSummary])
async def list_conversions():
    return await db.conversions.find({}, HIDDEN).sort("created_at", -1).to_list(50)


@api_router.get("/conversions/{conversion_id}", response_model=ConversionSummary)
async def get_conversion(conversion_id: str):
    doc = await db.conversions.find_one({"id": conversion_id}, HIDDEN)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


def _safe_name(doc, default="record"):
    return "".join(c for c in doc.get("title", default) if c.isalnum() or c in "-_") or default


async def _file_doc(conversion_id: str, field: str):
    doc = await db.conversions.find_one({"id": conversion_id}, {"_id": 0, field: 1, "title": 1})
    if not doc or not doc.get(field):
        raise HTTPException(status_code=404, detail="Not found")
    return doc


_STL_PARTS = {"full": ("stl_b64", ""), "half-a": ("stl_half_a_b64", "-halfA"),
              "half-b": ("stl_half_b_b64", "-halfB")}


@api_router.get("/conversions/{conversion_id}/stl")
async def download_stl(conversion_id: str, part: str = "full"):
    field, suffix = _STL_PARTS.get(part, _STL_PARTS["full"])
    doc = await _file_doc(conversion_id, field)
    return Response(
        content=base64.b64decode(doc[field]),
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{_safe_name(doc)}{suffix}.stl"'},
    )


@api_router.get("/conversions/{conversion_id}/scad")
async def download_scad(conversion_id: str):
    doc = await _file_doc(conversion_id, "scad")
    return Response(
        content=doc["scad"],
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{_safe_name(doc)}.scad"'},
    )


@api_router.get("/conversions/{conversion_id}/fpr")
async def download_fpr(conversion_id: str, side: str = "a"):
    field = "fpr_b" if side.lower() == "b" else "fpr"
    doc = await _file_doc(conversion_id, field)
    suffix = "-sideB" if field == "fpr_b" else ""
    return Response(
        content=doc[field],
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{_safe_name(doc)}{suffix}.fpr"'},
    )


_ALBUM_COLOURS = ["#E63946", "#2A9D8F", "#FFB703", "#457B9D", "#8E44AD", "#F4845F", "#1D3557", "#6A994E", "#D77A61", "#5BC0BE"]


def _label_card(doc, album=None) -> str:
    """Printable label card (SVG, 100 x 60 mm) for the record sleeve.
    album = (index, count) adds the sleeve number so an album stays in order."""
    def esc(t):
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def fit(t, size, width=60.0):
        # squeeze long titles into the text column instead of running under the disc art
        return f' textLength="{width}" lengthAdjust="spacingAndGlyphs"' if len(t or "") * size * 0.6 > width else ""
    notes = " ".join(n["name"] for n in doc.get("notes_used", []))
    side_b = (f'<text x="8" y="40" font-size="4" fill="#457B9D">SIDE B</text>'
              f'<text x="8" y="46" font-size="6" font-weight="700"{fit(doc.get("title_b"), 6)}>{esc(doc.get("title_b"))}</text>'
              if doc.get("two_sided") else "")
    badge = ""
    band = ""
    if album:
        i, n = album
        colour = _ALBUM_COLOURS[(i - 1) % len(_ALBUM_COLOURS)]
        badge = (f'<rect x="60" y="3" width="13" height="8" rx="1.5" fill="{colour}"/>'
                 f'<text x="66.5" y="8.8" font-size="4.5" font-weight="700" fill="#F4F1EA" text-anchor="middle">{i}/{n}</text>'
                 f'<text x="66.5" y="15" font-size="2.6" fill="#457B9D" text-anchor="middle">disc {i} of {n}</text>')
        # colour band down the spine + a dot per disc with this one filled, so a set reads at a glance
        dots = "".join(f'<circle cx="{3.5}" cy="{14 + k * 4.2}" r="1.1" fill="{_ALBUM_COLOURS[k % len(_ALBUM_COLOURS)]}" '
                       f'stroke="#F4F1EA" stroke-width="{0.5 if k + 1 == i else 0}"/>' for k in range(min(n, 10)))
        band = (f'<rect x="0.5" y="0.5" width="6" height="59" rx="3" fill="{colour}"/>'
                f'<rect x="3.5" y="0.5" width="3" height="59" fill="{colour}"/>{dots}'
                f'<text transform="translate(5,57) rotate(-90)" font-size="2.4" font-weight="700" fill="#F4F1EA" text-anchor="start">DISC {i}</text>')
    uid = re.sub(r"[^a-z0-9]", "", str(doc.get("id", "x")))[:8] or "x"
    # dedication bent around the little disc, like the raised ring on the record label
    ded = (f'<defs><path id="ded-{uid}" d="M 73 14 A 11 11 0 1 1 95 14 A 11 11 0 1 1 73 14"/></defs>'
           f'<text font-size="2.1" fill="#1D3557" letter-spacing="0.15"><textPath href="#ded-{uid}" startOffset="25%" text-anchor="middle">'
           f'{esc(fp.DEDICATION)}</textPath></text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60" font-family="DejaVu Sans, Arial, sans-serif" fill="#1D3557">
  <rect x="0.5" y="0.5" width="99" height="59" rx="3" fill="#F4F1EA" stroke="#1D3557" stroke-width="1"/>
  {band}
  <circle cx="84" cy="14" r="9" fill="#B9A9E3" stroke="#1D3557" stroke-width="0.8"/>
  <circle cx="84" cy="14" r="1.5" fill="#F4F1EA" stroke="#1D3557" stroke-width="0.5"/>
  {ded}
  <text x="84" y="29.5" font-size="2.8" text-anchor="middle" fill="#457B9D">RECORD</text>
  <text x="84" y="35" font-size="5" text-anchor="middle" font-weight="700">#{doc.get("record_no") or "-"}</text>
  {badge}
  <text x="8" y="12" font-size="2.6" fill="#457B9D" textLength="54" lengthAdjust="spacingAndGlyphs">FISHER-PRICE MUSIC BOX RECORD PLAYER</text>
  <text x="8" y="22" font-size="4" fill="#457B9D">SIDE A</text>
  <text x="8" y="29" font-size="6" font-weight="700"{fit(doc.get("title"), 6)}>{esc(doc.get("title"))}</text>
  {side_b}
  <text x="8" y="51.5" font-size="2.6" fill="#457B9D" font-style="italic">{esc(fp.DEDICATION)} · © 2026 Russ Campbell</text>
  <text x="8" y="55.5" font-size="2.8" fill="#457B9D">{doc.get("pin_count")} pins · {doc.get("thickness")} mm · {doc.get("duration")}s window · {esc(notes)}</text>
</svg>
'''


_SLEEVES_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title} — sleeve labels</title>
<style>
  @page {{ size: A4 portrait; margin: 10mm; }}
  body {{ margin: 0; font-family: "DejaVu Sans", Arial, sans-serif; color: #1D3557; background: #fff; }}
  .page {{ width: 190mm; display: grid; grid-template-columns: 1fr 1fr; gap: 6mm 8mm; padding: 4mm 0; page-break-after: always; }}
  .page:last-child {{ page-break-after: auto; }}
  svg {{ width: 90mm; height: 54mm; display: block; }}
  h1 {{ font-size: 14px; margin: 0 0 2mm; }}
  p.note {{ font-size: 10px; margin: 0 0 3mm; color: #457B9D; }}
  .bar {{ display: flex; gap: 8px; align-items: center; margin-bottom: 4mm; }}
  button {{ font: 700 12px "DejaVu Sans", Arial; padding: 6px 12px; border: 2px solid #1D3557; background: #E9C46A; border-radius: 6px; cursor: pointer; }}
  @media print {{ .bar {{ display: none; }} }}
</style></head>
<body>
<div class="bar"><h1>{title} — {count} numbered sleeve labels</h1><button onclick="window.print()">PRINT</button></div>
<p class="note">Cut along the card borders (100 × 60 mm). Play order: {order}. {dedication} · © 2026 Russ Campbell</p>
{pages}
</body></html>
"""


def _sleeve_sheet(album, docs) -> str:
    cards = [_label_card(d, (i + 1, len(docs))) for i, d in enumerate(docs)]
    pages = []
    for p in range(0, len(cards), 8):
        pages.append('<div class="page">' + "\n".join(cards[p:p + 8]) + "</div>")
    order = " → ".join(f"#{d.get('record_no') or '-'}" for d in docs) or "-"
    return _SLEEVES_HTML.format(title=album["title"].replace("<", "&lt;"), count=len(docs), order=order,
                                dedication=fp.DEDICATION, pages="\n".join(pages))


async def _album_docs(album_id: str):
    album = await db.albums.find_one({"id": album_id}, {"_id": 0})
    if not album:
        raise HTTPException(404, "Album not found")
    docs = []
    for disc in album.get("discs", []):
        doc = await db.conversions.find_one({"id": disc["id"]}, {"_id": 0, "stl_b64": 0, "stl_half_a_b64": 0, "stl_half_b_b64": 0, "scad": 0, "fpr": 0, "fpr_b": 0})
        if doc:
            docs.append(doc)
    return album, docs


@api_router.get("/album/{album_id}/sleeves")
async def album_sleeves(album_id: str):
    """One printable sheet (HTML, A4 pages of 8 cards) of numbered sleeve labels for the whole album."""
    album, docs = await _album_docs(album_id)
    return Response(_sleeve_sheet(album, docs), media_type="text/html; charset=utf-8")


@api_router.get("/conversions/{conversion_id}/label.svg")
async def download_label(conversion_id: str):
    doc = await db.conversions.find_one({"id": conversion_id}, {"_id": 0, "stl_b64": 0, "stl_half_a_b64": 0, "stl_half_b_b64": 0, "scad": 0, "fpr": 0, "fpr_b": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    album = (doc["album_index"], doc["album_count"]) if doc.get("album_index") and doc.get("album_count") else None
    return Response(_label_card(doc, album), media_type="image/svg+xml",
                    headers={"Content-Disposition": f'inline; filename="{_safe_name(doc)}-label.svg"'})


_PACK_README = """Fisher-Price Music Box Record Maker - print pack
=================================================
Record #{no}: {title}{b}

Files
  {name}.stl        full disc at 100% scale (diameter 121 mm) - single-sided: print flat, pins up
  {name}-halfA.stl  (two-sided only) RECOMMENDED: print each half flat, pins up, no supports,
  {name}-halfB.stl  then glue the flat backs together using the spindle + 4 drive holes to align
  {name}.scad       OpenSCAD source (edit pins / labels by hand if you like)
  {name}.fpr        music-box tune-tracker file for side A{fprb}
  {name}-label.svg  100 x 60 mm label card for the sleeve (open in a browser and print)
  mesh-check.txt    pre-flight report: watertight / winding / hole + triangle repairs done before export

Print settings
  0.10-0.12 mm layers, 0.4 mm nozzle (0.25 mm for crisper pins), PLA or PETG
  3-4 perimeters, 40%+ infill, no supports, outer walls <= 40 mm/s, seam at rear
  Two-sided discs are 5 mm thick; single-sided 3 mm
"""


def _mesh_report(doc) -> str:
    c = doc.get("mesh_check") or {}
    if not c:
        return "Mesh check: not available for this record (pressed before the pre-flight check existed).\n"
    yn = lambda v: "yes" if v else "NO"
    lines = [
        CREDITS,
        "Fisher-Price Music Box Record Maker - mesh pre-flight report",
        "=============================================================",
        f"Record #{doc.get('record_no') or '-'}: {doc.get('title')}" + (f" / {doc.get('title_b')}" if doc.get("two_sided") else ""),
        f"Pressed: {doc.get('created_at')}",
        "",
        f"Verdict: {'PRINT READY' if c.get('ok') else 'NEEDS ATTENTION'}",
        f"  watertight (no holes) ............ {yn(c.get('watertight'))}",
        f"  consistent triangle winding ....... {yn(c.get('winding_consistent'))}",
        f"  open edges after repair ........... {c.get('open_edges_after')}",
        f"  solid bodies ...................... {c.get('bodies')}",
        f"  triangles ......................... {c.get('faces')}",
        f"  volume ............................ {c.get('volume_mm3')} mm3",
    ]
    if c.get("halves_ok") is not None:
        lines.append(f"  half discs A + B print ready ...... {yn(c.get('halves_ok'))}")
    lines += [
        "",
        "Repairs performed before the STL was written",
        f"  hole triangles filled ............. {c.get('holes_filled', 0)}",
        f"  mismatched triangles re-wound ..... {c.get('flipped_faces_fixed', 0)}",
        f"  duplicate triangles removed ....... {c.get('duplicate_faces_removed', 0)}",
        f"  zero-area triangles removed ....... {c.get('degenerate_faces_removed', 0)}",
        f"  open edges before repair .......... {c.get('open_edges_before', 0)}",
        "",
        "Method: trimesh merge_vertices -> unique/nondegenerate faces -> fix_winding -> fill_holes -> fix_normals,",
        "then watertight / winding / boundary-edge verification (scipy graph engine).",
    ]
    return "\n".join(lines) + "\n"


@api_router.get("/conversions/{conversion_id}/pack")
async def download_pack(conversion_id: str):
    doc = await db.conversions.find_one({"id": conversion_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    name = _safe_name(doc)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{name}.stl", base64.b64decode(doc["stl_b64"]))
        if doc.get("stl_half_a_b64"):
            z.writestr(f"{name}-halfA.stl", base64.b64decode(doc["stl_half_a_b64"]))
            z.writestr(f"{name}-halfB.stl", base64.b64decode(doc["stl_half_b_b64"]))
        z.writestr(f"{name}.scad", doc["scad"])
        z.writestr(f"{name}.fpr", doc["fpr"])
        if doc.get("fpr_b"):
            z.writestr(f"{name}-sideB.fpr", doc["fpr_b"])
        z.writestr(f"{name}-label.svg", _label_card(doc, (doc["album_index"], doc["album_count"]) if doc.get("album_index") and doc.get("album_count") else None))
        z.writestr("mesh-check.txt", _mesh_report(doc))
        z.writestr("README.txt", _PACK_README.format(
            no=doc.get("record_no") or "-", title=doc.get("title"), name=name,
            b=f" / {doc.get('title_b')}" if doc.get("two_sided") else "",
            fprb=f"\n  {name}-sideB.fpr  tune-tracker file for side B" if doc.get("fpr_b") else ""))
    return Response(
        content=buf.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}-print-pack.zip"'},
    )


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
