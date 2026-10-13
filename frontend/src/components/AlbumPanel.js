import React, { useEffect, useState } from "react";
import axios from "axios";
import { Album, Loader2, Download, Disc3, AlertTriangle, CheckCircle2 } from "lucide-react";
import { BTN_BASE, BTN_DISABLED } from "../lib/fp";

export default function AlbumPanel({ api, file, settings, tracks, skyline, melodyFill = false, revSeconds, disabled, onOpenDisc }) {
  const [album, setAlbum] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!album || album.status !== "running") return undefined;
    const t = setInterval(async () => {
      try {
        const { data } = await axios.get(`${api}/album/${album.id}`);
        setAlbum(data);
      } catch (e) { /* keep polling */ }
    }, 3000);
    return () => clearInterval(t);
  }, [album, api]);

  const start = async () => {
    if (!file) return;
    setBusy(true); setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("title", settings.title || file.name.replace(/\.[^.]+$/, ""));
    form.append("tracks", (tracks || []).join(","));
    form.append("skyline", String(!!skyline));
    form.append("melody_fill", String(!!melodyFill && !!(tracks && tracks.length)));
    form.append("chords", String(settings.voices > 1));
    form.append("voices", String(settings.voices || 1));
    form.append("duration", String(settings.autoFit ? 0 : settings.duration));
    form.append("rev_seconds", String(revSeconds));
    form.append("two_sided", String(!!settings.twoSided));
    form.append("thickness", String(settings.thickness));
    form.append("engrave", String(!!settings.engrave));
    form.append("pin_radius", String(settings.pinRadius));
    form.append("roll", settings.roll);
    form.append("auto_transpose", String(!!settings.autoTranspose));
    form.append("manual_offset", String(settings.manualOffset));
    try {
      const { data } = await axios.post(`${api}/album`, form);
      setAlbum(data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not start the album.");
    } finally { setBusy(false); }
  };

  const running = album && album.status === "running";
  const pct = album && album.total_discs ? Math.round((album.done / album.total_discs) * 100) : 0;

  return (
    <div data-testid="album-panel" className="flex flex-col gap-3">
      <button
        type="button" data-testid="album-button" disabled={disabled || busy || running || !file} onClick={start}
        className={`${BTN_BASE} text-base py-3 ${disabled || busy || running || !file ? BTN_DISABLED : "bg-[#1D3557] text-white"}`}
        title="Cut the whole song onto as many discs as it takes"
      >
        {busy || running ? <Loader2 className="h-5 w-5 animate-spin" /> : <Album className="h-5 w-5" />}
        {running ? `CUTTING DISC ${Math.min(album.done + 1, album.total_discs || 1)} OF ${album.total_discs || "…"}` : "CUT THE WHOLE SONG (ALBUM)"}
      </button>
      <p className="font-mono text-[10px] text-[#457B9D] -mt-1">
        Splits the full song into {settings.twoSided ? "two-sided" : "single-sided"} discs — one revolution per side — with one key and one tempo across the set{settings.autoFit ? " (tempo auto-fitted)" : ""}.
      </p>
      {error && <div data-testid="album-error" className="font-mono text-xs bg-[#E63946] text-white rounded-md p-2 flex items-center gap-2"><AlertTriangle className="h-4 w-4" /> {error}</div>}
      {album && (
        <div data-testid="album-status" className="border-2 border-[#1D3557] rounded-lg bg-[#F4F1EA] p-3 flex flex-col gap-2 font-mono text-xs">
          <div className="flex items-center justify-between">
            <span className="font-sans font-black text-sm">{album.title}</span>
            <span data-testid="album-progress-text">
              {album.status === "error" ? "FAILED" : album.status === "done" ? `${album.total_discs} disc(s) · ${album.total_sides} side(s)` : album.total_discs ? `${album.done}/${album.total_discs} discs` : "measuring the song…"}
            </span>
          </div>
          <div className="h-3 border-2 border-[#1D3557] rounded-full bg-white overflow-hidden">
            <div data-testid="album-progress-bar" className={`h-full transition-[width] duration-500 ${album.status === "error" ? "bg-[#E63946]" : "bg-[#2A9D8F]"}`} style={{ width: `${album.status === "done" ? 100 : pct}%` }} />
          </div>
          {album.status === "error" && <div className="text-[#E63946]">{album.error}</div>}
          {album.duration > 0 && (
            <div className="text-[#457B9D]">
              {album.duration.toFixed(1)} s of song per side · from {album.start.toFixed(1)} s · transposed {album.offset > 0 ? "+" : ""}{album.offset} st
              {album.fit ? ` · ${Math.round(album.fit.score)}% match after ${album.fit.tries.toLocaleString()} tries` : ""}
            </div>
          )}
          <ol className="flex flex-col gap-1">
            {album.discs.map((d) => (
              <li key={d.id} data-testid={`album-disc-${d.sides[0]}`} className="flex items-center gap-2 bg-white border border-[#1D3557]/30 rounded px-2 py-1">
                <Disc3 className="h-3.5 w-3.5 shrink-0" />
                <span className="font-bold">#{d.record_no}</span>
                <span className="truncate">{d.title}</span>
                <span className="text-[#457B9D] ml-auto whitespace-nowrap">side{d.sides.length > 1 ? "s" : ""} {d.sides.join(" + ")} · {d.note_count} pins</span>
                {d.mesh_ok === false ? <AlertTriangle className="h-3.5 w-3.5 text-[#E63946]" /> : <CheckCircle2 className="h-3.5 w-3.5 text-[#2A9D8F]" />}
                <button type="button" data-testid={`album-open-${d.sides[0]}`} onClick={() => onOpenDisc(d.id)} className="underline">open</button>
                <a data-testid={`album-stl-${d.sides[0]}`} href={`${api}/conversions/${d.id}/stl`} className="underline">.stl</a>
              </li>
            ))}
          </ol>
          {album.status === "done" && (
            <a
              data-testid="album-zip-link" href={`${api}/album/${album.id}/zip`}
              className={`${BTN_BASE} text-sm py-2 bg-[#2A9D8F] text-white`}
            >
              <Download className="h-4 w-4" /> DOWNLOAD ALBUM ZIP ({album.total_discs} STLs)
            </a>
          )}
        </div>
      )}
    </div>
  );
}
