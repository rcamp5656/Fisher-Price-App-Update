import React from "react";
import { Library, Plus } from "lucide-react";
import { CARD } from "../lib/fp";

const FIRST = 6;

// Every record number from #1 up — factory 1-5, then your pressings; gaps are clickable
export default function RecordShelf({ history, onGap, onOpen, current }) {
  const byNo = new Map();
  history.forEach((h) => { if (h.record_no != null && !byNo.has(h.record_no)) byNo.set(h.record_no, h); });
  // albums: discs sharing album_id, in play order; the disc after the one that is open is "next"
  const albums = new Map();
  history.forEach((h) => { if (h.album_id) { if (!albums.has(h.album_id)) albums.set(h.album_id, []); albums.get(h.album_id).push(h); } });
  albums.forEach((list) => list.sort((a, b) => (a.album_index || 0) - (b.album_index || 0)));
  const nextId = current && current.album_id
    ? (albums.get(current.album_id) || []).find((h) => h.album_index === (current.album_index || 0) + 1)?.id
    : null;
  const albumTag = (h) => (h.album_id ? `${h.album_index}/${h.album_count}` : null);
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
      {albums.size > 0 && (
        <div data-testid="shelf-albums" className="mb-4 flex flex-col gap-1 font-mono text-[11px]">
          {[...albums.values()].map((list) => (
            <div key={list[0].album_id} data-testid={`shelf-album-${list[0].album_id}`} className="flex flex-wrap items-center gap-1">
              <span className="font-sans font-black text-xs mr-1">ALBUM · {list[0].title.replace(/\s+\d+\/\d+$/, "")}</span>
              {list.map((h, i) => (
                <React.Fragment key={h.id}>
                  {i > 0 && <span className="text-[#457B9D]">→</span>}
                  <button type="button" data-testid={`shelf-album-disc-${h.id}`} onClick={() => onOpen(h)}
                    className={`px-1.5 py-0.5 rounded border ${h.id === nextId ? "border-[#E63946] bg-[#FFB703] font-bold" : current && h.id === current.id ? "border-[#2A9D8F] bg-[#2A9D8F]/20 font-bold" : "border-[#1D3557]/40 bg-white"}`}>
                    #{h.record_no} · {h.album_index}/{h.album_count}{h.id === nextId ? " · NEXT" : current && h.id === current.id ? " · PLAYING" : ""}
                  </button>
                </React.Fragment>
              ))}
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2 pt-3">
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
            const isNext = h.id === nextId;
            const isOpen = current && h.id === current.id;
            return (
              <div key={n} className="relative flex flex-col items-center gap-0.5">
                {isNext && <span data-testid={`shelf-next-${n}`} className="absolute -top-3 font-mono text-[9px] font-black text-[#E63946] whitespace-nowrap">NEXT ▶</span>}
                <button data-testid={`shelf-record-${n}`} onClick={() => onOpen(h)} title={`${h.title}${h.two_sided ? ` / ${h.title_b}` : ""}${h.album_id ? ` — album disc ${albumTag(h)}` : ""}`}
                  className={`h-14 w-14 rounded-full border-2 shadow-[2px_2px_0_0_#1D3557] hover:-translate-y-0.5 transition-transform duration-150 flex items-center justify-center relative ${
                    isNext ? "border-[#E63946] ring-4 ring-[#FFB703] bg-[#E63946]" : isOpen ? "border-[#1D3557] ring-4 ring-[#2A9D8F] bg-[#E63946]" : h.album_id ? "border-[#1D3557] bg-[#457B9D]" : "border-[#1D3557] bg-[#E63946]"
                  }`}>
                  <span className="absolute inset-[9px] rounded-full bg-[#F4F1EA] border border-[#1D3557]/30" />
                  <span className="relative font-mono font-black text-sm text-[#1D3557]">{n}</span>
                </button>
                {h.album_id && <span data-testid={`shelf-album-tag-${n}`} className="font-mono text-[9px] text-[#457B9D]">{albumTag(h)}</span>}
              </div>
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
