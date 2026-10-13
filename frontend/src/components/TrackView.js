import React, { useMemo } from "react";
import { NOTES, MAX_BEAT, TINE_COUNT, TRACK_TONE, TWIN_TINE, REAL_PITCH_OFFSET, noteName, toPhysical } from "../lib/fp";

const LABEL_W = 96;

// Read-only view of the 22 physical tracks exactly as they will be cut on the disc
export default function TrackView({ partition, duration }) {
  const tracks = useMemo(() => toPhysical(partition), [partition]);
  const cols = { gridTemplateColumns: `${LABEL_W}px repeat(${MAX_BEAT}, minmax(0, 1fr))` };

  return (
    <div className="select-none" data-testid="track-view">
      <div className="grid gap-[1px]" style={cols}>
        <div className="font-mono text-[9px] text-[#457B9D] leading-4">tine · note · groove</div>
        {Array.from({ length: MAX_BEAT }, (_, b) => (
          <div key={b} className="h-4 font-mono text-[9px] text-[#457B9D] leading-4 whitespace-nowrap">
            {b % 10 === 0 ? `${((b * duration) / MAX_BEAT).toFixed(0)}s` : ""}
          </div>
        ))}
      </div>
      <div className="grid gap-[1px]" style={cols}>
        {Array.from({ length: TINE_COUNT }, (_, i) => TINE_COUNT - 1 - i).map((track) => {
          const tone = TRACK_TONE[track];
          const groove = Math.floor(track / 2) + 1;
          return (
            <React.Fragment key={track}>
              <div
                className={`h-[17px] font-mono text-[9px] leading-[17px] pr-1 text-right flex items-center justify-end gap-1 ${
                  TWIN_TINE.has(tone) ? "text-[#2A9D8F]" : "text-[#1D3557]"
                }`}
                title={`Track ${track + 1} · ${TWIN_TINE.has(tone) ? "twin tine" : "single tine"} · sounds ${noteName(NOTES[tone] + REAL_PITCH_OFFSET)}`}
              >
                <span className="font-black">{track + 1}</span>
                <span>{noteName(NOTES[tone])}</span>
                <span className="text-[#457B9D]">g{groove}{track % 2 === 0 ? "i" : "o"}</span>
              </div>
              {tracks[track].map((on, beat) => (
                <div
                  key={beat}
                  data-testid={on ? `track-pin-${track}-${beat}` : undefined}
                  className={`h-[17px] rounded-[2px] border ${
                    on
                      ? "bg-[#1D3557] border-[#1D3557]"
                      : groove % 2 === 0
                        ? "bg-white border-[#1D3557]/15"
                        : "bg-[#F4F1EA] border-[#1D3557]/15"
                  }`}
                />
              ))}
            </React.Fragment>
          );
        })}
      </div>
      <p className="font-mono text-[10px] text-[#457B9D] mt-2">
        22 tracks = 11 grooves × 2 walls (i = inner, o = outer). Twin tines (green) take turns on repeated notes. Read-only — edit in the 16 PITCHES view.
      </p>
    </div>
  );
}
