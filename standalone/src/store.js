// ===== store.js — IndexedDB records/albums/settings + minimal ZIP writer (backup, print pack) =====
const STORE = (() => {
  const DB = "fisher-price-record-maker", VER = 1; let dbp = null;
  function open() { if (dbp) return dbp; dbp = new Promise((res, rej) => { const r = indexedDB.open(DB, VER); r.onupgradeneeded = () => { const d = r.result; for (const s of ["records", "albums", "settings"]) if (!d.objectStoreNames.contains(s)) d.createObjectStore(s, { keyPath: "id" }); }; r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }); return dbp; }
  const tx = async (store, mode, fn) => { const d = await open(); return new Promise((res, rej) => { const t = d.transaction(store, mode), s = t.objectStore(store); const out = fn(s); t.oncomplete = () => res(out && out.result !== undefined ? out.result : out); t.onerror = () => rej(t.error); }); };
  const put = (store, doc) => tx(store, "readwrite", (s) => s.put(doc));
  const get = (store, id) => tx(store, "readonly", (s) => s.get(id));
  const del = (store, id) => tx(store, "readwrite", (s) => s.delete(id));
  const all = (store) => tx(store, "readonly", (s) => s.getAll());
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => { const r = (Math.random() * 16) | 0; return (c === "x" ? r : (r & 3) | 8).toString(16); }));
  const settings = { async get(k, dflt) { const d = await get("settings", k); return d ? d.value : dflt; }, set: (k, value) => put("settings", { id: k, value }) };
  // list without heavy blobs
  async function records() { const rs = await all("records"); return rs.map(({ stl, scad, fpr, ...r }) => r).sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || "")); }
  async function nextRecordNo(title) { const rs = await records(); const start = await settings.get("numbering", 6); if (title) { const same = rs.find((r) => (r.title || "").trim().toLowerCase() === title.trim().toLowerCase()); if (same && same.recordNo) return same.recordNo; } const used = new Set(rs.map((r) => r.recordNo)); let n = start; while (used.has(n) || n <= 5) n++; return n; }

  // ---- tiny ZIP writer (STORE method, CRC32) ----
  const CRC = (() => { const t = new Uint32Array(256); for (let i = 0; i < 256; i++) { let c = i; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[i] = c >>> 0; } return t; })();
  const crc32 = (u8) => { let c = 0xffffffff; for (let i = 0; i < u8.length; i++) c = CRC[(c ^ u8[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  async function zip(files) {
    const enc = new TextEncoder(), parts = [], central = []; let offset = 0;
    const now = new Date(), dosTime = ((now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1)) & 0xffff, dosDate = (((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate()) & 0xffff;
    for (const [name, data] of files) {
      const body = data instanceof Blob ? new Uint8Array(await data.arrayBuffer()) : typeof data === "string" ? enc.encode(data) : new Uint8Array(data);
      const n = enc.encode(name), crc = crc32(body), lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true); lh.setUint16(10, dosTime, true); lh.setUint16(12, dosDate, true); lh.setUint32(14, crc, true); lh.setUint32(18, body.length, true); lh.setUint32(22, body.length, true); lh.setUint16(26, n.length, true); lh.setUint16(28, 0, true);
      parts.push(lh.buffer, n, body);
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true); ch.setUint16(12, dosTime, true); ch.setUint16(14, dosDate, true); ch.setUint32(16, crc, true); ch.setUint32(20, body.length, true); ch.setUint32(24, body.length, true); ch.setUint16(28, n.length, true); ch.setUint32(42, offset, true);
      central.push(ch.buffer, n); offset += 30 + n.length + body.length;
    }
    const cdSize = central.reduce((s, b) => s + (b.byteLength || b.length), 0), end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true); end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
    return new Blob([...parts, ...central, end.buffer], { type: "application/zip" });
  }
  function download(blob, name) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000); }
  const safeName = (t) => (t || "record").replace(/[^A-Za-z0-9 _-]+/g, "").trim().replace(/\s+/g, "-").slice(0, 40) || "record";
  return { put, get, del, all, uuid, settings, records, nextRecordNo, zip, download, safeName };
})();
