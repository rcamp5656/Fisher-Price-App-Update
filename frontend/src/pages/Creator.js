import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  UploadCloud, Download, Disc3, Music4, Wand2, Ruler, Clock,
  AlertTriangle, CheckCircle2, Loader2, History, FileMusic, RotateCcw,
  FileCode, FileText,
} from "lucide-react";
import RecordViewer from "../components/RecordViewer";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CARD = "bg-white border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl";

function Toggle({ checked, onChange, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={() => onChange(!checked)}
      className={`relative h-8 w-14 rounded-full border-2 border-[#1D3557] transition-colors duration-150 ${
        checked ? "bg-[#2A9D8F]" : "bg-[#E9C46A]"
      }`}
    >
      <span
        className={`absolute top-[2px] h-6 w-6 rounded-full border-2 border-[#1D3557] bg-white transition-transform duration-150 ${
          checked ? "translate-x-6" : "translate-x-[2px]"
        }`}
      />
    </button>
  );
}

function NoteBadge({ name }) {
  return (
    <span className="inline-block px-2 py-0.5 text-xs font-mono font-bold border-2 border-[#1D3557] rounded-md bg-[#E9C46A] text-[#1D3557]">
      {name}
    </span>
  );
}

export default function Creator() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [converting, setConverting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  const [thickness, setThickness] = useState(3.0);
  const [duration, setDuration] = useState(25);
  const [autoTranspose, setAutoTranspose] = useState(true);
  const [manualOffset, setManualOffset] = useState(0);
  const inputRef = useRef(null);

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/conversions`);
      setHistory(data);
    } catch (e) {
      /* ignore */
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const pickFile = (f) => {
    if (!f) return;
    if (!/\.(mid|midi)$/i.test(f.name)) {
      setError("That is not a MIDI file. Please choose a .mid or .midi file.");
      return;
    }
    setError(null);
    setFile(f);
  };

  const onConvert = async () => {
    if (!file) return;
    setConverting(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("duration", String(duration));
    form.append("thickness", String(thickness));
    form.append("auto_transpose", String(autoTranspose));
    form.append("manual_offset", String(manualOffset));
    try {
      const { data } = await axios.post(`${API}/convert`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
      loadHistory();
    } catch (e) {
      setError(e?.response?.data?.detail || "Conversion failed. Try another MIDI file.");
    } finally {
      setConverting(false);
    }
  };

  const stlUrl = result ? `${API}/conversions/${result.id}/stl` : null;
  const scadUrl = result ? `${API}/conversions/${result.id}/scad` : null;
  const fprUrl = result ? `${API}/conversions/${result.id}/fpr` : null;

  return (
    <div className="min-h-screen bg-[#F4F1EA] text-[#1D3557] fp-grain">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 p-6 md:p-12 max-w-[1400px] mx-auto">
        {/* Header */}
        <header className="col-span-12 flex flex-wrap gap-4 justify-between items-end border-b-4 border-[#1D3557] pb-6">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-full border-2 border-[#1D3557] bg-[#E63946] shadow-[3px_3px_0_0_#1D3557] flex items-center justify-center">
              <Disc3 className="h-8 w-8 text-white" />
            </div>
            <div>
              <h1 className="font-sans font-black tracking-tighter text-3xl sm:text-4xl lg:text-5xl leading-none">
                RECORD MAKER
              </h1>
              <p className="font-mono text-xs sm:text-sm text-[#457B9D] mt-1">
                MIDI → 3D-printable disc for the 1977 Fisher-Price Music Box Player
              </p>
            </div>
          </div>
          <div className="font-mono text-xs text-[#457B9D] hidden sm:block">
            v2 · 16 tines · 86 beats / rev
          </div>
        </header>

        {/* 3D Viewer */}
        <section
          data-testid="viewer-panel"
          className="col-span-12 lg:col-span-8 border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-2xl overflow-hidden min-h-[55vh] relative bg-[#F4F1EA]"
        >
          {stlUrl ? (
            <RecordViewer url={stlUrl} />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8">
              <img
                src="https://images.unsplash.com/photo-1485726696757-76885c99f0f5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1Mjh8MHwxfHNlYXJjaHwyfHx2aW50YWdlJTIwcmVjb3JkJTIwcGxheWVyfGVufDB8fHx8MTc5MTg1Njk5Nnww&ixlib=rb-4.1.0&q=85"
                alt="vintage record player"
                className="absolute inset-0 w-full h-full object-cover opacity-20 mix-blend-multiply"
              />
              <div className="relative z-10">
                <Disc3 className="h-16 w-16 mx-auto mb-4 text-[#457B9D]" />
                <p className="font-sans font-black text-2xl tracking-tight">YOUR RECORD APPEARS HERE</p>
                <p className="font-mono text-sm text-[#457B9D] mt-2">
                  Upload a MIDI file and hit "Cut the Record"
                </p>
              </div>
            </div>
          )}
          {converting && (
            <div className="absolute inset-0 z-20 bg-[#1D3557]/85 flex flex-col items-center justify-center text-white">
              <Loader2 className="h-12 w-12 animate-spin mb-4" />
              <p className="font-sans font-black text-2xl tracking-tight">PRESSING RECORD…</p>
              <p className="font-mono text-xs mt-2 opacity-80">generating printable geometry</p>
            </div>
          )}
          {stlUrl && (
            <div className="absolute bottom-3 left-3 font-mono text-[10px] text-[#457B9D] bg-white/70 border border-[#1D3557] rounded px-2 py-1">
              drag to rotate · scroll to zoom
            </div>
          )}
        </section>

        {/* Controls */}
        <aside className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          {/* Upload */}
          <div className={`${CARD} p-5`}>
            <h2 className="font-sans font-black text-xl tracking-tight flex items-center gap-2 mb-3">
              <Music4 className="h-5 w-5" /> 1 · LOAD MIDI
            </h2>
            <div
              data-testid="midi-upload-zone"
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault(); setDragging(false);
                pickFile(e.dataTransfer.files?.[0]);
              }}
              className={`cursor-pointer border-4 border-dashed rounded-xl p-6 text-center transition-colors duration-150 ${
                dragging ? "border-[#E63946] bg-[#E63946]/5" : "border-[#457B9D] bg-white"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".mid,.midi"
                className="hidden"
                data-testid="midi-file-input"
                onChange={(e) => pickFile(e.target.files?.[0])}
              />
              <UploadCloud className="h-9 w-9 mx-auto mb-2 text-[#457B9D]" />
              {file ? (
                <p className="font-mono text-sm font-bold flex items-center justify-center gap-2 break-all">
                  <FileMusic className="h-4 w-4 shrink-0" /> {file.name}
                </p>
              ) : (
                <>
                  <p className="font-mono text-sm font-bold">Drop a .mid file here</p>
                  <p className="font-mono text-xs text-[#457B9D] mt-1">or click to browse</p>
                </>
              )}
            </div>
          </div>

          {/* Options */}
          <div className={`${CARD} p-5 flex flex-col gap-5`}>
            <h2 className="font-sans font-black text-xl tracking-tight flex items-center gap-2">
              <Wand2 className="h-5 w-5" /> 2 · SETTINGS
            </h2>

            <div className="flex items-center justify-between">
              <label className="font-mono text-sm flex items-center gap-2">
                <Wand2 className="h-4 w-4" /> Auto-transpose
              </label>
              <Toggle checked={autoTranspose} onChange={setAutoTranspose} testId="transpose-toggle" />
            </div>

            {!autoTranspose && (
              <div>
                <label className="font-mono text-sm flex items-center justify-between">
                  <span>Manual shift</span>
                  <span className="font-bold" data-testid="offset-value">{manualOffset > 0 ? `+${manualOffset}` : manualOffset} st</span>
                </label>
                <input
                  type="range" min="-24" max="24" step="1" value={manualOffset}
                  data-testid="offset-slider"
                  onChange={(e) => setManualOffset(Number(e.target.value))}
                  className="w-full mt-2 accent-[#E63946]"
                />
              </div>
            )}

            <div>
              <label className="font-mono text-sm flex items-center justify-between">
                <span className="flex items-center gap-2"><Clock className="h-4 w-4" /> Capture window</span>
                <span className="font-bold" data-testid="duration-value">{duration}s</span>
              </label>
              <input
                type="range" min="5" max="40" step="1" value={duration}
                data-testid="duration-slider"
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full mt-2 accent-[#457B9D]"
              />
              <p className="font-mono text-[10px] text-[#457B9D] mt-1">
                First {duration}s of the song fit one disc revolution
              </p>
            </div>

            <div>
              <label className="font-mono text-sm flex items-center justify-between">
                <span className="flex items-center gap-2"><Ruler className="h-4 w-4" /> Disc thickness</span>
                <span className="font-bold" data-testid="thickness-value">{thickness.toFixed(1)}mm</span>
              </label>
              <input
                type="range" min="2" max="6" step="0.5" value={thickness}
                data-testid="thickness-slider"
                onChange={(e) => setThickness(Number(e.target.value))}
                className="w-full mt-2 accent-[#457B9D]"
              />
            </div>
          </div>

          {/* Action */}
          <button
            data-testid="convert-button"
            disabled={!file || converting}
            onClick={onConvert}
            className={`font-sans font-black text-lg tracking-tight rounded-xl border-2 border-[#1D3557] py-4 flex items-center justify-center gap-2 transition-[transform,box-shadow] duration-150 ${
              !file || converting
                ? "bg-[#E9C46A]/50 text-[#1D3557]/50 cursor-not-allowed shadow-[2px_2px_0_0_#1D3557]"
                : "bg-[#E63946] text-white shadow-[4px_4px_0_0_#1D3557] hover:-translate-y-1 hover:shadow-[6px_6px_0_0_#1D3557] active:translate-y-1 active:shadow-[2px_2px_0_0_#1D3557]"
            }`}
          >
            {converting ? <Loader2 className="h-5 w-5 animate-spin" /> : <Disc3 className="h-5 w-5" />}
            {converting ? "CUTTING…" : "CUT THE RECORD"}
          </button>

          {stlUrl && (
            <div className="flex flex-col gap-3">
              <p className="font-mono text-xs text-[#457B9D]">3 · DOWNLOAD FILES</p>
              <a
                data-testid="download-stl-button"
                href={stlUrl}
                className="font-sans font-black text-lg tracking-tight rounded-xl border-2 border-[#1D3557] py-4 flex items-center justify-center gap-2 bg-[#2A9D8F] text-white shadow-[4px_4px_0_0_#1D3557] transition-[transform,box-shadow] duration-150 hover:-translate-y-1 hover:shadow-[6px_6px_0_0_#1D3557] active:translate-y-1 active:shadow-[2px_2px_0_0_#1D3557]"
              >
                <Download className="h-5 w-5" /> .STL (3D PRINT)
              </a>
              <div className="grid grid-cols-2 gap-3">
                <a
                  data-testid="download-scad-button"
                  href={scadUrl}
                  className="font-sans font-bold text-sm tracking-tight rounded-xl border-2 border-[#1D3557] py-3 flex items-center justify-center gap-2 bg-white text-[#1D3557] shadow-[3px_3px_0_0_#1D3557] transition-[transform,box-shadow] duration-150 hover:-translate-y-1 hover:shadow-[5px_5px_0_0_#1D3557] active:translate-y-1 active:shadow-[2px_2px_0_0_#1D3557]"
                >
                  <FileCode className="h-4 w-4" /> .SCAD
                </a>
                <a
                  data-testid="download-fpr-button"
                  href={fprUrl}
                  className="font-sans font-bold text-sm tracking-tight rounded-xl border-2 border-[#1D3557] py-3 flex items-center justify-center gap-2 bg-white text-[#1D3557] shadow-[3px_3px_0_0_#1D3557] transition-[transform,box-shadow] duration-150 hover:-translate-y-1 hover:shadow-[5px_5px_0_0_#1D3557] active:translate-y-1 active:shadow-[2px_2px_0_0_#1D3557]"
                >
                  <FileText className="h-4 w-4" /> .FPR
                </a>
              </div>
            </div>
          )}
        </aside>

        {/* Error */}
        {error && (
          <div data-testid="error-panel" className="col-span-12 bg-[#E63946] text-white border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl p-5 font-mono text-sm flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0" /> {error}
          </div>
        )}

        {/* Results / spec sheet */}
        {result && (
          <div data-testid="result-panel" className="col-span-12 grid grid-cols-1 md:grid-cols-12 gap-6">
            <div className={`${CARD} p-6 md:col-span-7`}>
              <h3 className="font-sans font-black text-xl tracking-tight flex items-center gap-2 mb-4">
                <CheckCircle2 className="h-5 w-5 text-[#2A9D8F]" /> SPEC SHEET — {result.title}
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-sm">
                {[
                  ["Notes placed", result.pin_count],
                  ["On-pitch", result.exact],
                  ["Snapped", result.adjusted],
                  ["Transpose", `${result.offset >= 0 ? "+" : ""}${result.offset} st`],
                  ["Window", `${result.duration}s`],
                  ["Thickness", `${result.thickness}mm`],
                  ["Triangles", result.triangles.toLocaleString()],
                  ["Diameter", "121mm"],
                ].map(([k, v]) => (
                  <div key={k} className="border-2 border-[#1D3557] rounded-lg p-2 bg-[#F4F1EA]">
                    <div className="text-[10px] uppercase text-[#457B9D]">{k}</div>
                    <div className="font-black text-lg text-[#1D3557]">{v}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="md:col-span-5 bg-[#FFB703] border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl p-6 font-mono text-sm">
              <h3 className="font-sans font-black text-lg tracking-tight mb-3">PLAYABLE TINES USED</h3>
              <div className="flex flex-wrap gap-2 mb-3">
                {result.notes_used.map((n) => <NoteBadge key={n.midi} name={n.name} />)}
              </div>
              {result.adjusted > 0 ? (
                <p className="flex items-start gap-2 text-[#1D3557]">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  {result.adjusted} note(s) were off the music box scale and snapped to the nearest playable tine.
                </p>
              ) : (
                <p className="flex items-start gap-2 text-[#1D3557]">
                  <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
                  Every note landed exactly on a playable tine. Perfect fit!
                </p>
              )}
            </div>
          </div>
        )}

        {/* History */}
        {history.length > 0 && (
          <div className={`${CARD} p-6 col-span-12`}>
            <h3 className="font-sans font-black text-xl tracking-tight flex items-center gap-2 mb-4">
              <History className="h-5 w-5" /> RECENT PRESSINGS
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {history.map((h) => (
                <div key={h.id} data-testid={`history-item-${h.id}`} className="border-2 border-[#1D3557] rounded-lg p-3 bg-[#F4F1EA] flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-mono font-bold truncate">{h.title}</div>
                    <div className="font-mono text-[11px] text-[#457B9D]">
                      {h.pin_count} notes · {h.thickness}mm
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button
                      title="Preview"
                      data-testid={`history-preview-${h.id}`}
                      onClick={() => setResult(h)}
                      className="h-9 w-9 flex items-center justify-center rounded-md border-2 border-[#1D3557] bg-white hover:bg-[#E9C46A] transition-colors duration-150"
                    >
                      <RotateCcw className="h-4 w-4" />
                    </button>
                    <a
                      title="Download"
                      href={`${API}/conversions/${h.id}/stl`}
                      className="h-9 w-9 flex items-center justify-center rounded-md border-2 border-[#1D3557] bg-[#2A9D8F] text-white hover:brightness-110 transition-[filter] duration-150"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <footer className="col-span-12 font-mono text-[11px] text-[#457B9D] text-center pt-4">
          Print at 100% scale · Ø121mm · fits the vintage Fisher-Price turntable spindle
        </footer>
      </div>
    </div>
  );
}
