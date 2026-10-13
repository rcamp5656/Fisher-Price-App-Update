import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Settings2, Save, RotateCcw } from "lucide-react";
import { COMB_TRACKS, COMB_FACTORY, noteName, noteToMidi, applyComb, INPUT, BTN_LIFT } from "../lib/fp";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Enter your own 22 tuner readings (track 1 = innermost tine, low -> high)
export default function CombEditor({ onChanged }) {
  const [open, setOpen] = useState(false);
  const [names, setNames] = useState(() => COMB_TRACKS.map(noteName));
  const [busy, setBusy] = useState(false);

  const save = async () => {
    const midis = names.map(noteToMidi);
    const bad = midis.findIndex((m) => m == null);
    if (bad >= 0) { toast.error(`Tine ${bad + 1}: "${names[bad]}" is not a note name (use e.g. G#5)`); return; }
    setBusy(true);
    try {
      const { data } = await axios.put(`${API}/comb`, { tracks: midis });
      applyComb(data); onChanged(data);
      toast.success("Comb saved", { description: `${data.notes.length} unique pitches on 22 tines` });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save comb");
    } finally { setBusy(false); }
  };

  const reset = async () => {
    setBusy(true);
    const { data } = await axios.delete(`${API}/comb`);
    applyComb(data); onChanged(data); setNames(data.tracks.map(noteName));
    setBusy(false);
    toast.success("Factory comb restored");
  };

  return (
    <div>
      <button
        type="button" data-testid="comb-toggle" onClick={() => setOpen(!open)}
        className="w-full font-mono text-xs py-1.5 rounded-md border-2 border-[#1D3557] bg-white hover:bg-[#E9C46A] flex items-center justify-center gap-2"
      >
        <Settings2 className="h-3.5 w-3.5" /> Comb: {COMB_FACTORY ? "factory (22 tines, 16 pitches)" : "custom"} {open ? "▲" : "▼"}
      </button>
      {open && (
        <div data-testid="comb-editor" className="mt-2 border-2 border-[#1D3557] rounded-lg bg-[#F4F1EA] p-3">
          <p className="font-mono text-[10px] text-[#457B9D] mb-2">
            Tuner reading of each tine, 1 = innermost track, low → high. Repeat a note for twin tines. Written in Fred's notation (sounding pitch may be a 3rd lower).
          </p>
          <div className="grid grid-cols-4 gap-1">
            {names.map((n, i) => (
              <label key={i} className="flex items-center gap-1 font-mono text-[10px]">
                <span className="w-5 text-right text-[#457B9D]">{i + 1}</span>
                <input
                  data-testid={`comb-tine-${i + 1}`} value={n}
                  onChange={(e) => setNames(names.map((x, j) => (j === i ? e.target.value : x)))}
                  className={`${INPUT} w-full px-1 py-0.5 text-[11px]`}
                />
              </label>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <button type="button" data-testid="comb-save" disabled={busy} onClick={save}
              className={`flex-1 font-sans font-bold text-xs py-2 rounded-md border-2 border-[#1D3557] bg-[#2A9D8F] text-white flex items-center justify-center gap-1 shadow-[2px_2px_0_0_#1D3557] ${BTN_LIFT}`}>
              <Save className="h-3.5 w-3.5" /> SAVE COMB
            </button>
            <button type="button" data-testid="comb-reset" disabled={busy} onClick={reset}
              className={`font-sans font-bold text-xs px-3 py-2 rounded-md border-2 border-[#1D3557] bg-white flex items-center gap-1 shadow-[2px_2px_0_0_#1D3557] ${BTN_LIFT}`}>
              <RotateCcw className="h-3.5 w-3.5" /> Factory
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
