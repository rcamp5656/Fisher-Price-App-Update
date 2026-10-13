import React, { useEffect, useRef, useState } from "react";
import { NOTES, MAX_BEAT, TWIN_TINE, TINES, REAL_PITCH_OFFSET, noteName, clonePartition } from "../lib/fp";

const LABEL_W = 64;

function Playhead({ playing, getBeat }) {
  const [beat, setBeat] = useState(-1);
  useEffect(() => {
    if (!playing) { setBeat(-1); return undefined; }
    let raf;
    const tick = () => { setBeat(getBeat()); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, getBeat]);
  if (beat < 0 || beat > MAX_BEAT) return null;
  return (
    <div
      data-testid="playhead"
      className="absolute top-0 bottom-0 w-[2px] bg-[#E63946] pointer-events-none z-10"
      style={{ left: `calc(${LABEL_W}px + (100% - ${LABEL_W}px) * ${beat / MAX_BEAT})` }}
    />
  );
}

const cellAt = (e) => {
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const c = el && el.closest ? el.closest("[data-beat]") : null;
  return c ? { tone: +c.dataset.tone, beat: +c.dataset.beat } : null;
};
const same = (a, b) => a.tone === b.tone && a.beat === b.beat;

export default function NoteEditor({ partition, onChange, duration, playing, getBeat, onTap, conflicts }) {
  const drag = useRef(null);

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

  const cols = { gridTemplateColumns: `${LABEL_W}px repeat(${MAX_BEAT}, minmax(0, 1fr))` };

  return (
    <div className="relative select-none" data-testid="note-editor">
      <div className="grid gap-[1px]" style={cols}>
        <div />
        {Array.from({ length: MAX_BEAT }, (_, b) => (
          <div key={b} className="h-4 font-mono text-[9px] text-[#457B9D] leading-4 overflow-visible whitespace-nowrap">
            {b % 10 === 0 ? `${((b * duration) / MAX_BEAT).toFixed(0)}s` : ""}
          </div>
        ))}
      </div>
      <div
        className="relative grid gap-[1px] cursor-crosshair touch-none"
        style={cols}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <Playhead playing={playing} getBeat={getBeat} />
        {[...partition].map((_, i) => NOTES.length - 1 - i).map((tone) => (
          <React.Fragment key={tone}>
            <div
              className="h-6 font-mono text-[10px] font-bold leading-6 pr-1 text-right text-[#1D3557] flex items-center justify-end gap-1"
              title={`${noteName(NOTES[tone])} in Fred's notation · sounds ${noteName(NOTES[tone] + REAL_PITCH_OFFSET)} on the toy · tine${TINES[tone].length > 1 ? "s" : ""} ${TINES[tone].join("+")}${TWIN_TINE.has(tone) ? " (twin — can repeat on consecutive beats)" : ""}`}
            >
              <span className="text-[#457B9D] text-[8px] leading-none font-normal">{TINES[tone].join("+")}</span>
              {noteName(NOTES[tone])}
            </div>
            {partition[tone].map((on, beat) => {
              const clash = on && conflicts.has(`${tone}-${beat}`);
              return (
                <div
                  key={beat}
                  data-tone={tone}
                  data-beat={beat}
                  data-testid={on ? (clash ? `clash-${tone}-${beat}` : `note-${tone}-${beat}`) : undefined}
                  title={clash ? "Single tine can't re-strike this fast — may go silent" : undefined}
                  className={`h-6 rounded-[2px] border transition-colors duration-100 ${
                    clash
                      ? "bg-[#FFB703] border-[#E63946] border-2 hover:bg-[#e0a000]"
                      : on
                        ? "bg-[#E63946] border-[#1D3557] hover:bg-[#c42f3b]"
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
