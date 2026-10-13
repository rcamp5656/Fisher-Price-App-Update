from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import base64
import logging
import re
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
HIDDEN = {"_id": 0, "stl_b64": 0, "fpr": 0, "fpr_b": 0, "scad": 0}

Partition = List[List[bool]]


class ConversionSummary(BaseModel):
    id: str
    filename: str
    title: str
    title_b: Optional[str] = None
    two_sided: bool = False
    record_no: Optional[int] = None
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
    note_count: int
    notes_used: List[dict]
    duration: float
    start: float
    beats: int


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
    overrides: Optional[dict] = None
    overrides_b: Optional[dict] = None


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


async def _record_no(title: str) -> int:
    """Reuse the number of an earlier pressing with the same title, else next free."""
    same = None
    if title:
        same = await db.conversions.find_one(
            {"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}, "record_no": {"$ne": None}},
            {"_id": 0, "record_no": 1}, sort=[("created_at", -1)])
    if same:
        return same["record_no"]
    top = await db.conversions.find_one({"record_no": {"$ne": None}}, {"_id": 0, "record_no": 1},
                                        sort=[("record_no", -1)])
    return (top["record_no"] + 1) if top else FIRST_RECORD_NO


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


@api_router.post("/scan")
async def scan(file: UploadFile = File(...)):
    """Whole-song overview: every note-on as [seconds, midi] plus total length."""
    raw = await _read_midi(file)
    try:
        events = await run_in_threadpool(fp.parse_midi_events, raw, 3600.0, 0.0)
        total = await run_in_threadpool(fp.midi_length, raw)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read MIDI: {e}")
    return {"events": [[round(t, 3), n] for t, n in events], "total": round(total, 2)}


@api_router.post("/analyze", response_model=Analysis)
async def analyze(
    file: UploadFile = File(...),
    duration: float = Form(25.0),
    start: float = Form(0.0),
    auto_transpose: bool = Form(True),
    manual_offset: int = Form(0),
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


async def _store(doc_id, filename, title, out, meta, title_b=None,
                 partition=None, partition_b=None, record_no=None,
                 overrides=None, overrides_b=None):
    stats = out["stats"]
    doc = {
        "id": doc_id,
        "filename": filename,
        "title": title,
        "title_b": title_b,
        "record_no": record_no,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stl_b64": base64.b64encode(out["stl"]).decode(),
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
    }
    await db.conversions.insert_one(doc)
    for k in ("stl_b64", "fpr", "fpr_b", "scad", "_id"):
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
            req.overrides, req.overrides_b,
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
                        req.overrides, req.overrides_b)


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


@api_router.get("/conversions/{conversion_id}/stl")
async def download_stl(conversion_id: str):
    doc = await _file_doc(conversion_id, "stl_b64")
    return Response(
        content=base64.b64decode(doc["stl_b64"]),
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{_safe_name(doc)}.stl"'},
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
