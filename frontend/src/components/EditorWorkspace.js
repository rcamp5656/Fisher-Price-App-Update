import React, { useEffect, useMemo, useState } from "react";
import { Play, Square, RotateCcw, Gauge, AlertTriangle, Repeat, Shuffle, FileMusic } from "lucide-react";
import NoteEditor from "./NoteEditor";
import TrackView from "./TrackView";
import { useMusicBox } from "../hooks/useMusicBox";
import { countNotes, speedPct, grooveConflicts, chordConflicts, makePlayable, BTN_LIFT } from "../lib/fp";

function Stat({ label, value, warn, testId }) {
  return (
    <div data-testid={testId} className={`border-2 border-[#1D3557] rounded-md px-2 py-1 ${warn ? "bg-[#FFB703]" : "bg-white"}`}>
      <div className="text-[9px] uppercase text-[#457B9D] leading-none">{label}</div>
      <div className="font-black text-sm leading-tight">{value}</div>
    </div>
  );
}

export default function EditorWorkspace({
  sides, active, onActive, duration, revSeconds, onRevSeconds, loop, onLoop,
}) {
  const side = sides.find((s) => s.key === active) || sides[0];
  const [view, setView] = useState("pitch");
  const sequence = useMemo(() => sides.map((s) => s.partition), [sides]);
  const { playing, sideIdx, play, stop, getPos, tap } = useMusicBox(sequence, revSeconds, loop);
  const a = side.analysis;
  const pct = speedPct(duration, revSeconds);
  const repeats = useMemo(() => grooveConflicts(side.partition), [side.partition]);
  const chords = useMemo(() => chordConflicts(side.partition), [side.partition]);
  const conflicts = useMemo(() => new Set([...repeats, ...chords]), [repeats, chords]);
  const clashCount = repeats.size;
  const chordCount = chords.size;

  useEffect(() => {
    if (playing && sides[sideIdx]) onActive(sides[sideIdx].key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, sideIdx]);

  const activeIdx = sides.indexOf(side);
  const getBeat = () => {
    const p = getPos();
    return p && p.side === activeIdx ? p.beat : -1;
  };

  return (
    <div className="flex flex-col h-full p-4 gap-3" data-testid="editor-workspace">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border-2 border-[#1D3557] overflow-hidden font-sans font-black text-xs">
          {[["pitch", "16 PITCHES"], ["tracks", "22 TINES"]].map(([v, l]) => (
            <button
              key={v} data-testid={`view-${v}`} onClick={() => setView(v)}
              className={`px-3 py-1.5 ${view === v ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"}`}
            >
              {l}
            </button>
          ))}
        </div>
        {sides.length > 1 && sides.map((s, i) => (
          <button
            key={s.key}
            data-testid={`side-tab-${s.key}`}
            onClick={() => { if (!playing) onActive(s.key); }}
            className={`font-sans font-black text-sm px-3 py-1.5 rounded-lg border-2 border-[#1D3557] flex items-center gap-2 ${
              s.key === active ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"
            }`}
          >
            {playing && sideIdx === i && <span className="h-2 w-2 rounded-full bg-[#E63946] animate-pulse" />}
            SIDE {s.key.toUpperCase()} · {s.title || "untitled"}
          </button>
        ))}
        <div className="flex gap-2 font-mono ml-auto">
          <Stat label="Notes" value={countNotes(side.partition)} testId="stat-notes" />
          <Stat label="On-pitch" value={a.exact} />
          <Stat label="Snapped" value={a.adjusted} warn={a.adjusted > 0} />
          <Stat label="Merged" value={a.merged} warn={a.merged > 0} />
          <Stat label="Too close" value={clashCount} warn={clashCount > 0} testId="stat-repeats" />
          <Stat label="Chords" value={chordCount} warn={chordCount > 0} testId="stat-chords" />
          {a.staggered > 0 && <Stat label="Staggered" value={a.staggered} testId="stat-staggered" />}
          {a.dropped > 0 && <Stat label="Dropped" value={a.dropped} warn testId="stat-dropped" />}
          <Stat label="Transpose" value={`${a.offset >= 0 ? "+" : ""}${a.offset}`} />
        </div>
      </div>

      {a.dropped > 0 && (
        <p data-testid="dropped-notice" className="font-mono text-[11px] text-[#1D3557] bg-white border-2 border-[#1D3557] rounded-md px-2 py-1 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {a.dropped} MIDI note(s) were dropped to fit the toy (cams in one groove need ≥ 2 beats of spacing). The MIDI capture is kept —
          {a.partition_midi && (
            <button type="button" data-testid="load-midi-raw-button" onClick={() => side.onChange(a.partition_midi)}
              className="font-sans font-black text-[11px] px-2 py-0.5 rounded border-2 border-[#1D3557] bg-[#E9C46A] flex items-center gap-1 whitespace-nowrap">
              <FileMusic className="h-3 w-3" /> SHOW MIDI VERSION
            </button>
          )}
        </p>
      )}
      {a.merged > 0 && (
        <p data-testid="merged-warning" className="font-mono text-[11px] text-[#1D3557] bg-[#FFB703] border-2 border-[#1D3557] rounded-md px-2 py-1 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {a.merged} note(s) landed on an already-filled beat and were merged — shorten the capture window for finer timing.
        </p>
      )}
      {chordCount > 0 && (
        <p data-testid="chord-warning" className="font-mono text-[11px] text-[#1D3557] bg-[#FFB703] border-2 border-[#E63946] rounded-md px-2 py-1 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[#E63946]" />
          {chordCount} highlighted note(s) share a beat with another note — the player plucks one tine at a time, so they must be offset (the originals always stagger them).
          <button type="button" data-testid="auto-stagger-button" onClick={() => side.onChange(makePlayable(side.partition))}
            className="ml-auto font-sans font-black text-[11px] px-2 py-0.5 rounded border-2 border-[#1D3557] bg-[#1D3557] text-white flex items-center gap-1 whitespace-nowrap">
            <Shuffle className="h-3 w-3" /> MAKE PLAYABLE
          </button>
        </p>
      )}
      {clashCount > 0 && (
        <p data-testid="repeat-warning" className="font-mono text-[11px] text-[#1D3557] bg-[#FFB703] border-2 border-[#E63946] rounded-md px-2 py-1 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[#E63946]" />
          {clashCount} highlighted note(s) are too close in the same groove — cams need ≥ 2 beats between them (a 2.4 mm cam is longer than one beat at the inner tracks) or they overlap and jam the tines.
          <button type="button" data-testid="make-playable-button" onClick={() => side.onChange(makePlayable(side.partition))}
            className="ml-auto font-sans font-black text-[11px] px-2 py-0.5 rounded border-2 border-[#1D3557] bg-[#1D3557] text-white flex items-center gap-1 whitespace-nowrap">
            <Shuffle className="h-3 w-3" /> MAKE PLAYABLE
          </button>
        </p>
      )}

      <div className="overflow-x-auto flex-1">
        <div className="min-w-[760px]">
          {view === "tracks" ? (
            <TrackView partition={side.partition} duration={duration} overrides={side.overrides} onOverrides={side.onOverrides} />
          ) : (
            <NoteEditor
              partition={side.partition}
              onChange={side.onChange}
              duration={duration}
              playing={playing}
              getBeat={getBeat}
              onTap={tap}
              conflicts={conflicts}
            />
          )}
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
          {playing ? "STOP" : sides.length > 1 ? "PLAY A → B" : "PLAY PREVIEW"}
        </button>
        <button
          data-testid="loop-button"
          aria-pressed={loop}
          onClick={() => onLoop(!loop)}
          title="Loop the disc"
          className={`font-sans font-bold text-sm px-3 py-2 rounded-lg border-2 border-[#1D3557] flex items-center gap-2 shadow-[3px_3px_0_0_#1D3557] ${BTN_LIFT} ${
            loop ? "bg-[#E63946] text-white" : "bg-white"
          }`}
        >
          <Repeat className="h-4 w-4" /> Loop
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
            type="range" min="20" max="60" step="1" value={revSeconds}
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
        click empty = add · click note = remove · drag note = nudge · row label = tine number(s) on the 22-tine comb · preview sounds at real toy pitch (A♭ major)
      </p>
    </div>
  );
}
