import React, { useEffect, useState } from "react";
import axios from "axios";
import { Library, Loader2, Music2 } from "lucide-react";
import { BTN_LIFT } from "../lib/fp";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// The ten factory nursery rhymes, ready to press
export default function LibraryPicker({ duration, onPick }) {
  const [open, setOpen] = useState(false);
  const [tunes, setTunes] = useState(null);

  useEffect(() => {
    if (!open) return;
    setTunes(null);
    axios.get(`${API}/library`, { params: { duration } }).then(({ data }) => setTunes(data)).catch(() => setTunes([]));
  }, [open, duration]);

  return (
    <div>
      <button
        type="button" data-testid="library-toggle" onClick={() => setOpen(!open)}
        className={`w-full font-sans font-bold text-sm py-2 rounded-lg border-2 border-[#1D3557] bg-[#FFB703] flex items-center justify-center gap-2 shadow-[3px_3px_0_0_#1D3557] ${BTN_LIFT}`}
      >
        <Library className="h-4 w-4" /> {open ? "HIDE" : "OR PICK A"} FACTORY TUNE
      </button>
      {open && (
        <div data-testid="library-list" className="mt-2 border-2 border-[#1D3557] rounded-lg bg-[#F4F1EA] p-2 flex flex-col gap-1 max-h-64 overflow-y-auto">
          {!tunes && <Loader2 className="h-4 w-4 animate-spin mx-auto my-2" />}
          {tunes && tunes.map((t) => (
            <button
              key={t.title} type="button" data-testid={`library-${t.title.replace(/\W+/g, "-").toLowerCase()}`}
              onClick={() => { onPick(t); setOpen(false); }}
              className="text-left font-mono text-xs px-2 py-1.5 rounded border-2 border-transparent hover:border-[#1D3557] hover:bg-white flex items-center gap-2"
            >
              <Music2 className="h-3 w-3 shrink-0 text-[#E63946]" />
              <span className="font-bold flex-1">{t.title}</span>
              <span className="text-[#457B9D]">{t.analysis.note_count} notes</span>
            </button>
          ))}
          <p className="font-mono text-[9px] text-[#457B9D] px-2 pt-1">Transcribed by ear from the 1971–77 record set — tweak in the editor if a note is off.</p>
        </div>
      )}
    </div>
  );
}
