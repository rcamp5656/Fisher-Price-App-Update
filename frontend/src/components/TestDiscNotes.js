import React, { useEffect, useState } from "react";
import axios from "axios";
import { ClipboardCheck, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { INPUT } from "../lib/fp";

const OPTIONS = [[1, "ONE", "single notes only"], [2, "TWO", "two-note chords"], [3, "THREE", "triads"]];
const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "");

// After printing the chord test disc: note which section the comb played cleanly → default "notes at once"
export default function TestDiscNotes({ api, saved, onSaved }) {
  const [voices, setVoices] = useState(saved?.voices || null);
  const [note, setNote] = useState(saved?.note || "");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (saved) { setVoices(saved.voices || null); setNote(saved.note || ""); } }, [saved]);

  const save = async () => {
    if (!voices) return;
    setBusy(true);
    try {
      const { data } = await axios.put(`${api}/defaults`, { voices, note });
      onSaved(data);
      toast.success(`Default set: ${OPTIONS.find(([v]) => v === data.voices)?.[1] || data.voices} note(s) at once`, { description: "Every new record starts with this setting." });
    } catch (e) {
      toast.error("Could not save the test result");
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="test-disc-notes" className="border-2 border-dashed border-[#1D3557]/50 rounded-lg p-2 flex flex-col gap-2 font-mono text-[11px] text-[#1D3557]">
      <div className="flex items-center gap-1 font-sans font-black text-xs"><ClipboardCheck className="h-3.5 w-3.5" /> AFTER PRINTING — which section played cleanly?</div>
      <div className="grid grid-cols-3 gap-1">
        {OPTIONS.map(([v, l, hint]) => (
          <button
            key={v} type="button" data-testid={`test-result-${v}`} onClick={() => setVoices(v)} title={hint}
            className={`font-sans font-bold text-xs py-1.5 rounded-md border-2 border-[#1D3557] ${voices === v ? "bg-[#1D3557] text-white" : "bg-white hover:bg-[#E9C46A]"}`}
          >
            {l}
          </button>
        ))}
      </div>
      <textarea
        data-testid="test-result-note" value={note} onChange={(e) => setNote(e.target.value.slice(0, 400))} rows={2}
        placeholder="e.g. beats 30-40 (two notes) rang clean, triads at 58-68 buzzed on the low tines"
        className={`${INPUT} text-xs py-1 resize-none`}
      />
      <button
        type="button" data-testid="test-result-save" disabled={!voices || busy} onClick={save}
        className={`font-sans font-black text-xs py-1.5 rounded-md border-2 border-[#1D3557] flex items-center justify-center gap-1 ${!voices || busy ? "bg-[#E9C46A]/50 text-[#1D3557]/50" : "bg-[#2A9D8F] text-white"}`}
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} SAVE AS DEFAULT “NOTES AT ONCE”
      </button>
      {saved?.voices && (
        <p data-testid="test-result-saved" className="text-[#457B9D]">
          Default: <b>{OPTIONS.find(([v]) => v === saved.voices)?.[1] || saved.voices}</b> at once · saved {fmt(saved.tested_at)}{saved.note ? ` · “${saved.note}”` : ""}
        </p>
      )}
    </div>
  );
}
