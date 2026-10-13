import React, { useEffect, useRef, useState } from "react";
import BackupButton from "./BackupButton";
import { Library, Plus, Search } from "lucide-react";
import { CARD } from "../lib/fp";

const FIRST = 6;
// same 10-colour palette as the sleeve-card spines (backend _ALBUM_COLOURS), by disc index
export const ALBUM_COLOURS = ["#E63946", "#2A9D8F", "#FFB703", "#457B9D", "#8E44AD", "#F4845F", "#1D3557", "#6A994E", "#D77A61", "#5BC0BE"];
export const albumColour = (h) => ALBUM_COLOURS[((h.album_index || 1) - 1) % ALBUM_COLOURS.length];

// Every record number from #1 up — factory 1-5, then your pressings; gaps are clickable
export default function RecordShelf({ history, onGap, onOpen, current, api }) {
  const [focus, setFocus] = useState(null);   // album_id to spotlight; others dim
  const [q, setQ] = useState("");
  const firstHit = useRef(null);
  const needle = q.trim().toLowerCase();
  const hit = (h) => !!h && (!needle || String(h.record_no) === needle.replace(/^#/, "") || `${h.title} ${h.title_b || ""}`.toLowerCase().includes(needle));
  const hits = history.filter(hit).length;
  useEffect(() => { if (needle && firstHit.current) firstHit.current.scrollIntoView({ behavior: "smooth", block: "center" }); }, [needle, hits]);
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

  const firstHitNo = needle ? slots.find((n) => hit(byNo.get(n))) : null;
  return (
    <div data-testid="record-shelf" className={`${CARD} p-6 col-span-12`}>
      <div className="flex flex-wrap items-center gap-3 mb-1">
        <h3 className="font-sans font-black text-xl tracking-tight flex items-center gap-2">
          <Library className="h-5 w-5" /> RECORD SHELF
        </h3>
        <label className="flex items-center gap-1 font-mono text-xs border-2 border-[#1D3557] rounded-md px-2 py-1 bg-white">
          <Search className="h-3.5 w-3.5" />
          <input
            data-testid="shelf-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="title or #number"
            onKeyDown={(e) => { if (e.key === "Enter") { const h = history.find(hit); if (h) onOpen(h); } if (e.key === "Escape") setQ(""); }}
            className="bg-transparent outline-none w-40"
          />
          {needle && <span data-testid="shelf-search-count" className={`font-bold ${hits ? "text-[#2A9D8F]" : "text-[#E63946]"}`}>{hits} hit{hits === 1 ? "" : "s"}</span>}
        </label>
        {api && <span className="ml-auto"><BackupButton api={api} /></span>}
      </div>
      <p className="font-mono text-xs text-[#457B9D] mb-4">
        1–5 are the factory set. {byNo.size} pressed · {gaps} gap{gaps === 1 ? "" : "s"} — click a gap to press into that number.
      </p>
      {albums.size > 0 && (
        <div data-testid="shelf-albums" className="mb-4 flex flex-col gap-1 font-mono text-[11px]">
          {[...albums.values()].map((list) => (
            <div key={list[0].album_id} data-testid={`shelf-album-${list[0].album_id}`} className="flex flex-wrap items-center gap-1">
              <button type="button" data-testid={`shelf-album-name-${list[0].album_id}`}
                onClick={() => setFocus(focus === list[0].album_id ? null : list[0].album_id)}
                title={focus === list[0].album_id ? "Show every record again" : "Spotlight this album on the shelf"}
                className={`font-sans font-black text-xs mr-1 px-1.5 py-0.5 rounded border-2 ${focus === list[0].album_id ? "border-[#1D3557] bg-[#1D3557] text-white" : "border-transparent hover:border-[#1D3557] hover:bg-[#E9C46A]"}`}>
                ALBUM · {list[0].title.replace(/\s+\d+\/\d+$/, "")}{focus === list[0].album_id ? " ✕" : ""}
              </button>
              {list.map((h, i) => (
                <React.Fragment key={h.id}>
                  {i > 0 && <span className="text-[#457B9D]">→</span>}
                  <button type="button" data-testid={`shelf-album-disc-${h.id}`} onClick={() => onOpen(h)}
                    style={{ borderLeftColor: albumColour(h), borderLeftWidth: 5 }}
                    className={`px-1.5 py-0.5 rounded border ${h.id === nextId ? "border-[#E63946] bg-[#FFB703] font-bold" : current && h.id === current.id ? "border-[#2A9D8F] bg-[#2A9D8F]/20 font-bold" : "border-[#1D3557]/40 bg-white"}`}>
                    #{h.record_no} · {h.album_index}/{h.album_count}{h.id === nextId ? " · NEXT" : current && h.id === current.id ? " · PLAYING" : ""}
                  </button>
                </React.Fragment>
              ))}
            </div>
          ))}
        </div>
      )}
      {focus && (
        <p data-testid="shelf-focus-note" className="font-mono text-[11px] text-[#1D3557] -mt-2 mb-2">
          Spotlight: only this album's discs are lit — tap the album name again to show everything.
        </p>
      )}
      <div className="flex flex-wrap gap-2 pt-3">
        {slots.map((n) => {
          const h = byNo.get(n);
          const lit = (!focus || (h && h.album_id === focus)) && (!needle || hit(h));
          const dim = lit ? "" : "opacity-20 grayscale";
          const isHit = needle && hit(h);
          if (n < FIRST) {
            return (
              <div key={n} data-testid={`shelf-factory-${n}`} className={`h-14 w-14 rounded-full border-2 border-[#1D3557] bg-[#B9A9E3] ${dim} flex items-center justify-center font-mono font-black text-sm text-[#1D3557]/70`} title="Factory record">
                {n}
              </div>
            );
          }
          if (h) {
            const isNext = h.id === nextId;
            const isOpen = current && h.id === current.id;
            return (
              <div key={n} ref={n === firstHitNo ? firstHit : null} className={`relative flex flex-col items-center gap-0.5 transition-opacity duration-300 ${dim} ${isHit ? "scale-110" : ""}`}>
                {isNext && <span data-testid={`shelf-next-${n}`} className="absolute -top-3 font-mono text-[9px] font-black text-[#E63946] whitespace-nowrap">NEXT ▶</span>}
                <button data-testid={`shelf-record-${n}`} onClick={() => onOpen(h)} title={`${h.title}${h.two_sided ? ` / ${h.title_b}` : ""}${h.album_id ? ` — album disc ${albumTag(h)}` : ""}`}
                  style={h.album_id && !isNext && !isOpen ? { backgroundColor: albumColour(h) } : undefined}
                  className={`h-14 w-14 rounded-full border-2 shadow-[2px_2px_0_0_#1D3557] hover:-translate-y-0.5 transition-transform duration-150 flex items-center justify-center relative ${
                    isNext ? "border-[#E63946] ring-4 ring-[#FFB703] bg-[#E63946]" : isOpen ? "border-[#1D3557] ring-4 ring-[#2A9D8F] bg-[#E63946]" : h.album_id ? "border-[#1D3557]" : "border-[#1D3557] bg-[#E63946]"
                  }`}>
                  <span className="absolute inset-[9px] rounded-full bg-[#F4F1EA] border border-[#1D3557]/30" />
                  <span className="relative font-mono font-black text-sm text-[#1D3557]">{n}</span>
                </button>
                {h.album_id && <span data-testid={`shelf-album-tag-${n}`} style={{ color: albumColour(h) }} className="font-mono text-[9px] font-black">{albumTag(h)}</span>}
              </div>
            );
          }
          return (
            <button key={n} data-testid={`shelf-gap-${n}`} onClick={() => onGap(n)} title={`Press record #${n}`}
              className={`${dim} h-14 w-14 rounded-full border-2 border-dashed border-[#457B9D] text-[#457B9D] font-mono text-xs flex flex-col items-center justify-center hover:bg-[#E9C46A] hover:border-[#1D3557] hover:text-[#1D3557]`}>
              <Plus className="h-3 w-3" /> {n}
            </button>
          );
        })}
      </div>
    </div>
  );
}
