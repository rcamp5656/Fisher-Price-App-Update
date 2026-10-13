"""Folder-backed stand-in for the Motor (MongoDB) client used by server.py.

Each document is one JSON file: <data_dir>/<collection>/<key>.json, so the
offline ZIP build runs without MongoDB. Supports only what server.py uses:
find_one / find().sort().to_list / insert_one / update_one($set,$push,$inc,
upsert) / delete_one, filters by equality, $ne, $regex(+$options i),
and include / exclude projections.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _match(doc: dict, flt: dict) -> bool:
    for k, cond in (flt or {}).items():
        v = doc.get(k)
        if isinstance(cond, dict):
            if "$ne" in cond and v == cond["$ne"]:
                return False
            if "$regex" in cond:
                flags = re.I if "i" in cond.get("$options", "") else 0
                if not isinstance(v, str) or not re.search(cond["$regex"], v, flags):
                    return False
        elif v != cond:
            return False
    return True


def _project(doc: dict, proj: Optional[dict]) -> dict:
    if not proj:
        return dict(doc)
    include = [k for k, v in proj.items() if v and k != "_id"]
    if include:
        out = {k: doc[k] for k in include if k in doc}
        if proj.get("_id", 1) and "_id" in doc:
            out["_id"] = doc["_id"]
        return out
    return {k: v for k, v in doc.items() if proj.get(k, 1)}


class _Cursor:
    def __init__(self, docs: List[dict], proj):
        self._docs, self._proj = docs, proj

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: (d.get(key) is None, d.get(key) if d.get(key) is not None else 0),
                        reverse=direction < 0)
        return self

    async def to_list(self, n: Optional[int] = None):
        docs = self._docs if n is None else self._docs[:n]
        return [_project(d, self._proj) for d in docs]


class _Collection:
    def __init__(self, path: Path):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    def _key(self, doc: dict) -> str:
        raw = str(doc.get("id") or doc.get("_id") or "")
        return re.sub(r"[^A-Za-z0-9_-]", "_", raw) or "doc"

    def _all(self) -> List[dict]:
        out = []
        for p in sorted(self.path.glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    def _write(self, doc: dict):
        (self.path / f"{self._key(doc)}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def _select(self, flt, sort=None) -> List[dict]:
        docs = [d for d in self._all() if _match(d, flt)]
        for key, direction in reversed(sort or []):
            docs.sort(key=lambda d: (d.get(key) is None, d.get(key) if d.get(key) is not None else 0),
                      reverse=direction < 0)
        return docs

    async def find_one(self, flt=None, projection=None, sort=None):
        docs = self._select(flt, sort)
        return _project(docs[0], projection) if docs else None

    def find(self, flt=None, projection=None):
        return _Cursor(self._select(flt), projection)

    async def insert_one(self, doc: dict):
        self._write(dict(doc))

    async def update_one(self, flt, update: Dict[str, Any], upsert: bool = False):
        docs = self._select(flt)
        if docs:
            doc = docs[0]
        elif upsert:
            doc = {k: v for k, v in (flt or {}).items() if not isinstance(v, dict)}
        else:
            return
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        for k, v in update.get("$push", {}).items():
            doc.setdefault(k, []).append(v)
        for k, v in update.get("$inc", {}).items():
            doc[k] = doc.get(k, 0) + v
        self._write(doc)

    async def delete_one(self, flt):
        for d in self._select(flt)[:1]:
            (self.path / f"{self._key(d)}.json").unlink(missing_ok=True)

    async def delete_many(self, flt):
        for d in self._select(flt):
            (self.path / f"{self._key(d)}.json").unlink(missing_ok=True)


class FileDB:
    """db.<collection> -> folder-backed collection."""

    def __init__(self, root: str):
        self.root = Path(root)

    def __getattr__(self, name: str) -> _Collection:
        return _Collection(self.root / name)

    def close(self):
        pass
