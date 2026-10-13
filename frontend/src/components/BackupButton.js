import React, { useEffect, useState } from "react";
import axios from "axios";
import { Archive, Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

const fmtMB = (b) => (b ? `${(b / 1048576).toFixed(b > 104857600 ? 0 : 1)} MB` : "");

// One click: build a ZIP of every record/album/setting in the background, then hand over the download
export default function BackupButton({ api }) {
  const [st, setSt] = useState({ status: "idle" });
  const [asked, setAsked] = useState(false);
  useEffect(() => {
    if (st.status !== "running") return undefined;
    const t = setInterval(async () => {
      try { const { data } = await axios.get(`${api}/backup`); setSt(data); } catch (e) { /* keep polling */ }
    }, 1500);
    return () => clearInterval(t);
  }, [st.status, api]);
  useEffect(() => {
    if (asked && st.status === "ready") toast.success("Backup ready", { description: `${st.total} records · ${fmtMB(st.size)} — click DOWNLOAD BACKUP` });
    if (asked && st.status === "error") toast.error("Backup failed", { description: st.error });
  }, [st.status, asked, st.total, st.size, st.error]);

  const start = async () => {
    setAsked(true);
    try { await axios.post(`${api}/backup`); setSt((p) => ({ ...p, status: "running", done: 0 })); }
    catch (e) { toast.error("Could not start the backup"); }
  };

  const base = "font-sans font-black text-xs px-3 py-1.5 rounded-md border-2 border-[#1D3557] flex items-center gap-1 shadow-[2px_2px_0_0_#1D3557]";
  if (st.status === "running") {
    return (
      <span data-testid="backup-progress" className={`${base} bg-white`}>
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> PACKING {st.done}/{st.total} RECORDS…
      </span>
    );
  }
  if (st.status === "ready" && asked) {
    return (
      <span className="flex items-center gap-2">
        <a data-testid="backup-download-link" href={`${api}/backup.zip`} className={`${base} bg-[#2A9D8F] text-white`}>
          <Download className="h-3.5 w-3.5" /> DOWNLOAD BACKUP ({fmtMB(st.size)})
        </a>
        <button type="button" data-testid="backup-refresh" onClick={start} className="font-mono text-[10px] underline text-[#457B9D]">rebuild</button>
      </span>
    );
  }
  return (
    <button type="button" data-testid="backup-start" onClick={start} title="Every record, album and setting: STL + SCAD + FPR + label + JSON — copy it somewhere safe"
      className={`${base} bg-[#E9C46A] hover:bg-[#FFB703]`}>
      <Archive className="h-3.5 w-3.5" /> BACKUP ALL RECORDS (.ZIP)
    </button>
  );
}
