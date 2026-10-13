import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { NOTES, MAX_BEAT, TWIN_TINE, TINES, REAL_PITCH_OFFSET, noteName, clonePartition } from "../lib/fp";

const LABEL_W = 64;
const GAP = 1;
const MIN_CELL = 9;

function Playhead({ playing, getBeat, from, to, cellW, rowH }) {
  const [beat, setBeat] = useState(-1);
  useEffect(() => {
    if (!playing) { setBeat(-1); return undefined; }
    let raf;
    const tick = () => { setBeat(getBeat()); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, getBeat]);
  if (beat < from || beat > to + 1) return null;
  return (
    <div
      data-testid="playhead"
      className="absolute w-[2px] bg-[#E63946] pointer-events-none z-10 shadow-[0_0_6px_#E63946]"
      style={{ top: 0, bottom: 0, left: LABEL_W + (beat - from) * (cellW + GAP) }}
    />
  );
}

const cellAt = (e) => {
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const c = el && el.closest ? el.closest("[data-beat]") : null;
  return c ? { tone: +c.dataset.tone, beat: +c.dataset.beat } : null;
};
const same = (a, b) => a.tone === b.tone && a.beat === b.beat;

// grid lines: strong every 10 beats, light every 5
const barClass = (b) => (b % 10 === 0 ? "border-l-2 border-l-[#1D3557]/60" : b % 5 === 0 ? "border-l border-l-[#1D3557]/30" : "");

export default function NoteEditor({ partition, onChange, duration, start = 0, playing, getBeat, onTap, conflicts, fit = false, onSeek, cueBeat = null, ghosts }) {
  const drag = useRef(null);
  const box = useRef(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  // show only the beats that carry notes (plus one spare beat each side) when `fit` is on
  const usedBeats = [];
  partition.forEach((row) => row.forEach((on, b) => { if (on) usedBeats.push(b); }));
  const from = fit && usedBeats.length ? Math.max(0, Math.min(...usedBeats) - 1) : 0;
  const to = fit && usedBeats.length ? Math.min(MAX_BEAT - 1, Math.max(...usedBeats) + 1) : MAX_BEAT - 1;
  const beats = Array.from({ length: to - from + 1 }, (_, i) => from + i);

  const cellW = Math.max(MIN_CELL, Math.floor((width - LABEL_W - GAP * beats.length - 1) / beats.length));
  const rowH = Math.max(20, Math.min(30, Math.round(cellW * 2.2)));
  const secPerBeat = duration / MAX_BEAT;
  const songTime = (b) => (start + b * secPerBeat).toFixed(1);
  const cols = { gridTemplateColumns: `${LABEL_W}px repeat(${beats.length}, ${cellW}px)`, gap: GAP };

  const update = (fn) => {
    const next = clonePartition(partition);
    fn(next);
    onChange(next);
  };

  const onPointerDown = (e) => {
    const c = cellAt(e);
    if (!c) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    if (partition[c.tone][c.beat]) {
      drag.current = { from: c, moved: false, added: false };
    } else {
      update((p) => { p[c.tone][c.beat] = true; });
      onTap(c.tone);
      drag.current = { from: c, moved: false, added: true };
    }
  };

  const onPointerMove = (e) => {
    const d = drag.current;
    if (!d || d.added) return;
    const c = cellAt(e);
    if (!c || same(c, d.from) || partition[c.tone][c.beat]) return;
    update((p) => { p[d.from.tone][d.from.beat] = false; p[c.tone][c.beat] = true; });
    if (c.tone !== d.from.tone) onTap(c.tone);
    drag.current = { from: c, moved: true, added: false };
  };

  const onPointerUp = () => {
    const d = drag.current;
    if (d && !d.moved && !d.added) update((p) => { p[d.from.tone][d.from.beat] = false; });
    drag.current = null;
  };

  return (
    <div className="relative select-none" data-testid="note-editor" ref={box}>
      <div className="flex items-baseline justify-between font-mono text-[10px] text-[#457B9D] mb-1 pl-[64px]" data-testid="window-ruler-caption">
        <span>
          window <b className="text-[#1D3557]">{songTime(0)}s → {songTime(MAX_BEAT)}s</b> of song · {fit ? `beats ${from}–${to}` : "86 beats = 1 revolution"}
        </span>
        <span>{secPerBeat.toFixed(2)} s / beat</span>
      </div>
      <div className="grid" style={cols} data-testid="beat-ruler" title="Click a beat to play from there">
        <div className="font-mono text-[8px] text-[#457B9D] leading-none pr-1 text-right self-end">play from ▸</div>
        {beats.map((b) => (
          <div
            key={b}
            data-testid={`ruler-beat-${b}`}
            onClick={() => onSeek && onSeek(b)}
            className={`relative h-6 font-mono text-[9px] text-[#457B9D] leading-none cursor-pointer hover:bg-[#E63946]/20 rounded-t ${barClass(b)} ${cueBeat === b ? "bg-[#E63946]/30" : ""}`}
          >
            {b % 10 === 0 && (
              <span className="absolute left-0.5 top-0 whitespace-nowrap pointer-events-none">
                <span className="font-bold text-[#1D3557]">{b}</span>
                <span className="block">{songTime(b)}s</span>
              </span>
            )}
            {cueBeat === b && (
              <span data-testid="cue-marker" className="absolute left-1/2 -translate-x-1/2 bottom-0 w-0 h-0 border-l-[5px] border-r-[5px] border-t-[6px] border-l-transparent border-r-transparent border-t-[#E63946] pointer-events-none" />
            )}
          </div>
        ))}
      </div>
      <div
        className="relative grid cursor-crosshair touch-none"
        style={cols}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <Playhead playing={playing} getBeat={getBeat} from={from} to={to} cellW={cellW} rowH={rowH} />
        {[...partition].map((_, i) => NOTES.length - 1 - i).map((tone) => (
          <React.Fragment key={tone}>
            <div
              style={{ height: rowH }}
              className="font-mono text-[10px] font-bold pr-1 text-right text-[#1D3557] flex items-center justify-end gap-1"
              title={`${noteName(NOTES[tone])} in Fred's notation · sounds ${noteName(NOTES[tone] + REAL_PITCH_OFFSET)} on the toy · tine${TINES[tone].length > 1 ? "s" : ""} ${TINES[tone].join("+")}${TWIN_TINE.has(tone) ? " (twin — can repeat on consecutive beats)" : ""}`}
            >
              <span className="text-[#457B9D] text-[8px] leading-none font-normal">{TINES[tone].join("+")}</span>
              {noteName(NOTES[tone])}
            </div>
            {beats.map((beat) => {
              const on = partition[tone][beat];
              const clash = on && conflicts.has(`${tone}-${beat}`);
              const ghost = !on && ghosts && ghosts.has(`${tone}-${beat}`);
              return (
                <div
                  key={beat}
                  data-tone={tone}
                  data-beat={beat}
                  data-testid={on ? (clash ? `clash-${tone}-${beat}` : `note-${tone}-${beat}`) : undefined}
                  title={clash ? "Can't be played this close to another note — use MAKE PLAYABLE" : ghost ? "The MIDI had this note here — it was moved so the toy can play it" : undefined}
                  style={{ height: rowH }}
                  className={`rounded-[2px] border transition-colors duration-100 ${barClass(beat)} ${
                    clash
                      ? "bg-[#FFB703] border-[#E63946] border-2 hover:bg-[#e0a000]"
                      : on
                        ? "bg-[#E63946] border-[#1D3557] hover:bg-[#c42f3b]"
                        : ghost
                          ? "bg-white border-dashed border-[#E63946]/70 hover:bg-[#E9C46A]"
                        : tone % 2 === 0
                          ? "bg-white border-[#1D3557]/15 hover:bg-[#E9C46A]"
                          : "bg-[#F4F1EA] border-[#1D3557]/15 hover:bg-[#E9C46A]"
                  }`}
                />
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
