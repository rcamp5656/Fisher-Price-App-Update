import React, { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, ChevronLeft, ChevronRight, Play, Square } from "lucide-react";
import { INPUT, MAX_BEAT, midiToFreq, REAL_PITCH_OFFSET } from "../lib/fp";
import { pluck, newCtx } from "../hooks/useMusicBox";

// Whole-song pin map with a draggable capture window
export default function SongOverview({ scan: rawScan, tracks, duration, start, onStart, label, revSeconds = 25 }) {
  const ref = useRef(null);
  const [playing, setPlaying] = useState(false);
  const ctxRef = useRef(null);
  const stopSel = () => { if (ctxRef.current) ctxRef.current.close(); ctxRef.current = null; setPlaying(false); };
  useEffect(() => stopSel, []);
  // raw MIDI preview of exactly what sits inside the window, at toy speed
  // only the chosen tracks are shown and heard
  const scan = useMemo(() => {
    if (!tracks || !tracks.length) return rawScan;
    const sel = new Set(tracks);
    const events = rawScan.events.filter((e) => e.length < 3 || sel.has(e[2]));
    return { ...rawScan, events: events.length ? events : rawScan.events };
  }, [rawScan, tracks]);
  const playSel = () => {
    stopSel();
    const ctx = newCtx();
    ctxRef.current = ctx;
    const t0 = ctx.currentTime + 0.1;
    const scale = revSeconds / duration;
    const sel = scan.events.filter(([t]) => t >= start && t < start + duration);
    sel.forEach(([t, n]) => pluck(ctx, ctx.destination, midiToFreq(n + REAL_PITCH_OFFSET), t0 + (t - start) * scale));
    setPlaying(true);
    const len = sel.length ? (Math.max(...sel.map(([t]) => t)) - start) * scale + 2 : 0.5;
    setTimeout(() => { if (ctxRef.current === ctx) stopSel(); }, len * 1000);
  };
  const total = Math.max(scan.total, duration, 1);
  const { lo, hi } = useMemo(() => {
    const ns = scan.events.map((e) => e[1]);
    return { lo: Math.min(...ns) - 1, hi: Math.max(...ns) + 1 };
  }, [scan]);
  const winPct = Math.min(100, (duration / total) * 100);
  const startPct = (Math.min(start, Math.max(0, total - duration)) / total) * 100;
  const inWindow = (t) => t >= start && t < start + duration;

  const seek = (clientX) => {
    const r = ref.current.getBoundingClientRect();
    const t = ((clientX - r.left) / r.width) * total - duration / 2;
    onStart(Math.round(Math.max(0, Math.min(total - duration, t)) * 10) / 10);
  };
  const drag = useRef(false);
  const maxStart = Math.max(0, total - duration);
  const setStart = (v) => onStart(Math.round(Math.max(0, Math.min(maxStart, Number(v) || 0)) * 10) / 10);

  return (
    <div data-testid="song-overview" className="font-mono text-[10px] text-[#457B9D]">
      <div className="flex items-center justify-between mb-1">
        <span className="flex items-center gap-1"><Crosshair className="h-3 w-3" /> {label || "Whole song"} · {scan.events.length} notes · {scan.total.toFixed(0)}s — drag the {MAX_BEAT}-beat window ({duration}s of song)</span>
        <span className="font-bold text-[#1D3557]" data-testid="window-start">{start.toFixed(1)}s → {(start + duration).toFixed(1)}s</span>
      </div>
      <div className="flex items-center gap-1 mb-1">
        <button type="button" data-testid="window-nudge-left" onClick={() => setStart(start - 0.5)} disabled={start <= 0}
          className="h-7 w-7 flex items-center justify-center rounded border-2 border-[#1D3557] bg-white hover:bg-[#E9C46A] disabled:opacity-40">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <label className="flex items-center gap-1 text-[#1D3557]">
          start
          <input data-testid="window-start-input" type="number" step="0.1" min="0" max={maxStart.toFixed(1)} value={start}
            onChange={(e) => setStart(e.target.value)} className={`${INPUT} w-20 py-0.5 text-xs`} />
          s
        </label>
        <button type="button" data-testid="window-nudge-right" onClick={() => setStart(start + 0.5)} disabled={start >= maxStart}
          className="h-7 w-7 flex items-center justify-center rounded border-2 border-[#1D3557] bg-white hover:bg-[#E9C46A] disabled:opacity-40">
          <ChevronRight className="h-4 w-4" />
        </button>
        <button type="button" data-testid="window-play" onClick={playing ? stopSel : playSel} title="Hear the MIDI inside the window"
          className={`h-7 px-2 flex items-center gap-1 rounded border-2 border-[#1D3557] font-bold ${playing ? "bg-[#1D3557] text-white" : "bg-[#2A9D8F] text-white"}`}>
          {playing ? <Square className="h-3 w-3" /> : <Play className="h-3 w-3" />} {playing ? "STOP" : "HEAR WINDOW"}
        </button>
        <span className="ml-auto">max {maxStart.toFixed(1)}s</span>
      </div>
      <div
        ref={ref}
        className="relative h-20 border-2 border-[#1D3557] rounded-md bg-white overflow-hidden cursor-ew-resize select-none touch-none"
        onPointerDown={(e) => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId); seek(e.clientX); }}
        onPointerMove={(e) => { if (drag.current) seek(e.clientX); }}
        onPointerUp={() => { drag.current = false; }}
        onPointerCancel={() => { drag.current = false; }}
      >
        {scan.events.map(([t, n], i) => (
          <span
            key={i}
            className={`absolute w-[3px] h-[3px] rounded-full ${inWindow(t) ? "bg-[#E63946]" : "bg-[#1D3557]/40"}`}
            style={{ left: `${(t / total) * 100}%`, top: `${(1 - (n - lo) / (hi - lo)) * 100}%` }}
          />
        ))}
        <div
          data-testid="capture-window"
          className="absolute top-0 bottom-0 border-x-2 border-[#E63946] bg-[#E63946]/10 pointer-events-none"
          style={{ left: `${startPct}%`, width: `${winPct}%` }}
        />
      </div>
    </div>
  );
}
