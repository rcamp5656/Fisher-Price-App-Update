import React from "react";
import { Download, FileCode, FileText, CheckCircle2, AlertTriangle, History, RotateCcw, Share2, Package, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { BTN_BASE, BTN_LIFT, CARD } from "../lib/fp";

const SMALL = `font-sans font-bold text-sm tracking-tight rounded-xl border-2 border-[#1D3557] py-3 flex items-center justify-center gap-2 bg-white text-[#1D3557] shadow-[3px_3px_0_0_#1D3557] ${BTN_LIFT}`;

async function copyShareLink(id) {
  const url = `${window.location.origin}/r/${id}`;
  try {
    await navigator.clipboard.writeText(url);
    toast.success("Share link copied", { description: url });
  } catch (e) {
    toast.info("Copy this share link", { description: url, duration: 8000 });
    window.prompt("Copy this link:", url);
  }
}

export function DownloadPanel({ api, result }) {
  const base = `${api}/conversions/${result.id}`;
  return (
    <div className="flex flex-col gap-3">
      <p className="font-mono text-xs text-[#457B9D]">4 · DOWNLOAD & SHARE</p>
      {!result.two_sided && (
        <a data-testid="download-stl-button" href={`${base}/stl`} className={`${BTN_BASE} text-lg py-4 bg-[#2A9D8F] text-white`}>
          <Download className="h-5 w-5" /> .STL (3D PRINT)
        </a>
      )}
      {result.two_sided && (
        <div className="border-2 border-[#1D3557] rounded-xl p-3 bg-[#2A9D8F]/15 flex flex-col gap-2">
          <p className="font-mono text-[10px] text-[#1D3557] font-bold">TWO-SIDED = TWO FLAT HALVES. Print each half pins-up with NO supports, then glue the flat backs together — the spindle hole + 4 drive holes line them up.</p>
          <div className="grid grid-cols-2 gap-2">
            <a data-testid="download-half-a-button" href={`${base}/stl?part=half-a`} className={`${BTN_BASE} text-base py-3 bg-[#2A9D8F] text-white`}>
              <Download className="h-5 w-5" /> HALF A .STL
            </a>
            <a data-testid="download-half-b-button" href={`${base}/stl?part=half-b`} className={`${BTN_BASE} text-base py-3 bg-[#2A9D8F] text-white`}>
              <Download className="h-5 w-5" /> HALF B .STL
            </a>
          </div>
          <a data-testid="download-stl-button" href={`${base}/stl`} className="font-mono text-[10px] text-[#457B9D] underline text-center" title="One solid disc with pins on both faces — the underside grooves and pins need supports">
            full one-piece disc .stl (needs supports — not recommended)
          </a>
        </div>
      )}
      <div className={`grid gap-3 ${result.two_sided ? "grid-cols-3" : "grid-cols-2"}`}>
        <a data-testid="download-scad-button" href={`${base}/scad`} className={SMALL}>
          <FileCode className="h-4 w-4" /> .SCAD
        </a>
        <a data-testid="download-fpr-button" href={`${base}/fpr`} className={SMALL}>
          <FileText className="h-4 w-4" /> {result.two_sided ? ".FPR A" : ".FPR"}
        </a>
        {result.two_sided && (
          <a data-testid="download-fpr-b-button" href={`${base}/fpr?side=b`} className={SMALL}>
            <FileText className="h-4 w-4" /> .FPR B
          </a>
        )}
      </div>
      <a data-testid="download-pack-button" href={`${base}/pack`} className={`${SMALL} bg-[#1D3557] text-white`.replace("bg-white text-[#1D3557]", "")}>
        <Package className="h-4 w-4" /> PRINT PACK (.ZIP — STL + SCAD + FPR + LABEL CARD)
      </a>
      <button
        type="button"
        data-testid="share-link-button"
        onClick={() => copyShareLink(result.id)}
        className={`${SMALL.replace("bg-white", "bg-[#FFB703]")}`}
      >
        <Share2 className="h-4 w-4" /> COPY SHARE LINK
      </button>
    </div>
  );
}

function NoteBadge({ name }) {
  return (
    <span className="inline-block px-2 py-0.5 text-xs font-mono font-bold border-2 border-[#1D3557] rounded-md bg-[#E9C46A] text-[#1D3557]">
      {name}
    </span>
  );
}

export function MeshCheck({ check }) {
  if (!check) return null;
  const fixes = [
    [check.holes_filled, "hole triangle(s) filled"],
    [check.flipped_faces_fixed, "mismatched triangle(s) re-wound"],
    [check.duplicate_faces_removed, "duplicate triangle(s) removed"],
    [check.degenerate_faces_removed, "zero-area triangle(s) removed"],
  ].filter(([n]) => n > 0);
  return (
    <div data-testid="mesh-check" className={`mt-4 border-2 border-[#1D3557] rounded-lg p-3 font-mono text-xs ${check.ok ? "bg-[#2A9D8F]/15" : "bg-[#FFB703]"}`}>
      <div className="flex items-center gap-2 font-sans font-black text-sm">
        {check.ok ? <ShieldCheck className="h-4 w-4 text-[#2A9D8F]" /> : <AlertTriangle className="h-4 w-4 text-[#E63946]" />}
        MESH CHECK — {check.ok ? "PRINT READY" : "NEEDS ATTENTION"}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
        <span data-testid="mesh-watertight">{check.watertight ? "✓" : "✗"} watertight</span>
        <span data-testid="mesh-winding">{check.winding_consistent ? "✓" : "✗"} consistent triangle winding</span>
        <span data-testid="mesh-open-edges">{check.open_edges_after === 0 ? "✓" : "✗"} {check.open_edges_after} open edge(s)</span>
        <span>{check.bodies} solid body{check.bodies === 1 ? "" : "ies"}</span>
        {check.volume_mm3 != null && <span>{(check.volume_mm3 / 1000).toFixed(1)} cm³</span>}
        {check.halves_ok != null && <span>{check.halves_ok ? "✓" : "✗"} half discs</span>}
      </div>
      <div className="mt-1 text-[#457B9D]" data-testid="mesh-fixes">
        {fixes.length ? `Repaired before export: ${fixes.map(([n, l]) => `${n} ${l}`).join(" · ")}` : "No repairs were needed — the mesh came out clean."}
      </div>
    </div>
  );
}

export function SpecSheet({ result }) {
  const cells = [
    ["Record #", result.record_no ?? "—"],
    ["Pins placed", result.pin_count],
    ["Staggered", result.toy_fixes ?? 0],
    ["On-pitch", result.exact],
    ["Snapped", result.adjusted],
    ["Merged", result.merged ?? 0],
    ["Transpose", `${result.offset >= 0 ? "+" : ""}${result.offset} st`],
    ["Window", `${result.duration}s`],
    ["Thickness", `${result.thickness}mm`],
    ["Sides", result.two_sided ? "A + B" : "A only"],
    ["Triangles", result.triangles.toLocaleString()],
    ["Diameter", "121mm"],
  ];
  return (
    <div data-testid="result-panel" className="col-span-12 grid grid-cols-1 md:grid-cols-12 gap-6">
      <div className={`${CARD} p-6 md:col-span-7`}>
        <h3 className="font-sans font-black text-xl tracking-tight flex items-center gap-2 mb-4">
          <CheckCircle2 className="h-5 w-5 text-[#2A9D8F]" />
          {result.record_no != null && (
            <span data-testid="record-number" className="font-mono text-sm bg-[#1D3557] text-white rounded px-2 py-0.5">#{result.record_no}</span>
          )}
          SPEC SHEET — {result.title}
          {result.two_sided && <span className="font-mono text-sm text-[#457B9D]">/ {result.title_b}</span>}
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-sm">
          {cells.map(([k, v]) => (
            <div key={k} className="border-2 border-[#1D3557] rounded-lg p-2 bg-[#F4F1EA]">
              <div className="text-[10px] uppercase text-[#457B9D]">{k}</div>
              <div className="font-black text-lg text-[#1D3557]">{v}</div>
            </div>
          ))}
        </div>
        <MeshCheck check={result.mesh_check} />
      </div>
      <div className="md:col-span-5 bg-[#FFB703] border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl p-6 font-mono text-sm">
        <h3 className="font-sans font-black text-lg tracking-tight mb-3">PITCHES USED (22-TINE COMB)</h3>
        <div className="flex flex-wrap gap-2 mb-3">
          {result.notes_used.map((n) => <NoteBadge key={n.midi} name={n.name} />)}
        </div>
        {result.adjusted > 0 ? (
          <p className="flex items-start gap-2"><AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            {result.adjusted} note(s) were off the music box scale and snapped to the nearest playable tine.</p>
        ) : (
          <p className="flex items-start gap-2"><CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
            Every note landed exactly on a playable tine. Perfect fit!</p>
        )}
      </div>
    </div>
  );
}

export function HistoryPanel({ api, history, onPreview }) {
  if (!history.length) return null;
  return (
    <div className={`${CARD} p-6 col-span-12`}>
      <h3 className="font-sans font-black text-xl tracking-tight flex items-center gap-2 mb-4">
        <History className="h-5 w-5" /> RECENT PRESSINGS
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {history.map((h) => (
          <div key={h.id} data-testid={`history-item-${h.id}`} className="border-2 border-[#1D3557] rounded-lg p-3 bg-[#F4F1EA] flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="font-mono font-bold truncate">
                {h.record_no != null && <span className="text-[#457B9D]">#{h.record_no} </span>}
                {h.title}{h.two_sided ? ` / ${h.title_b}` : ""}
              </div>
              <div className="font-mono text-[11px] text-[#457B9D]">
                {h.pin_count} pins · {h.thickness}mm{h.two_sided ? " · 2-sided" : ""}
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <button
                title="Open" data-testid={`history-preview-${h.id}`} onClick={() => onPreview(h)}
                className="h-9 w-9 flex items-center justify-center rounded-md border-2 border-[#1D3557] bg-white hover:bg-[#E9C46A] transition-colors duration-150"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
              <a
                title="Download STL" href={`${api}/conversions/${h.id}/stl`}
                className="h-9 w-9 flex items-center justify-center rounded-md border-2 border-[#1D3557] bg-[#2A9D8F] text-white hover:brightness-110 transition-[filter] duration-150"
              >
                <Download className="h-4 w-4" />
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
