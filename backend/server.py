from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import base64
import logging
from pathlib import Path
from pydantic import BaseModel
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


class ConversionSummary(BaseModel):
    id: str
    filename: str
    title: str
    created_at: str
    note_count: int
    exact: int
    adjusted: int
    offset: int
    pin_count: int
    duration: float
    thickness: float
    beats: int
    triangles: int
    notes_used: List[dict]


@api_router.get("/")
async def root():
    return {"message": "Fisher-Price Music Box Record Creator API"}


@api_router.post("/convert", response_model=ConversionSummary)
async def convert(
    file: UploadFile = File(...),
    duration: float = Form(25.0),
    thickness: float = Form(3.0),
    auto_transpose: bool = Form(True),
    manual_offset: int = Form(0),
    title: Optional[str] = Form(None),
):
    if not file.filename.lower().endswith((".mid", ".midi")):
        raise HTTPException(status_code=400, detail="Please upload a .mid or .midi file")

    raw = await file.read()
    disc_title = (title or Path(file.filename).stem)[:40]
    try:
        out = fp.generate_stl(
            raw,
            duration=max(1.0, min(60.0, duration)),
            thickness=max(1.5, min(8.0, thickness)),
            auto_transpose=auto_transpose,
            manual_offset=manual_offset,
            title=disc_title,
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

    doc_id = str(uuid.uuid4())
    doc = {
        "id": doc_id,
        "filename": file.filename,
        "title": disc_title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stl_b64": base64.b64encode(out["stl"]).decode(),
        "fpr": out["fpr"],
        "scad": out["scad"],
        **{k: stats[k] for k in (
            "note_count", "exact", "adjusted", "offset", "pin_count",
            "duration", "thickness", "beats", "triangles", "notes_used")},
    }
    await db.conversions.insert_one(doc)
    for k in ("stl_b64", "fpr", "scad", "_id"):
        doc.pop(k, None)
    return doc


@api_router.get("/conversions", response_model=List[ConversionSummary])
async def list_conversions():
    docs = await db.conversions.find(
        {}, {"_id": 0, "stl_b64": 0, "fpr": 0, "scad": 0}
    ).sort("created_at", -1).to_list(50)
    return docs


@api_router.get("/conversions/{conversion_id}", response_model=ConversionSummary)
async def get_conversion(conversion_id: str):
    doc = await db.conversions.find_one(
        {"id": conversion_id}, {"_id": 0, "stl_b64": 0, "fpr": 0, "scad": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


def _safe_name(doc, default="record"):
    return "".join(c for c in doc.get("title", default) if c.isalnum() or c in "-_") or default


@api_router.get("/conversions/{conversion_id}/stl")
async def download_stl(conversion_id: str):
    doc = await db.conversions.find_one({"id": conversion_id}, {"_id": 0, "stl_b64": 1, "title": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=base64.b64decode(doc["stl_b64"]),
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{_safe_name(doc)}.stl"'},
    )


@api_router.get("/conversions/{conversion_id}/scad")
async def download_scad(conversion_id: str):
    doc = await db.conversions.find_one({"id": conversion_id}, {"_id": 0, "scad": 1, "title": 1})
    if not doc or "scad" not in doc:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=doc["scad"],
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{_safe_name(doc)}.scad"'},
    )


@api_router.get("/conversions/{conversion_id}/fpr")
async def download_fpr(conversion_id: str):
    doc = await db.conversions.find_one({"id": conversion_id}, {"_id": 0, "fpr": 1, "title": 1})
    if not doc or "fpr" not in doc:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=doc["fpr"],
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{_safe_name(doc)}.fpr"'},
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
