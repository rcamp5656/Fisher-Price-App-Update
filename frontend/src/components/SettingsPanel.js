import React from "react";
import { Wand2, Ruler, Clock, Tag, Disc3, Gauge, Hash } from "lucide-react";
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

export default function SettingsPanel({ s, set, revSeconds }) {
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
        <Row icon={Clock} label="Capture window" value={`${s.duration}s`} testId="duration-value" />
        <input
          type="range" min="5" max="45" step="1" value={s.duration}
          data-testid="duration-slider"
          onChange={(e) => set({ duration: Number(e.target.value) })}
          className="w-full mt-2 accent-[#457B9D]"
        />
        <div className="flex items-center justify-between gap-2 mt-1">
          <p className="font-mono text-[10px] text-[#457B9D]">
            {s.duration}s of song → 1 revolution ({revSeconds}s) ={" "}
            <span className={`font-bold ${pct === 100 ? "text-[#2A9D8F]" : "text-[#E63946]"}`} data-testid="window-speed">{pct}% tempo</span>
          </p>
          {pct !== 100 && (
            <button
              type="button" data-testid="match-speed-button"
              onClick={() => set({ duration: revSeconds })}
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
          <p className="font-mono text-[10px] text-[#457B9D] mt-1">Two-sided discs need ≥ 5 mm so the top and bottom grooves don't meet (Fred's spec).</p>
        )}
      </div>
    </div>
  );
}
