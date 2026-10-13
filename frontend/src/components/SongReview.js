import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Headphones, Loader2, Download, AlertTriangle } from "lucide-react";
import { BTN_BASE, BTN_DISABLED } from "../lib/fp";

// Whole song rendered server-side as the toy plays it: 6 kHz mono, Fisher-Price notes only
export default function SongReview({ api, file, settings, tracks, skyline, melodyFill = false, revSeconds, disabled }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [out, setOut] = useState(null);
  const urlRef = useRef(null);

  useEffect(() => () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current); }, []);
  useEffect(() => { setOut(null); }, [file, tracks, skyline, melodyFill]);

  const render = async () => {
    if (!file) return;
    setBusy(true); setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("tracks", (tracks || []).join(","));
    form.append("skyline", String(!!skyline));
    form.append("melody_fill", String(!!melodyFill && !!(tracks && tracks.length)));
    form.append("chords", String(!!settings.chords));
    form.append("duration", String(settings.autoFit ? 0 : settings.duration));
    form.append("rev_seconds", String(revSeconds));
    form.append("roll", settings.roll);
    form.append("auto_transpose", String(!!settings.autoTranspose));
    form.append("manual_offset", String(settings.manualOffset));
    try {
      const res = await axios.post(`${api}/render`, form, { responseType: "blob" });
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      const url = URL.createObjectURL(res.data);
      urlRef.current = url;
      const h = res.headers;
      setOut({
        url, sides: +h["x-sides"], notes: +h["x-notes"], duration: +h["x-duration"], start: +h["x-start"],
        offset: +h["x-offset"], score: h["x-fit-score"] ? +h["x-fit-score"] : null, rate: +h["x-sample-rate"] || 6000,
        name: file.name.replace(/\.[^.]+$/, ""),
      });
    } catch (e) {
      let msg = "Could not render the song.";
      try { msg = JSON.parse(await e.response.data.text()).detail || msg; } catch (_) { /* keep */ }
      setError(msg);
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="song-review" className="flex flex-col gap-2">
      <button
        type="button" data-testid="render-song-button" disabled={disabled || busy || !file} onClick={render}
        className={`${BTN_BASE} text-base py-3 ${disabled || busy || !file ? BTN_DISABLED : "bg-[#457B9D] text-white"}`}
        title="Hear the whole song exactly as the toy will play it"
      >
        {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Headphones className="h-5 w-5" />}
        {busy ? "RENDERING…" : "HEAR THE WHOLE SONG AS THE TOY"}
      </button>
      <p className="font-mono text-[10px] text-[#457B9D] -mt-1">
        Converts the full MIDI to Fisher-Price notes (16 tines, staggered, toy speed) and renders it as 8 kHz mono audio for review.
      </p>
      {error && <div data-testid="render-error" className="font-mono text-xs bg-[#E63946] text-white rounded-md p-2 flex items-center gap-2"><AlertTriangle className="h-4 w-4" /> {error}</div>}
      {out && (
        <div data-testid="render-result" className="border-2 border-[#1D3557] rounded-lg bg-[#F4F1EA] p-3 flex flex-col gap-2 font-mono text-[11px] text-[#1D3557]">
          <audio data-testid="render-audio" controls src={out.url} className="w-full" />
          <div data-testid="render-meta" className="text-[#457B9D]">
            {out.sides} side(s) · {out.notes} toy notes · {out.duration.toFixed(1)} s of song per revolution · from {out.start.toFixed(1)} s · transposed {out.offset > 0 ? "+" : ""}{out.offset} st
            {out.score != null ? ` · ${Math.round(out.score)}% match` : ""} · {out.rate / 1000} kHz mono
          </div>
          <a data-testid="render-download" href={out.url} download={`${out.name}-fisher-price-6kHz-mono.wav`} className={`${BTN_BASE} text-sm py-2 bg-[#2A9D8F] text-white`}>
            <Download className="h-4 w-4" /> DOWNLOAD .WAV
          </a>
        </div>
      )}
    </div>
  );
}
