import React, { useEffect, useRef, useState } from "react";
import { Play, Square, Sparkles, Layers3, Drum } from "lucide-react";
import { midiToFreq } from "../lib/fp";
import { pluck, newCtx } from "../hooks/useMusicBox";

const NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];
const nn = (m) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;

// tiny piano-roll of one track across the whole song
function Strip({ track, total, selected }) {
  const lo = track.low, hi = Math.max(track.high, lo + 1);
  return (
    <svg viewBox="0 0 300 24" preserveAspectRatio="none" className={`w-full h-6 rounded border border-[#1D3557]/30 ${selected ? "bg-white" : "bg-[#F4F1EA]"}`} data-testid={`track-strip-${track.index}`}>
      {track.strip.map(([t, n], i) => (
        <rect key={i} x={(t / Math.max(total, 1)) * 300} y={22 - ((n - lo) / (hi - lo)) * 20} width="1.2" height="2" fill={selected ? "#E63946" : "#457B9D"} />
      ))}
    </svg>
  );
}

export default function TrackPicker({ scan, tracks, onTracks, skyline, onSkyline }) {
  const ctxRef = useRef(null);
  const [playingIdx, setPlayingIdx] = useState(null);
  const stop = () => { if (ctxRef.current) ctxRef.current.close(); ctxRef.current = null; setPlayingIdx(null); };
  useEffect(() => stop, []);
  if (!scan || !scan.tracks || scan.tracks.length < 2) return null;

  const all = scan.tracks.filter((t) => !t.drums).map((t) => t.index);
  const sel = new Set(tracks && tracks.length ? tracks : all);
  const toggle = (idx) => {
    const next = new Set(sel);
    if (next.has(idx)) next.delete(idx); else next.add(idx);
    onTracks([...next].sort((a, b) => a - b));
  };
  // 12 s of the track from its first note, at real tempo
  const audition = (track) => {
    if (playingIdx === track.index) { stop(); return; }
    stop();
    const ctx = newCtx();
    ctxRef.current = ctx;
    const t0 = ctx.currentTime + 0.05;
    const from = track.first;
    scan.events.filter(([t, , ti]) => ti === track.index && t >= from && t < from + 12)
      .forEach(([t, n]) => pluck(ctx, ctx.destination, midiToFreq(n), t0 + (t - from)));
    setPlayingIdx(track.index);
    setTimeout(() => { if (ctxRef.current === ctx) stop(); }, 13000);
  };

  return (
    <div data-testid="track-picker" className="border-2 border-[#1D3557] rounded-lg bg-[#F4F1EA] p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-sans font-black text-sm flex items-center gap-1"><Layers3 className="h-4 w-4" /> TRACKS · {sel.size}/{all.length} used</span>
        <button
          type="button" data-testid="track-auto-melody" onClick={() => onTracks(scan.suggested != null ? [scan.suggested] : all)}
          className="font-mono text-[10px] font-bold px-2 py-1 rounded border-2 border-[#1D3557] bg-[#E9C46A] hover:bg-[#2A9D8F] hover:text-white flex items-center gap-1"
        >
          <Sparkles className="h-3 w-3" /> melody only
        </button>
      </div>
      <p className="font-mono text-[10px] text-[#457B9D]">
        A full band arrangement can't fit 16 tines — pick the line that carries the tune. ★ = most melody-like. Drums have no tine on the toy and are skipped.
      </p>
      <div className="flex flex-col gap-1 max-h-72 overflow-y-auto pr-1">
        {scan.tracks.map((t) => {
          const on = !t.drums && sel.has(t.index);
          return (
            <div key={t.index} data-testid={`track-row-${t.index}`} className={`rounded-md border-2 p-1.5 flex flex-col gap-1 ${on ? "border-[#1D3557] bg-white" : "border-[#1D3557]/20 bg-[#F4F1EA]"} ${t.drums ? "opacity-60" : ""}`}>
              <div className="flex items-center gap-2 font-mono text-[11px]">
                <input
                  type="checkbox" data-testid={`track-check-${t.index}`} checked={on} disabled={t.drums}
                  onChange={() => toggle(t.index)} className="accent-[#E63946] h-4 w-4 shrink-0"
                />
                <span className="font-bold text-[#1D3557] truncate flex items-center gap-1">
                  {t.drums && <Drum className="h-3 w-3" />}
                  {t.index === scan.suggested && <span title="most melody-like" className="text-[#E63946]">★</span>}
                  {t.instrument}{t.name ? ` · ${t.name}` : ""}
                </span>
                <span className="ml-auto text-[#457B9D] whitespace-nowrap">{t.notes} notes · {nn(t.low)}–{nn(t.high)}</span>
                {!t.drums && (
                  <button
                    type="button" data-testid={`track-play-${t.index}`} onClick={() => audition(t)}
                    className={`h-6 w-6 shrink-0 rounded border-2 border-[#1D3557] flex items-center justify-center ${playingIdx === t.index ? "bg-[#1D3557] text-white" : "bg-[#2A9D8F] text-white"}`}
                    title="Hear 12 s of this track alone"
                  >
                    {playingIdx === t.index ? <Square className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                  </button>
                )}
              </div>
              <Strip track={t} total={scan.total} selected={on} />
            </div>
          );
        })}
      </div>
      <label className="flex items-center gap-2 font-mono text-[11px] cursor-pointer">
        <input type="checkbox" data-testid="skyline-check" checked={!!skyline} onChange={(e) => onSkyline(e.target.checked)} className="accent-[#E63946] h-4 w-4" />
        Skyline — keep only the top note of chords (good for piano / guitar tracks)
      </label>
    </div>
  );
}
