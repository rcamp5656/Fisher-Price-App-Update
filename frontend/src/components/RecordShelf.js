import React from "react";
import { Library, Plus } from "lucide-react";
import { CARD } from "../lib/fp";

const FIRST = 6;

// Every record number from #1 up — factory 1-5, then your pressings; gaps are clickable
export default function RecordShelf({ history, onGap, onOpen }) {
  const byNo = new Map();
  history.forEach((h) => { if (h.record_no != null && !byNo.has(h.record_no)) byNo.set(h.record_no, h); });
  const max = Math.max(FIRST + 3, ...byNo.keys());
  const slots = Array.from({ length: max }, (_, i) => i + 1);
  const gaps = slots.filter((n) => n >= FIRST && !byNo.has(n)).length;

  return (
    <div data-testid="record-shelf" className={`${CARD} p-6 col-span-12`}>
      <h3 className="font-sans font-black text-xl tracking-tight flex items-center gap-2 mb-1">
        <Library className="h-5 w-5" /> RECORD SHELF
      </h3>
      <p className="font-mono text-xs text-[#457B9D] mb-4">
        1–5 are the factory set. {byNo.size} pressed · {gaps} gap{gaps === 1 ? "" : "s"} — click a gap to press into that number.
      </p>
      <div className="flex flex-wrap gap-2">
        {slots.map((n) => {
          const h = byNo.get(n);
          if (n < FIRST) {
            return (
              <div key={n} data-testid={`shelf-factory-${n}`} className="h-14 w-14 rounded-full border-2 border-[#1D3557] bg-[#B9A9E3] flex items-center justify-center font-mono font-black text-sm text-[#1D3557]/70" title="Factory record">
                {n}
              </div>
            );
          }
          if (h) {
            return (
              <button key={n} data-testid={`shelf-record-${n}`} onClick={() => onOpen(h)} title={`${h.title}${h.two_sided ? ` / ${h.title_b}` : ""}`}
                className="h-14 w-14 rounded-full border-2 border-[#1D3557] bg-[#E63946] shadow-[2px_2px_0_0_#1D3557] hover:-translate-y-0.5 transition-transform duration-150 flex items-center justify-center relative">
                <span className="absolute inset-[9px] rounded-full bg-[#F4F1EA] border border-[#1D3557]/30" />
                <span className="relative font-mono font-black text-sm text-[#1D3557]">{n}</span>
              </button>
            );
          }
          return (
            <button key={n} data-testid={`shelf-gap-${n}`} onClick={() => onGap(n)} title={`Press record #${n}`}
              className="h-14 w-14 rounded-full border-2 border-dashed border-[#457B9D] text-[#457B9D] font-mono text-xs flex flex-col items-center justify-center hover:bg-[#E9C46A] hover:border-[#1D3557] hover:text-[#1D3557]">
              <Plus className="h-3 w-3" /> {n}
            </button>
          );
        })}
      </div>
    </div>
  );
}
