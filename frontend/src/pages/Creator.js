import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  Disc3, Music4, Wand2, AlertTriangle, Loader2, Grid3X3, Box, ListMusic,
} from "lucide-react";
import RecordViewer from "../components/RecordViewer";
import UploadZone from "../components/UploadZone";
import SettingsPanel from "../components/SettingsPanel";
import EditorWorkspace from "../components/EditorWorkspace";
import { DownloadPanel, SpecSheet, HistoryPanel } from "../components/ResultPanels";
import { CARD, BTN_BASE, BTN_DISABLED, MAX_BEAT, NOTES, TOY_REV_SECONDS } from "../lib/fp";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const stem = (name) => name.replace(/\.[^.]+$/, "").slice(0, 40);
const emptyAnalysis = () => ({
  partition: NOTES.map(() => Array(MAX_BEAT).fill(false)),
  offset: 0, exact: 0, adjusted: 0, merged: 0, note_count: 0,
});

const DEFAULTS = {
  title: "", titleB: "", thickness: 3.0, duration: TOY_REV_SECONDS, autoTranspose: true,
  manualOffset: 0, twoSided: false, sideMode: "continue", engrave: true,
};

export default function Creator() {
  const [files, setFiles] = useState({ a: null, b: null });
  const [s, setS] = useState(DEFAULTS);
  const [revSeconds, setRevSeconds] = useState(TOY_REV_SECONDS);
  const [analysis, setAnalysis] = useState(null);
  const [parts, setParts] = useState({ a: null, b: null });
  const [active, setActive] = useState("a");
  const [stale, setStale] = useState(false);
  const [result, setResult] = useState(null);
  const [tab, setTab] = useState("notes");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [history, setHistory] = useState([]);
  const skipStale = useRef(false);

  const set = (patch) => setS((p) => ({ ...p, ...patch }));

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/conversions`);
      setHistory(data);
    } catch (e) { /* ignore */ }
  }, []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  useEffect(() => {
    if (skipStale.current) { skipStale.current = false; return; }
    if (analysis) setStale(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files.a, files.b, s.duration, s.autoTranspose, s.manualOffset, s.twoSided, s.sideMode]);

  const onFileA = (f) => { setFiles((p) => ({ ...p, a: f })); setS((p) => ({ ...p, title: p.title || stem(f.name) })); };
  const onFileB = (f) => { setFiles((p) => ({ ...p, b: f })); setS((p) => ({ ...p, titleB: p.titleB || stem(f.name) })); };

  const analyzeSide = async (file, start) => {
    const form = new FormData();
    form.append("file", file);
    form.append("duration", String(s.duration));
    form.append("start", String(start));
    form.append("auto_transpose", String(s.autoTranspose));
    form.append("manual_offset", String(s.manualOffset));
    const { data } = await axios.post(`${API}/analyze`, form);
    return data;
  };

  const needsB = s.twoSided && s.sideMode === "file";
  const canAnalyze = files.a && (!needsB || files.b) && !busy;

  const onAnalyze = async () => {
    if (!canAnalyze) return;
    setBusy("analyze"); setError(null); setNotice(null);
    try {
      const a = await analyzeSide(files.a, 0);
      let b = null;
      if (s.twoSided) {
        try {
          b = s.sideMode === "file" ? await analyzeSide(files.b, 0) : await analyzeSide(files.a, s.duration);
        } catch (e) {
          if (e?.response?.status !== 422) throw e;
          b = emptyAnalysis();
          setNotice(`Side B is blank — no notes found ${s.sideMode === "file" ? "in that file" : `between ${s.duration}s and ${s.duration * 2}s`}. You can draw notes by hand.`);
        }
      }
      skipStale.current = false;
      setAnalysis({ a, b });
      setParts({ a: a.partition, b: b ? b.partition : null });
      setActive("a"); setStale(false); setResult(null); setTab("notes");
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not read that MIDI file.");
    } finally { setBusy(null); }
  };

  const onPress = async () => {
    if (!analysis || stale || busy) return;
    setBusy("press"); setError(null);
    const b = analysis.b;
    try {
      const { data } = await axios.post(`${API}/press`, {
        title: s.title.trim() || "Record",
        partition: parts.a,
        partition_b: s.twoSided ? parts.b : null,
        title_b: s.titleB.trim() || "Side B",
        thickness: s.thickness,
        engrave: s.engrave,
        filename: files.a?.name || "record.mid",
        duration: s.duration,
        offset: analysis.a.offset,
        exact: analysis.a.exact + (b?.exact || 0),
        adjusted: analysis.a.adjusted + (b?.adjusted || 0),
        merged: analysis.a.merged + (b?.merged || 0),
      });
      setResult(data); setTab("preview"); loadHistory();
    } catch (e) {
      setError(e?.response?.data?.detail || "Pressing failed. Try again.");
    } finally { setBusy(null); }
  };

  const openHistory = (h) => {
    setResult(h); setTab("preview"); setError(null);
    if (!h.partition) return;
    const mk = (p, meta) => ({ partition: p, offset: meta.offset ?? 0, exact: meta.exact ?? 0, adjusted: meta.adjusted ?? 0, merged: meta.merged ?? 0 });
    skipStale.current = true;
    setAnalysis({ a: mk(h.partition, h), b: h.partition_b ? mk(h.partition_b, { offset: h.offset }) : null });
    setParts({ a: h.partition, b: h.partition_b || null });
    setActive("a"); setStale(false);
    set({ title: h.title, titleB: h.title_b || "", twoSided: !!h.two_sided, thickness: h.thickness, duration: h.duration });
    setTimeout(() => { skipStale.current = false; }, 0);
  };

  const sides = analysis ? [
    { key: "a", title: s.title, analysis: analysis.a, partition: parts.a, original: analysis.a.partition,
      onChange: (p) => setParts((x) => ({ ...x, a: p })) },
    ...(s.twoSided && analysis.b ? [{
      key: "b", title: s.titleB, analysis: analysis.b, partition: parts.b, original: analysis.b.partition,
      onChange: (p) => setParts((x) => ({ ...x, b: p })) }] : []),
  ] : [];

  const showViewer = tab === "preview" && result;
  const TabBtn = ({ id, icon: Icon, label, disabled }) => (
    <button
      data-testid={`tab-${id}`} disabled={disabled} onClick={() => setTab(id)}
      className={`font-sans font-black text-xs px-3 py-1.5 rounded-md border-2 border-[#1D3557] flex items-center gap-1.5 ${
        tab === id ? "bg-[#1D3557] text-white" : disabled ? "bg-white/50 text-[#1D3557]/40 cursor-not-allowed" : "bg-white hover:bg-[#E9C46A]"
      }`}
    >
      <Icon className="h-3.5 w-3.5" /> {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-[#F4F1EA] text-[#1D3557] fp-grain">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 p-6 md:p-12 max-w-[1400px] mx-auto">
        <header className="col-span-12 flex flex-wrap gap-4 justify-between items-end border-b-4 border-[#1D3557] pb-6">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-full border-2 border-[#1D3557] bg-[#E63946] shadow-[3px_3px_0_0_#1D3557] flex items-center justify-center">
              <Disc3 className="h-8 w-8 text-white" />
            </div>
            <div>
              <h1 className="font-sans font-black tracking-tighter text-3xl sm:text-4xl lg:text-5xl leading-none">RECORD MAKER</h1>
              <p className="font-mono text-xs sm:text-sm text-[#457B9D] mt-1">
                MIDI → 3D-printable disc for the 1977 Fisher-Price Music Box Player
              </p>
            </div>
          </div>
          <div className="font-mono text-xs text-[#457B9D] hidden sm:block">v3 · 22 tines (16 pitches) · 86 beats / rev · two-sided</div>
        </header>

        {/* Workspace */}
        <section data-testid="viewer-panel" className="col-span-12 lg:col-span-8 border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-2xl overflow-hidden min-h-[55vh] relative bg-[#F4F1EA] flex flex-col">
          <div className="flex items-center gap-2 p-3 border-b-2 border-[#1D3557]/20 bg-white/60">
            <TabBtn id="notes" icon={Grid3X3} label="NOTES" disabled={!analysis} />
            <TabBtn id="preview" icon={Box} label="3D PREVIEW" disabled={!result} />
            {stale && analysis && (
              <span data-testid="stale-badge" className="ml-auto font-mono text-[10px] bg-[#FFB703] border-2 border-[#1D3557] rounded px-2 py-0.5">
                settings changed · reload notes
              </span>
            )}
          </div>
          <div className="relative flex-1 min-h-[420px]">
            {showViewer ? (
              <RecordViewer url={`${API}/conversions/${result.id}/stl`} />
            ) : analysis ? (
              <EditorWorkspace
                sides={sides} active={active} onActive={setActive}
                duration={s.duration} revSeconds={revSeconds} onRevSeconds={setRevSeconds}
              />
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
                  <p className="font-mono text-sm text-[#457B9D] mt-2">Upload a MIDI, load the notes, tweak them, then cut the record</p>
                </div>
              </div>
            )}
            {busy && (
              <div className="absolute inset-0 z-20 bg-[#1D3557]/85 flex flex-col items-center justify-center text-white">
                <Loader2 className="h-12 w-12 animate-spin mb-4" />
                <p className="font-sans font-black text-2xl tracking-tight">{busy === "press" ? "PRESSING RECORD…" : "READING MIDI…"}</p>
                <p className="font-mono text-xs mt-2 opacity-80">{busy === "press" ? "generating printable geometry" : "mapping notes onto the tines"}</p>
              </div>
            )}
            {showViewer && (
              <div className="absolute bottom-3 left-3 font-mono text-[10px] text-[#457B9D] bg-white/70 border border-[#1D3557] rounded px-2 py-1">
                drag to rotate · scroll to zoom{result.two_sided ? " · flip to see side B" : ""}
              </div>
            )}
          </div>
        </section>

        {/* Controls */}
        <aside className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          <div className={`${CARD} p-5 flex flex-col gap-3`}>
            <h2 className="font-sans font-black text-xl tracking-tight flex items-center gap-2">
              <Music4 className="h-5 w-5" /> 1 · LOAD MIDI
            </h2>
            <UploadZone file={files.a} onFile={onFileA} onError={setError} testId="midi-upload-zone" label={needsB ? "Side A" : null} />
            {needsB && (
              <UploadZone file={files.b} onFile={onFileB} onError={setError} testId="midi-upload-zone-b" label="Side B" />
            )}
          </div>

          <div className={`${CARD} p-5 flex flex-col gap-4`}>
            <h2 className="font-sans font-black text-xl tracking-tight flex items-center gap-2">
              <Wand2 className="h-5 w-5" /> 2 · SETTINGS
            </h2>
            <SettingsPanel s={s} set={set} revSeconds={revSeconds} />
          </div>

          <button
            data-testid="analyze-button" disabled={!canAnalyze} onClick={onAnalyze}
            className={`${BTN_BASE} text-lg py-4 ${!canAnalyze ? BTN_DISABLED : "bg-[#457B9D] text-white"}`}
          >
            {busy === "analyze" ? <Loader2 className="h-5 w-5 animate-spin" /> : <ListMusic className="h-5 w-5" />}
            {analysis && !stale ? "3 · RELOAD NOTES" : "3 · LOAD NOTES"}
          </button>

          <button
            data-testid="convert-button" disabled={!analysis || stale || !!busy} onClick={onPress}
            className={`${BTN_BASE} text-lg py-4 ${!analysis || stale || busy ? BTN_DISABLED : "bg-[#E63946] text-white"}`}
          >
            {busy === "press" ? <Loader2 className="h-5 w-5 animate-spin" /> : <Disc3 className="h-5 w-5" />}
            {busy === "press" ? "CUTTING…" : "CUT THE RECORD"}
          </button>

          {result && <DownloadPanel api={API} result={result} />}
        </aside>

        {error && (
          <div data-testid="error-panel" className="col-span-12 bg-[#E63946] text-white border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl p-5 font-mono text-sm flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0" /> {error}
          </div>
        )}
        {notice && (
          <div data-testid="notice-panel" className="col-span-12 bg-[#FFB703] border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl p-5 font-mono text-sm flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0" /> {notice}
          </div>
        )}

        {result && <SpecSheet result={result} />}
        <HistoryPanel api={API} history={history} onPreview={openHistory} />

        <footer className="col-span-12 font-mono text-[11px] text-[#457B9D] text-center pt-4">
          Print at 100% scale · Ø121mm · one revolution ≈ {revSeconds}s on the toy · fits the vintage Fisher-Price spindle
        </footer>
      </div>
    </div>
  );
}
