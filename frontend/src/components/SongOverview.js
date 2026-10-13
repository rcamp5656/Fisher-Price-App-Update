import React, { useMemo, useRef } from "react";
import { Crosshair } from "lucide-react";

// Whole-song pin map with a draggable capture window
export default function SongOverview({ scan, duration, start, onStart, label }) {
  const ref = useRef(null);
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

  return (
    <div data-testid="song-overview" className="font-mono text-[10px] text-[#457B9D]">
      <div className="flex items-center justify-between mb-1">
        <span className="flex items-center gap-1"><Crosshair className="h-3 w-3" /> {label || "Whole song"} · {scan.events.length} notes · {scan.total.toFixed(0)}s — drag the window to the best {duration}s</span>
        <span className="font-bold text-[#1D3557]" data-testid="window-start">{start.toFixed(1)}s → {(start + duration).toFixed(1)}s</span>
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
