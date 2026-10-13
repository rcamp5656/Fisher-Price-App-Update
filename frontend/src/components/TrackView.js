import React, { useMemo } from "react";
import { NOTES, MAX_BEAT, TINE_COUNT, TRACK_TONE, TWIN_TINE, TINES, REAL_PITCH_OFFSET, noteName, toPhysical } from "../lib/fp";

const LABEL_W = 96;

// The 22 physical tracks exactly as they will be cut. Pins on twin-tine tracks
// can be clicked to move the note to the sibling tine.
export default function TrackView({ partition, duration, overrides = {}, onOverrides }) {
  const tracks = useMemo(() => toPhysical(partition, overrides), [partition, overrides]);
  const cols = { gridTemplateColumns: `${LABEL_W}px repeat(${MAX_BEAT}, minmax(0, 1fr))` };

  const flip = (track, beat) => {
    const tone = TRACK_TONE[track];
    if (!TWIN_TINE.has(tone) || !onOverrides) return;
    const slot = TINES[tone].indexOf(track + 1);
    onOverrides({ ...overrides, [`${tone}-${beat}`]: slot === 0 ? 1 : 0 });
  };

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
          const twin = TWIN_TINE.has(tone);
          const groove = Math.floor(track / 2) + 1;
          return (
            <React.Fragment key={track}>
              <div
                className={`h-[17px] font-mono text-[9px] leading-[17px] pr-1 text-right flex items-center justify-end gap-1 ${twin ? "text-[#2A9D8F]" : "text-[#1D3557]"}`}
                title={`Track ${track + 1} · ${twin ? "twin tine — click a pin to swap it to the sibling tine" : "single tine"} · sounds ${noteName(NOTES[tone] + REAL_PITCH_OFFSET)}`}
              >
                <span className="font-black">{track + 1}</span>
                <span>{noteName(NOTES[tone])}</span>
                <span className="text-[#457B9D]">g{groove}{track % 2 === 0 ? "i" : "o"}</span>
              </div>
              {tracks[track].map((on, beat) => (
                <div
                  key={beat}
                  data-testid={on ? `track-pin-${track}-${beat}` : undefined}
                  onClick={on ? () => flip(track, beat) : undefined}
                  className={`h-[17px] rounded-[2px] border ${
                    on
                      ? twin
                        ? "bg-[#2A9D8F] border-[#1D3557] cursor-pointer hover:bg-[#1D3557]"
                        : "bg-[#1D3557] border-[#1D3557]"
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
        22 tracks = 11 grooves × 2 walls (i = inner, o = outer). Green pins sit on twin tines — click one to move the note to its sibling tine. Add/remove notes in the pitch view.
      </p>
    </div>
  );
}
