import React from "react";
import { Wand2, Ruler, Clock, Tag, Disc3, Gauge, Hash, Layers, Target, Heart } from "lucide-react";
import { speedPct } from "../lib/fp";

export function Toggle({ checked, onChange, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={() => onChange(!checked)}
      className={`relative h-8 w-14 shrink-0 rounded-full border-2 border-[#1D3557] transition-colors duration-150 ${
        checked ? "bg-[#2A9D8F]" : "bg-[#E9C46A]"
      }`}
    >
      <span
        className={`absolute top-[2px] h-6 w-6 rounded-full border-2 border-[#1D3557] bg-white transition-transform duration-150 ${
          checked ? "translate-x-6" : "translate-x-[2px]"
        }`}
      />
    </button>
  );
}

const INPUT = "w-full font-mono text-sm border-2 border-[#1D3557] rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#E63946]";

function Row({ icon: Icon, label, value, testId }) {
  return (
    <label className="font-mono text-sm flex items-center justify-between">
      <span className="flex items-center gap-2"><Icon className="h-4 w-4" /> {label}</span>
      <span className="font-bold" data-testid={testId}>{value}</span>
    </label>
  );
}

export default function SettingsPanel({ s, set, revSeconds, numStart, onNumStart, fit }) {
  const pct = speedPct(s.duration, revSeconds);
  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="font-mono text-sm flex items-center gap-2 mb-1"><Tag className="h-4 w-4" /> Disc title (side A)</label>
        <input
          data-testid="title-input" className={INPUT} maxLength={40} value={s.title}
          placeholder="Twinkle Twinkle" onChange={(e) => set({ title: e.target.value })}
        />
      </div>

      <div>
        <label className="font-mono text-sm flex items-center justify-between">
          <span className="flex items-center gap-2"><Hash className="h-4 w-4" /> Record number</span>
          <span className="font-mono text-[10px] text-[#457B9D]">{s.recordNo === "" ? `auto → #${s.nextNo ?? "…"}` : "manual"}</span>
        </label>
        <input
          data-testid="record-no-input" type="number" min="1" max="999" className={`${INPUT} mt-1`} value={s.recordNo}
          placeholder={`auto (#${s.nextNo ?? "…"})`} onChange={(e) => set({ recordNo: e.target.value })}
        />
        <label className="font-mono text-[10px] text-[#457B9D] flex items-center justify-between gap-2 mt-1">
          <span>Auto numbering starts at</span>
          <input
            data-testid="numbering-start-input" type="number" min="1" max="999" defaultValue={numStart} key={numStart}
            onBlur={(e) => Number(e.target.value) !== numStart && onNumStart(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
            className={`${INPUT} w-20 py-0.5 text-xs`}
          />
        </label>
      </div>

      <div className="flex items-center justify-between">
        <label className="font-mono text-sm flex items-center gap-2"><Tag className="h-4 w-4" /> Engrave title on label</label>
        <Toggle checked={s.engrave} onChange={(v) => set({ engrave: v })} testId="engrave-toggle" />
      </div>

      <div className="flex items-center justify-between">
        <label className="font-mono text-sm flex items-center gap-2"><Disc3 className="h-4 w-4" /> Two-sided disc</label>
        <Toggle checked={s.twoSided} onChange={(v) => set({ twoSided: v, thickness: v ? Math.max(5, s.thickness) : s.thickness })} testId="two-sided-toggle" />
      </div>

      {s.twoSided && (
        <div className="border-2 border-[#1D3557] rounded-lg p-3 bg-[#F4F1EA] flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            {[["file", "2nd MIDI file"], ["continue", "Continue song"]].map(([v, l]) => (
              <button
                key={v} type="button" data-testid={`side-mode-${v}`}
                onClick={() => set({ sideMode: v })}
                className={`font-sans font-bold text-xs py-2 rounded-md border-2 border-[#1D3557] ${
                  s.sideMode === v ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
          <p className="font-mono text-[10px] text-[#457B9D]">
            {s.sideMode === "file"
              ? "Side B plays a different song from a second MIDI file."
              : `Side B continues the same song from ${s.duration}s to ${s.duration * 2}s.`}
          </p>
          <input
            data-testid="title-b-input" className={INPUT} maxLength={40} value={s.titleB}
            placeholder="Side B title" onChange={(e) => set({ titleB: e.target.value })}
          />
        </div>
      )}

      <div className="flex items-center justify-between">
        <label className="font-mono text-sm flex items-center gap-2"><Wand2 className="h-4 w-4" /> Auto-transpose</label>
        <Toggle checked={s.autoTranspose} onChange={(v) => set({ autoTranspose: v })} testId="transpose-toggle" />
      </div>

      {!s.autoTranspose && (
        <div>
          <Row icon={Wand2} label="Manual shift" testId="offset-value"
            value={`${s.manualOffset > 0 ? "+" : ""}${s.manualOffset} st`} />
          <input
            type="range" min="-24" max="24" step="1" value={s.manualOffset}
            data-testid="offset-slider"
            onChange={(e) => set({ manualOffset: Number(e.target.value) })}
            className="w-full mt-2 accent-[#E63946]"
          />
        </div>
      )}

      <div>
        <label className="font-mono text-sm flex items-center gap-2 mb-1"><Layers className="h-4 w-4" /> Notes at once (22 tines)</label>
        <div className="grid grid-cols-4 gap-1">
          {[[1, "ONE"], [2, "TWO"], [3, "THREE"], [16, "ALL"]].map(([v, l]) => (
            <button
              key={v} type="button" data-testid={`voices-${v}`}
              onClick={() => set({ voices: v, chords: v > 1 })}
              className={`font-sans font-bold text-xs py-2 rounded-md border-2 border-[#1D3557] ${
                (s.voices || 1) === v ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
        <p className="font-mono text-[10px] text-[#457B9D] mt-1" data-testid="voices-hint">
          {(s.voices || 1) === 1
            ? "Factory style — one tine per beat, chords are rolled."
            : (s.voices || 1) >= 16
              ? "Experimental — every note stays on its beat; dense mixes may jam the comb."
              : `Simple chords — up to ${s.voices} tines pluck together on a beat (melody kept on top, then the bass note). Extra notes roll to a nearby beat with room. Print it and listen!`}
        </p>
      </div>

      <div>
        <label className="font-mono text-sm flex items-center gap-2 mb-1"><Layers className="h-4 w-4" /> Chord roll direction</label>
        <div className="grid grid-cols-2 gap-2">
          {[["before", "LEAN BEFORE"], ["after", "LEAN AFTER"]].map(([v, l]) => (
            <button
              key={v} type="button" data-testid={`roll-${v}`}
              onClick={() => set({ roll: v })}
              className={`font-sans font-bold text-xs py-2 rounded-md border-2 border-[#1D3557] ${
                s.roll === v ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
        <p className="font-mono text-[10px] text-[#457B9D] mt-1" data-testid="roll-hint">
          {s.roll === "after"
            ? "The melody (top note) lands on the beat and the lower chord notes follow just after it — like a harp strummed downward."
            : "Lower chord notes are plucked just before the beat so the melody (top note) lands exactly on time — like the factory records."}
        </p>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <label className="font-mono text-sm flex items-center gap-2"><Target className="h-4 w-4" /> Auto-fit to the MIDI</label>
          <Toggle checked={s.autoFit} onChange={(v) => set({ autoFit: v })} testId="autofit-toggle" />
        </div>
        <p className="font-mono text-[10px] text-[#457B9D] mt-1" data-testid="autofit-hint">
          {s.autoFit
            ? "Re-maps the slice up to 12,000 ways (tempo ±35 %, start ±0.5 s), compares each disc with the MIDI and keeps the closest match."
            : "Off — the window length and start are used exactly as set below."}
        </p>
        {s.autoFit && fit && (
          <div className="mt-2 border-2 border-[#1D3557] rounded-md bg-[#2A9D8F]/15 p-2 font-mono text-[11px] text-[#1D3557]" data-testid="autofit-result">
            <span className="font-sans font-black text-sm" data-testid="autofit-score">{Math.round(fit.score)}% match</span>
            {fit.tries ? ` after ${fit.tries.toLocaleString()} tries` : ""} · {fit.matched} notes matched
            · ±{Math.round(fit.timing_ms)} ms timing · tempo ×{Number(fit.tempo).toFixed(2)}
            {fit.nudge ? ` · start nudged ${fit.nudge > 0 ? "+" : ""}${fit.nudge.toFixed(2)}s` : ""}
          </div>
        )}
      </div>

      <div>
        <Row icon={Clock} label="Window: 86 beats" value={`${Number(s.duration).toFixed(1)}s of song`} testId="duration-value" />
        <input
          type="range" min="5" max="45" step="0.1" value={s.duration}
          data-testid="duration-slider"
          onChange={(e) => set({ duration: Number(e.target.value), autoFit: false })}
          className="w-full mt-2 accent-[#457B9D]"
        />
        <div className="flex items-center justify-between gap-2 mt-1">
          <p className="font-mono text-[10px] text-[#457B9D]">
            beat = {Math.round((s.duration / 86) * 1000)} ms of song → 1 revolution ({revSeconds}s) ={" "}
            <span className={`font-bold ${pct === 100 ? "text-[#2A9D8F]" : "text-[#E63946]"}`} data-testid="window-speed">{pct}% tempo</span>
          </p>
          {pct !== 100 && (
            <button
              type="button" data-testid="match-speed-button"
              onClick={() => set({ duration: revSeconds, autoFit: false })}
              className="font-mono text-[10px] font-bold px-2 py-1 rounded border-2 border-[#1D3557] bg-[#E9C46A] hover:bg-[#2A9D8F] hover:text-white flex items-center gap-1 whitespace-nowrap"
            >
              <Gauge className="h-3 w-3" /> match toy
            </button>
          )}
        </div>
      </div>

      <div>
        <Row icon={Ruler} label="Disc thickness" value={`${s.thickness.toFixed(1)}mm`} testId="thickness-value" />
        <input
          type="range" min={s.twoSided ? "4.5" : "2"} max="7" step="0.5" value={s.thickness}
          data-testid="thickness-slider"
          onChange={(e) => set({ thickness: Number(e.target.value) })}
          className="w-full mt-2 accent-[#457B9D]"
        />
        {s.twoSided && (
          <p className="font-mono text-[10px] text-[#457B9D] mt-1">Two-sided discs need ≥ 5 mm so the top and bottom grooves don't meet (Fred's spec). You'll also get two flat-backed halves to print pins-up and glue.</p>
        )}
      </div>

      <div>
        <Row icon={Ruler} label="Pin height (triangle)" value={`${s.pinRadius.toFixed(2)}mm`} testId="pin-radius-value" />
        <input
          type="range" min="0.4" max="1.0" step="0.05" value={s.pinRadius}
          data-testid="pin-radius-slider"
          onChange={(e) => set({ pinRadius: Number(e.target.value) })}
          className="w-full mt-2 accent-[#E63946]"
        />
        <p className={`font-mono text-[10px] mt-1 ${s.pinRadius < 0.6 ? "text-[#E63946] font-bold" : "text-[#457B9D]"}`} data-testid="pin-radius-hint">
          {s.pinRadius < 0.6
            ? "Shallow pin — the tine may not be pushed far enough to ring. Originals ≈ 0.8 mm."
            : `Triangle ramp on the groove wall: 1.6 mm base buried 0.5 mm into the wall, apex pushing the tine sideways by this much. Originals ≈ 0.8 mm.`}
        </p>
      </div>

      <div>
        <Row icon={Heart} label="Dedication letters (Barbara ring)" value={`${(s.dedHeight ?? 2.4).toFixed(1)}mm`} testId="ded-height-value" />
        <input
          type="range" min="2" max="3.5" step="0.1" value={s.dedHeight ?? 2.4}
          data-testid="ded-height-slider"
          onChange={(e) => set({ dedHeight: Number(e.target.value) })}
          className="w-full mt-2 accent-[#E63946]"
        />
        <p className="font-mono text-[10px] text-[#457B9D] mt-1" data-testid="ded-height-hint">
          {(s.dedHeight ?? 2.4) < 2.5
            ? "Fine lettering — crisp with a 0.25 mm nozzle; a 0.4 mm nozzle may blur the thin strokes."
            : (s.dedHeight ?? 2.4) <= 3.0
              ? "Good match for a 0.4 mm nozzle — strokes ≈ 0.45 mm, still clear of the title arc and record number."
              : "Bold lettering — easiest to read, ring now sits 10.3–13.8 mm from the spindle (title starts at 14 mm)."}
        </p>
        <div className="grid grid-cols-3 gap-1 mt-2">
          {[["bold", "BOLD", "DejaVu Sans Bold — crispest print"], ["rounded", "ROUNDED", "Comfortaa — soft, friendly letters"], ["script", "SCRIPT", "Pacifico — handwritten dedication feel (3 mm+ recommended)"]].map(([v, l, hint]) => (
            <button
              key={v} type="button" data-testid={`ded-font-${v}`} title={hint}
              onClick={() => set({ dedFont: v })}
              className={`font-sans font-bold text-xs py-1.5 rounded-md border-2 border-[#1D3557] ${(s.dedFont || "bold") === v ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"}`}
            >
              {l}
            </button>
          ))}
        </div>
        <p className="font-mono text-[10px] text-[#457B9D] mt-1" data-testid="ded-font-hint">
          {(s.dedFont || "bold") === "script"
            ? "Pacifico script — strokes are thickened 0.08 mm so they print; use 3.0 mm+ letters. OpenSCAD needs the TTF from backend/fonts."
            : (s.dedFont || "bold") === "rounded"
              ? "Comfortaa rounded — strokes thickened 0.12 mm for the nozzle; gentle look, still easy to read."
              : "DejaVu Sans Bold — the factory-style lettering used for the title arc."}
        </p>
        {s.twoSided && (
          <label className="flex items-center justify-between mt-2 font-mono text-xs">
            <span>Dedication ring on side B too</span>
            <Toggle checked={s.dedB !== false} onChange={(v) => set({ dedB: v })} testId="ded-b-toggle" />
          </label>
        )}
      </div>
    </div>
  );
}
