import React from "react";
import { Play, Square, RotateCcw, Gauge, AlertTriangle } from "lucide-react";
import NoteEditor from "./NoteEditor";
import { useMusicBox } from "../hooks/useMusicBox";
import { countNotes, speedPct, BTN_LIFT } from "../lib/fp";

function Stat({ label, value, warn }) {
  return (
    <div className={`border-2 border-[#1D3557] rounded-md px-2 py-1 ${warn ? "bg-[#FFB703]" : "bg-white"}`}>
      <div className="text-[9px] uppercase text-[#457B9D] leading-none">{label}</div>
      <div className="font-black text-sm leading-tight">{value}</div>
    </div>
  );
}

export default function EditorWorkspace({
  sides, active, onActive, duration, revSeconds, onRevSeconds,
}) {
  const side = sides.find((s) => s.key === active) || sides[0];
  const { playing, play, stop, getBeat, tap } = useMusicBox(side.partition, revSeconds);
  const a = side.analysis;
  const pct = speedPct(duration, revSeconds);

  return (
    <div className="flex flex-col h-full p-4 gap-3" data-testid="editor-workspace">
      <div className="flex flex-wrap items-center gap-2">
        {sides.length > 1 && sides.map((s) => (
          <button
            key={s.key}
            data-testid={`side-tab-${s.key}`}
            onClick={() => { stop(); onActive(s.key); }}
            className={`font-sans font-black text-sm px-3 py-1.5 rounded-lg border-2 border-[#1D3557] ${
              s.key === active ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"
            }`}
          >
            SIDE {s.key.toUpperCase()} · {s.title || "untitled"}
          </button>
        ))}
        <div className="flex gap-2 font-mono ml-auto">
          <Stat label="Notes" value={countNotes(side.partition)} />
          <Stat label="On-pitch" value={a.exact} />
          <Stat label="Snapped" value={a.adjusted} warn={a.adjusted > 0} />
          <Stat label="Merged" value={a.merged} warn={a.merged > 0} />
          <Stat label="Transpose" value={`${a.offset >= 0 ? "+" : ""}${a.offset}`} />
        </div>
      </div>

      {a.merged > 0 && (
        <p data-testid="merged-warning" className="font-mono text-[11px] text-[#1D3557] bg-[#FFB703] border-2 border-[#1D3557] rounded-md px-2 py-1 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {a.merged} note(s) landed on an already-filled beat and were merged — shorten the capture window for finer timing.
        </p>
      )}

      <div className="overflow-x-auto flex-1">
        <div className="min-w-[760px]">
          <NoteEditor
            partition={side.partition}
            onChange={side.onChange}
            duration={duration}
            playing={playing}
            getBeat={getBeat}
            onTap={tap}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t-2 border-[#1D3557]/20 pt-3">
        <button
          data-testid="play-button"
          onClick={playing ? stop : play}
          className={`font-sans font-black text-sm px-4 py-2 rounded-lg border-2 border-[#1D3557] flex items-center gap-2 shadow-[3px_3px_0_0_#1D3557] ${BTN_LIFT} ${
            playing ? "bg-[#1D3557] text-white" : "bg-[#2A9D8F] text-white"
          }`}
        >
          {playing ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {playing ? "STOP" : "PLAY PREVIEW"}
        </button>
        <button
          data-testid="reset-notes-button"
          onClick={() => { stop(); side.onChange(side.original); }}
          className={`font-sans font-bold text-sm px-3 py-2 rounded-lg border-2 border-[#1D3557] bg-white flex items-center gap-2 shadow-[3px_3px_0_0_#1D3557] ${BTN_LIFT}`}
        >
          <RotateCcw className="h-4 w-4" /> Reset
        </button>
        <label className="font-mono text-xs flex items-center gap-2 ml-auto">
          <Gauge className="h-4 w-4" /> Toy speed
          <input
            type="range" min="25" max="40" step="1" value={revSeconds}
            data-testid="rev-slider"
            onChange={(e) => onRevSeconds(Number(e.target.value))}
            className="w-28 accent-[#E63946]"
          />
          <span className="font-bold" data-testid="rev-value">{revSeconds}s / rev</span>
          <span className={`px-2 py-0.5 rounded border-2 border-[#1D3557] font-bold ${pct === 100 ? "bg-[#2A9D8F] text-white" : "bg-[#E9C46A]"}`} data-testid="speed-readout">
            {pct}% tempo
          </span>
        </label>
      </div>
      <p className="font-mono text-[10px] text-[#457B9D]">
        click empty = add · click note = remove · drag note = nudge · ×2 = twin-tine pitch (repeats fast) · preview at real toy speed
      </p>
    </div>
  );
}
