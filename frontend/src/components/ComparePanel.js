import React, { useEffect, useMemo, useRef, useState } from "react";
import { Play, Square, ArrowLeftRight } from "lucide-react";
import { NOTES, MAX_BEAT, REAL_PITCH_OFFSET, midiToFreq, countNotes, diffPartitions } from "../lib/fp";
import { pluck, newCtx } from "../hooks/useMusicBox";

// one compact 16 x 86 grid — `mark` colours cells that differ from the other version
function MiniGrid({ partition, mark, color, beat, testId }) {
  return (
    <div className="relative border-2 border-[#1D3557] rounded-md bg-white overflow-hidden" data-testid={testId}>
      <div className="grid gap-px" style={{ gridTemplateColumns: `repeat(${MAX_BEAT}, minmax(0, 1fr))` }}>
        {[...partition].map((_, i) => NOTES.length - 1 - i).map((tone) =>
          partition[tone].map((on, b) => (
            <div
              key={`${tone}-${b}`}
              className={`h-[5px] ${on ? (mark.has(`${tone}-${b}`) ? color : "bg-[#1D3557]") : b % 10 === 0 ? "bg-[#1D3557]/10" : "bg-[#F4F1EA]"}`}
            />
          ))
        )}
      </div>
      {beat >= 0 && (
        <div className="absolute top-0 bottom-0 w-[2px] bg-[#E63946] pointer-events-none" style={{ left: `${(beat / MAX_BEAT) * 100}%` }} />
      )}
    </div>
  );
}

// plays a partition grid at toy speed, reporting the playhead beat
function useGridPlayer(revSeconds) {
  const ctxRef = useRef(null);
  const t0Ref = useRef(0);
  const [which, setWhich] = useState(null);
  const [beat, setBeat] = useState(-1);
  const stop = () => { if (ctxRef.current) ctxRef.current.close(); ctxRef.current = null; setWhich(null); setBeat(-1); };
  useEffect(() => stop, []);
  useEffect(() => {
    if (!which) return undefined;
    let raf;
    const tick = () => {
      const ctx = ctxRef.current;
      if (ctx) setBeat((ctx.currentTime - t0Ref.current) / (revSeconds / MAX_BEAT));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [which, revSeconds]);
  const play = (key, partition) => {
    stop();
    const ctx = newCtx();
    ctxRef.current = ctx;
    const beatSec = revSeconds / MAX_BEAT;
    const t0 = ctx.currentTime + 0.1;
    t0Ref.current = t0;
    let last = 0;
    partition.forEach((row, tone) => row.forEach((on, b) => {
      if (!on) return;
      last = Math.max(last, b);
      pluck(ctx, ctx.destination, midiToFreq(NOTES[tone] + REAL_PITCH_OFFSET), t0 + b * beatSec);
    }));
    setWhich(key);
    setTimeout(() => { if (ctxRef.current === ctx) stop(); }, ((last + 1) * beatSec + 1.5) * 1000);
  };
  return { which, beat, play, stop };
}

export default function ComparePanel({ midi, disc, revSeconds }) {
  const { moved, placed } = useMemo(() => diffPartitions(midi, disc), [midi, disc]);
  const { which, beat, play, stop } = useGridPlayer(revSeconds);
  if (!midi) return null;
  const chords = (() => { let n = 0; for (let b = 0; b < MAX_BEAT; b++) { const c = midi.reduce((s, r) => s + (r[b] ? 1 : 0), 0); if (c > 1) n += c - 1; } return n; })();
  const Btn = ({ k, part, label }) => (
    <button
      type="button" data-testid={`compare-play-${k}`} onClick={() => (which === k ? stop() : play(k, part))}
      className={`font-sans font-black text-[11px] px-2 py-1 rounded border-2 border-[#1D3557] flex items-center gap-1 ${which === k ? "bg-[#1D3557] text-white" : "bg-[#2A9D8F] text-white"}`}
    >
      {which === k ? <Square className="h-3 w-3" /> : <Play className="h-3 w-3" />} {which === k ? "STOP" : label}
    </button>
  );
  return (
    <div data-testid="compare-panel" className="border-2 border-[#1D3557] rounded-lg bg-[#F4F1EA] p-3 flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-[#1D3557]">
        <ArrowLeftRight className="h-4 w-4" />
        <span className="font-sans font-black text-sm">MIDI vs DISC</span>
        <span className="text-[#457B9D]" data-testid="compare-summary">
          {moved.size === 0 && placed.size === 0
            ? "identical — the toy plays exactly what the MIDI wrote"
            : `${moved.size} note(s) moved to free beats${chords ? ` (${chords} were stacked in chords)` : ""} · ${countNotes(midi)} MIDI notes → ${countNotes(disc)} pins`}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-[#457B9D]">MIDI slice as written · <span className="inline-block h-2 w-2 bg-[#FFB703] border border-[#1D3557] align-middle" /> will move</span>
            <Btn k="midi" part={midi} label="HEAR MIDI" />
          </div>
          <MiniGrid partition={midi} mark={moved} color="bg-[#FFB703]" beat={which === "midi" ? beat : -1} testId="compare-grid-midi" />
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-[#457B9D]">Disc as the toy plays it · <span className="inline-block h-2 w-2 bg-[#2A9D8F] border border-[#1D3557] align-middle" /> moved here</span>
            <Btn k="disc" part={disc} label="HEAR DISC" />
          </div>
          <MiniGrid partition={disc} mark={placed} color="bg-[#2A9D8F]" beat={which === "disc" ? beat : -1} testId="compare-grid-disc" />
        </div>
      </div>
    </div>
  );
}
