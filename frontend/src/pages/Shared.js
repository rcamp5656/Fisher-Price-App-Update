import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import axios from "axios";
import { Disc3, Loader2, AlertTriangle, Wand2, ArrowLeft } from "lucide-react";
import RecordViewer from "../components/RecordViewer";
import PrintGuide from "../components/PrintGuide";
import { DownloadPanel, SpecSheet } from "../components/ResultPanels";
import { CARD, BTN_BASE, countNotes } from "../lib/fp";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Shared() {
  const { id } = useParams();
  const [record, setRecord] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${API}/conversions/${id}`)
      .then(({ data }) => setRecord(data))
      .catch(() => setError("That record doesn't exist (or was never pressed)."));
  }, [id]);

  return (
    <div className="min-h-screen bg-[#F4F1EA] text-[#1D3557] fp-grain">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 p-6 md:p-12 max-w-[1400px] mx-auto">
        <header className="col-span-12 flex flex-wrap gap-4 justify-between items-end border-b-4 border-[#1D3557] pb-6">
          <Link to="/" className="flex items-center gap-4" data-testid="share-home-link">
            <div className="h-14 w-14 rounded-full border-2 border-[#1D3557] bg-[#E63946] shadow-[3px_3px_0_0_#1D3557] flex items-center justify-center">
              <Disc3 className="h-8 w-8 text-white" />
            </div>
            <div>
              <h1 className="font-sans font-black tracking-tighter text-3xl sm:text-4xl lg:text-5xl leading-none">RECORD MAKER</h1>
              <p className="font-mono text-xs sm:text-sm text-[#457B9D] mt-1">A shared disc for the 1977 Fisher-Price Music Box Player</p>
            </div>
          </Link>
          <Link to="/" className="font-mono text-xs text-[#457B9D] flex items-center gap-1 hover:text-[#E63946]">
            <ArrowLeft className="h-3.5 w-3.5" /> make your own
          </Link>
        </header>

        {error && (
          <div data-testid="share-error" className="col-span-12 bg-[#E63946] text-white border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl p-5 font-mono text-sm flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0" /> {error}
          </div>
        )}

        {!record && !error && (
          <div className="col-span-12 flex items-center justify-center py-24 font-mono text-sm text-[#457B9D]">
            <Loader2 className="h-6 w-6 animate-spin mr-3" /> loading record…
          </div>
        )}

        {record && (
          <>
            <section data-testid="share-viewer" className="col-span-12 lg:col-span-8 border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-2xl overflow-hidden min-h-[55vh] relative bg-[#F4F1EA]">
              <RecordViewer url={`${API}/conversions/${record.id}/stl`} />
              <div className="absolute bottom-3 left-3 font-mono text-[10px] text-[#457B9D] bg-white/70 border border-[#1D3557] rounded px-2 py-1">
                drag to rotate · scroll to zoom
              </div>
            </section>
            <aside className="col-span-12 lg:col-span-4 flex flex-col gap-6">
              <div className={`${CARD} p-5`}>
                {record.record_no != null && (
                  <p className="font-mono text-xs font-bold text-[#E63946] mb-1">RECORD #{record.record_no}</p>
                )}
                <p className="font-mono text-[10px] uppercase text-[#457B9D]">Side A</p>
                <h2 data-testid="share-title" className="font-sans font-black text-2xl tracking-tight break-words">{record.title}</h2>
                {record.two_sided && (
                  <>
                    <p className="font-mono text-[10px] uppercase text-[#457B9D] mt-3">Side B</p>
                    <h2 className="font-sans font-black text-2xl tracking-tight break-words">{record.title_b}</h2>
                  </>
                )}
                <p className="font-mono text-xs text-[#457B9D] mt-3">
                  {record.pin_count} pins · {record.thickness} mm · {record.duration}s window
                  {record.partition ? ` · ${countNotes(record.partition)} notes on A` : ""}
                </p>
              </div>
              <DownloadPanel api={API} result={record} />
              <Link
                to={`/?open=${record.id}`}
                data-testid="remix-button"
                className={`${BTN_BASE} text-lg py-4 bg-[#E63946] text-white`}
              >
                <Wand2 className="h-5 w-5" /> REMIX THIS RECORD
              </Link>
            </aside>
            <SpecSheet result={record} />
            <PrintGuide defaultOpen />
          </>
        )}

        <footer className="col-span-12 font-mono text-[11px] text-[#457B9D] text-center pt-4">
          Print at 100% scale · Ø121mm · fits the vintage Fisher-Price spindle
        </footer>
      </div>
    </div>
  );
}
