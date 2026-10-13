// ===== ui.js — the app: load, settings, editor, press, 3D preview, albums, shelf, backups =====
(() => {
  const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
  const h = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else if (k === "html") e.innerHTML = v; else e.setAttribute(k, v); } for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k.nodeType ? k : document.createTextNode(String(k))); return e; };
  const toast = (msg, err = false) => { const t = h("div", { class: "toast" + (err ? " err" : ""), "data-testid": "toast" }, msg); document.body.append(t); setTimeout(() => t.remove(), 4200); };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---------- state ----------
  const S = { title: "", titleB: "", twoSided: false, thickness: 3.0, duration: 25, revSeconds: 25, start: 0, pinRadius: FP.R_PIN, dedHeight: FP.DED_H, dedFont: "bold", dedB: true, voices: 1, roll: "before", engrave: true, recordNo: "", autoTranspose: true, offset: 0, skyline: false, tracks: null, comb: FP.DEFAULT_COMB,
    mid: null, midName: "", scan: [], analysis: null, analysisB: null, side: "a", playing: null, result: null, album: null, history: [], defaults: null, shelfFocus: null, shelfQ: "" };
  const part = () => (S.side === "a" ? S.analysis : S.analysisB);
  const setPart = (p) => { const a = part() || { partition: p, noteCount: 0, exact: 0, adjusted: 0, offset: 0, notesUsed: [] }; a.partition = p; if (S.side === "a") S.analysis = a; else S.analysisB = a; };

  // ---------- splash ----------
  function splash() { const el = $("#splash"); const go = () => { el.classList.add("hidden"); AUDIO.engine(); }; el.onclick = go; setTimeout(go, 2500); }

  // ---------- sound check ----------
  function soundCheck() {
    const el = $("#sound"); const draw = () => { const st = AUDIO.state(), v = AUDIO.getVolume(); const blocked = st === "suspended", muted = v === 0; el.innerHTML = ""; el.append(
      h("button", { class: "btn sm " + (blocked || muted ? "red" : "teal"), "data-testid": "sound-test-button", onclick: () => { AUDIO.engine(); AUDIO.testTone(); } }, "♪ TEST"),
      h("span", { class: "mono", "data-testid": "sound-state", style: blocked || muted ? "color:var(--red);font-weight:900" : "" }, muted ? "MUTED" : blocked ? "SOUND BLOCKED — click anywhere" : st === "running" ? `SOUND ON · ${Math.round(AUDIO.sampleRate() / 1000)} kHz` : "SOUND READY"),
      h("input", { type: "range", min: 0, max: 1, step: 0.05, value: v, style: "width:90px", "data-testid": "volume-slider", oninput: (e) => AUDIO.setVolume(Number(e.target.value)) }), h("span", { class: "mono" }, `${Math.round(v * 100)}%`)); };
    AUDIO.watch(draw); draw();
  }

  // ---------- load card ----------
  async function loadFile(file) {
    try { S.mid = FP.parseMidi(await file.arrayBuffer()); S.midName = file.name; S.scan = FP.scanTracks(S.mid); S.tracks = null; S.start = 0; S.title = S.title || file.name.replace(/\.(mid|midi)$/i, ""); $("#title").value = S.title; renderTracks(); $("#midi-info").textContent = `${file.name} · ${S.mid.events.length} notes · ${S.mid.length.toFixed(1)} s · ${S.scan.length} pitched tracks`; $("#start").max = Math.max(0, S.mid.length - 1); await autoFit(); }
    catch (e) { toast("Could not read that MIDI: " + e.message, true); }
  }
  function renderTracks() {
    const box = $("#tracks"); box.innerHTML = "";
    if (!S.scan.length) { box.append(h("div", { class: "hint" }, "Load a MIDI to see its tracks.")); return; }
    const best = S.scan[0].confidence; const auto = S.scan.filter((t) => t.confidence >= best - 15 && !t.drums).map((t) => t.index);
    if (!S.tracks) S.tracks = auto;
    S.scan.forEach((t) => box.append(h("label", {}, h("input", { type: "checkbox", "data-testid": `track-${t.index}`, ...(S.tracks.includes(t.index) ? { checked: "" } : {}), onchange: (e) => { S.tracks = e.target.checked ? [...S.tracks, t.index] : S.tracks.filter((x) => x !== t.index); } }), h("span", { class: "conf " + (t.confidence >= 65 ? "hi" : t.confidence < 40 ? "lo" : "") }, `${t.confidence}%`), h("span", { class: "grow" }, `${t.name}${t.instrument ? " · " + t.instrument : ""}`), h("span", {}, `${t.notes} notes · ${t.range[0]}–${t.range[1]}${t.poly ? ` · ${t.poly}% chords` : ""}`))));
    box.append(h("div", { class: "row" }, h("button", { class: "btn sm", "data-testid": "tracks-apply", onclick: autoFit }, "RE-FIT WITH THESE TRACKS"), h("label", { class: "mono" }, h("input", { type: "checkbox", onchange: (e) => { S.skyline = e.target.checked; } }), " top note only (skyline)")));
  }
  async function autoFit() {
    if (!S.mid) return;
    busy("Auto-fitting tempo & key…");
    await new Promise((r) => setTimeout(r, 30));
    try { const rec = FP.autoFit(S.mid, S.start, S.revSeconds, S.comb, S.roll, S.autoTranspose, S.offset, S.tracks, S.skyline, S.voices > 1, S.voices); S.analysis = rec; S.duration = rec.fit.duration; S.offset = rec.offset; S.side = "a"; S.result = null;
      $("#fit-info").innerHTML = `fit <b>${rec.fit.score}</b>/100 · ${rec.noteCount} notes → ${rec.exact} exact · ${rec.adjusted} nudged · ${rec.staggered} rolled · ${rec.dropped} dropped · window ${rec.fit.start}s + ${rec.fit.duration}s (${Math.round((rec.fit.duration / S.revSeconds) * 100)}% tempo) · key shift ${rec.offset >= 0 ? "+" : ""}${rec.offset}`;
      drawGrid(); showResult(null); }
    catch (e) { toast(e.message, true); } finally { busy(null); }
  }
  function pickTune(i) { const [title, mel] = FP.LIBRARY[i]; const rec = FP.eventsToRecord(FP.melodyEvents(mel, S.duration), S.duration, true, 0, S.comb, S.voices <= 1, S.roll, S.voices); S.analysis = rec; S.title = title; $("#title").value = title; S.mid = null; S.scan = []; S.midName = ""; renderTracks(); $("#midi-info").textContent = `Factory tune: ${title}`; $("#fit-info").textContent = `${rec.noteCount} notes · ${rec.exact} exact · ${rec.staggered} rolled`; S.side = "a"; S.result = null; drawGrid(); showResult(null); }
  let tunePlay = null;
  function playTune(i) { if (tunePlay) { tunePlay.stop(); tunePlay = null; $$(".tune-play").forEach((b) => (b.textContent = "▶")); return; } const [, mel] = FP.LIBRARY[i]; const rec = FP.eventsToRecord(FP.melodyEvents(mel, S.duration), S.duration, true, 0, S.comb); const btn = $(`#tune-play-${i}`); btn.textContent = "■"; tunePlay = AUDIO.playSides([rec.partition], S.comb.notes, S.revSeconds, () => {}, () => { tunePlay = null; btn.textContent = "▶"; }); }

  // ---------- settings ----------
  function settings() {
    const el = $("#settings"); el.innerHTML = "";
    const slider = (label, key, min, max, step, fmt, hint, testid) => { const wrap = h("div", {}); const val = h("span", { class: "val", "data-testid": `${testid}-value` }, fmt(S[key])); const hintEl = h("div", { class: "hint" }, hint(S[key])); wrap.append(h("div", { class: "row" }, h("span", { class: "mono" }, label), val), h("input", { type: "range", min, max, step, value: S[key], "data-testid": `${testid}-slider`, oninput: (e) => { S[key] = Number(e.target.value); val.textContent = fmt(S[key]); hintEl.textContent = hint(S[key]); if (key === "dedHeight") fontPreviews(); } }), hintEl); return wrap; };
    const seg = (key, opts, testid, after) => { const s = h("div", { class: "seg" }); const draw = () => { s.innerHTML = ""; opts.forEach(([v, l]) => s.append(h("button", { class: String(S[key]) === String(v) ? "on" : "", "data-testid": `${testid}-${v}`, onclick: () => { S[key] = v; draw(); after && after(); } }, l))); }; draw(); return s; };
    const toggle = (key, testid, after) => h("label", { class: "toggle" }, h("input", { type: "checkbox", ...(S[key] ? { checked: "" } : {}), "data-testid": testid, onchange: (e) => { S[key] = e.target.checked; after && after(); } }), h("i"));
    el.append(
      h("div", { class: "row" }, h("span", { class: "mono grow" }, "Two-sided disc (Side B)"), toggle("twoSided", "two-sided-toggle", () => { $("#sideb-wrap").classList.toggle("hidden", !S.twoSided); $("#side-seg").classList.toggle("hidden", !S.twoSided); if (S.twoSided && !S.analysisB) S.analysisB = { partition: S.comb.notes.map(() => Array(FP.MAX_BEAT).fill(false)), noteCount: 0, exact: 0, adjusted: 0, offset: 0, notesUsed: [] }; settings(); })),
      h("div", { class: "row" }, h("span", { class: "mono grow" }, "Engrave record number + dash"), toggle("engrave", "engrave-toggle")),
      h("div", { class: "row" }, h("span", { class: "mono grow" }, "Auto key shift (tines up/down)"), toggle("autoTranspose", "auto-transpose-toggle", autoFit)),
      slider("Toy speed: seconds per revolution", "revSeconds", 20, 32, 0.5, (v) => `${v.toFixed(1)}s`, (v) => `The toy turns one revolution in ~25 s; set it to what your player actually does (86 beats = ${(v / 86 * 1000).toFixed(0)} ms per beat).`, "rev-seconds"),
      slider("Disc thickness", "thickness", 2.5, 6, 0.1, (v) => `${v.toFixed(1)}mm`, (v) => (v < 3 ? "Thin — flexes more, grooves are 1.2 mm deep each side." : v > 4.5 ? "Thick — may not slide under the arm on some players." : "Factory records are about 3 mm."), "thickness"),
      slider("Pin height (triangle)", "pinRadius", 0.4, 1.2, 0.05, (v) => `${v.toFixed(2)}mm`, (v) => `Triangle ramp on the groove wall: ${FP.pinBase(v).toFixed(1)} mm base buried 0.5 mm into the wall. 0.9 is the print-tested default (0.8 felt a touch small).`, "pin-radius"),
      slider("Dedication letters (Barbara ring)", "dedHeight", 2, 3.5, 0.1, (v) => `${v.toFixed(1)}mm`, (v) => (v < 2.5 ? "Fine lettering — crisp with a 0.25 mm nozzle." : v <= 3 ? "Good match for a 0.4 mm nozzle." : "Bold lettering — easiest to read."), "ded-height"),
      h("div", { class: "row", id: "fontrow" }), h("div", { class: "hint" }, `“${FP.DEDICATION}” is raised on every disc. Font: BOLD = factory look · ROUNDED = soft · SCRIPT = handwritten (3 mm+ recommended).`),
      S.twoSided ? h("div", { class: "row" }, h("span", { class: "mono grow" }, "Dedication ring on side B too"), toggle("dedB", "ded-b-toggle")) : null,
      h("div", { class: "row" }, h("span", { class: "mono" }, "Notes at once"), seg("voices", [[1, "ONE"], [2, "TWO"], [3, "THREE"], [16, "ALL"]], "voices", () => refit()), h("span", { class: "hint" }, "ONE = factory style (notes roll). TWO/THREE = simple chords on different tines.")),
      h("div", { class: "row" }, h("span", { class: "mono" }, "Roll direction"), seg("roll", [["before", "LEAN BEFORE"], ["after", "LEAN AFTER"]], "roll", () => refit())),
      h("label", { class: "f" }, "Record number (blank = next free)"), h("input", { type: "number", min: 6, max: 999, "data-testid": "record-no", value: S.recordNo, oninput: (e) => { S.recordNo = e.target.value; } }),
    );
    fontPreviews();
  }
  const refit = () => { if (S.mid) autoFit(); else if (S.analysis) { const ev = S.analysis.events; if (ev && ev.length) { const rec = FP.eventsToRecord(ev, S.duration, false, S.offset, S.comb, S.voices <= 1, S.roll, S.voices); S.analysis = { ...S.analysis, ...rec }; drawGrid(); } } };
  let fontsReady = null;
  function fontPreviews() {
    const row = $("#fontrow"); if (!row) return; row.innerHTML = "";
    [["bold", "BOLD"], ["rounded", "ROUNDED"], ["script", "SCRIPT"]].forEach(([k, l]) => { const c = h("canvas", { width: 160, height: 160, "data-testid": `ded-font-preview-${k}` }); row.append(h("button", { class: "btn fontbtn" + (S.dedFont === k ? " on" : ""), "data-testid": `ded-font-${k}`, onclick: () => { S.dedFont = k; fontPreviews(); } }, c, l)); previewRing(c, k); });
  }
  async function previewRing(canvas, font) {
    const g = canvas.getContext("2d"); g.clearRect(0, 0, 160, 160); g.fillStyle = "#B9A9E3"; g.beginPath(); g.arc(80, 80, 78, 0, 7); g.fill(); g.fillStyle = "#F4F1EA"; g.beginPath(); g.arc(80, 80, 12, 0, 7); g.fill();
    try { const { fonts } = await GEOM.ready(() => {}); const f = fonts[font] || fonts.bold; const path = f.getPath(FP.DEDICATION, 0, 0, 10); const bb = path.getBoundingBox(); const w = bb.x2 - bb.x1, hh = bb.y2 - bb.y1; const s = Math.min(S.dedHeight / hh, ((FP.DED_ARC * Math.PI) / 180) * FP.DED_R / w); const k = 160 / 42; g.fillStyle = "#1D3557"; g.beginPath();
      const warp = (x, y) => { const X = (x - (bb.x1 + bb.x2) / 2) * s, Y = -(y - (bb.y1 + bb.y2) / 2) * s; const th = -X / FP.DED_R; const r = FP.DED_R + Y; return [80 + r * Math.cos(th) * k, 80 - r * Math.sin(th) * k]; };
      let lx = 0, ly = 0; for (const c of path.commands) { if (c.type === "M") { const [px, py] = warp(c.x, c.y); g.moveTo(px, py); lx = c.x; ly = c.y; } else if (c.type === "L") { const [px, py] = warp(c.x, c.y); g.lineTo(px, py); lx = c.x; ly = c.y; } else if (c.type === "Q" || c.type === "C") { for (let i = 1; i <= 5; i++) { const t = i / 5, mt = 1 - t; const x = c.type === "Q" ? mt * mt * lx + 2 * mt * t * c.x1 + t * t * c.x : mt ** 3 * lx + 3 * mt * mt * t * c.x1 + 3 * mt * t * t * c.x2 + t ** 3 * c.x; const y = c.type === "Q" ? mt * mt * ly + 2 * mt * t * c.y1 + t * t * c.y : mt ** 3 * ly + 3 * mt * mt * t * c.y1 + 3 * mt * t * t * c.y2 + t ** 3 * c.y; const [px, py] = warp(x, y); g.lineTo(px, py); } lx = c.x; ly = c.y; } else if (c.type === "Z") g.closePath(); }
      g.fill("evenodd"); } catch (e) { g.fillStyle = "#1D3557"; g.font = "10px sans-serif"; g.fillText("fonts load online", 40, 84); }
  }

  // ---------- note editor (canvas) ----------
  const grid = { cell: 0, left: 54, top: 18 };
  function drawGrid(playBeat = -1) {
    const c = $("#grid"), p = part(); const W = c.clientWidth || 1000; const cell = Math.floor((W - grid.left) / FP.MAX_BEAT); grid.cell = cell; const rows = S.comb.tones; c.width = grid.left + cell * FP.MAX_BEAT + 1; c.height = grid.top + cell * rows + 1;
    const g = c.getContext("2d"); g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); g.font = "10px monospace"; g.textBaseline = "middle";
    const conflicts = new Set(); if (p) { for (let b = 0; b < FP.MAX_BEAT; b++) { const tones = []; p.partition.forEach((r, t) => { if (r[b]) tones.push(t); }); if (tones.length > S.voices) tones.forEach((t) => conflicts.add(`${t}-${b}`)); } p.partition.forEach((row, t) => { const gap = FP.gapBeats(t, S.comb, FP.MAX_BEAT); for (let b = 0; b < FP.MAX_BEAT; b++) if (row[b]) for (let d = 1; d < gap; d++) if (row[(b + d) % FP.MAX_BEAT]) { conflicts.add(`${t}-${b}`); conflicts.add(`${t}-${(b + d) % FP.MAX_BEAT}`); } }); }
    for (let t = 0; t < rows; t++) { const y = grid.top + (rows - 1 - t) * cell; g.fillStyle = S.comb.twins.has(t) ? "#2A9D8F" : "#1D3557"; g.fillText(FP.noteName(S.comb.notes[t]).padStart(3), 4, y + cell / 2); g.fillStyle = "#1D3557"; g.fillText(S.comb.twins.has(t) ? "x2" : "", 30, y + cell / 2);
      for (let b = 0; b < FP.MAX_BEAT; b++) { const x = grid.left + b * cell; g.fillStyle = b % 4 === 0 ? "#f1ede4" : "#faf8f3"; g.fillRect(x, y, cell - 1, cell - 1); if (p && p.partition[t][b]) { g.fillStyle = conflicts.has(`${t}-${b}`) ? "#E63946" : "#1D3557"; g.beginPath(); g.arc(x + cell / 2, y + cell / 2, cell * 0.38, 0, 7); g.fill(); } } }
    g.fillStyle = "#457B9D"; for (let b = 0; b < FP.MAX_BEAT; b += 5) g.fillText(String(b), grid.left + b * cell + 2, 8);
    if (playBeat >= 0) { g.fillStyle = "rgba(230,57,70,.25)"; g.fillRect(grid.left + playBeat * cell, grid.top, cell, cell * rows); }
    $("#count").textContent = p ? `${p.partition.reduce((s, r) => s + r.filter(Boolean).length, 0)} pins · ${conflicts.size ? conflicts.size / 1 + " flagged (red = chord over limit or too close on one tine)" : "all playable"}` : "";
  }
  function gridClick(e) { const c = $("#grid"), r = c.getBoundingClientRect(); const x = (e.clientX - r.left) * (c.width / r.width), y = (e.clientY - r.top) * (c.height / r.height); const b = Math.floor((x - grid.left) / grid.cell), t = S.comb.tones - 1 - Math.floor((y - grid.top) / grid.cell); if (b < 0 || b >= FP.MAX_BEAT || t < 0 || t >= S.comb.tones) return; if (!part()) setPart(S.comb.notes.map(() => Array(FP.MAX_BEAT).fill(false))); const p = part().partition; if (e.shiftKey) { AUDIO.tap(S.comb.notes[t]); return; } p[t][b] = !p[t][b]; if (p[t][b]) AUDIO.tap(S.comb.notes[t]); S.result = null; drawGrid(); }
  function togglePlay() { if (S.playing) { S.playing.stop(); S.playing = null; $("#play").textContent = "▶ PLAY"; drawGrid(); return; } const sides = [S.analysis && S.analysis.partition, S.twoSided && S.analysisB && S.analysisB.partition].filter(Boolean); if (!sides.length) return; $("#play").textContent = "■ STOP"; S.playing = AUDIO.playSides(sides, S.comb.notes, S.revSeconds, (si, b) => { S.side = si === 0 ? "a" : "b"; drawGrid(b); }, () => { S.playing = null; $("#play").textContent = "▶ PLAY"; drawGrid(); }); }
  function reviewWav() { const sides = [S.analysis && S.analysis.partition, S.twoSided && S.analysisB && S.analysisB.partition].filter(Boolean); if (!sides.length) return; const blob = AUDIO.renderWav(sides, S.comb.notes, S.revSeconds); const a = $("#review"); a.src = URL.createObjectURL(blob); a.classList.remove("hidden"); $("#review-dl").href = a.src; $("#review-dl").download = `${STORE.safeName(S.title)}-toy-8kHz.wav`; $("#review-dl").classList.remove("hidden"); a.play().catch(() => {}); }

  // ---------- press ----------
  const busy = (msg) => { const b = $("#busy"); if (!msg) { b.classList.add("hidden"); return; } b.classList.remove("hidden"); b.textContent = msg; };
  async function press(opts = {}) {
    const p = opts.partition || (S.analysis && S.analysis.partition); if (!p) { toast("Load a tune or click some notes first", true); return null; }
    busy("Pressing the record…");
    try {
      const { fonts } = await GEOM.ready(busy);
      const title = opts.title ?? (S.title || "Untitled"), titleB = S.twoSided ? S.titleB || "Side B" : "", pb = opts.partitionB !== undefined ? opts.partitionB : S.twoSided && S.analysisB ? S.analysisB.partition : null;
      const recordNo = opts.recordNo || Number(S.recordNo) || (await STORE.nextRecordNo(title));
      const o = { partition: p, partitionB: pb, thickness: S.thickness, title, titleB, marks: S.engrave, recordNo, comb: S.comb, pinRadius: S.pinRadius, dedHeight: S.dedHeight, dedB: S.dedB, dedFont: S.dedFont, fonts };
      busy("Building 3D geometry…"); await new Promise((r) => setTimeout(r, 20));
      const mesh = GEOM.buildMesh(o);
      const a = opts.analysis || S.analysis || {};
      const rec = { id: STORE.uuid(), createdAt: new Date().toISOString(), title, titleB, twoSided: !!pb, recordNo, thickness: S.thickness, duration: Math.round((a.duration || S.duration) * 100) / 100, revSeconds: S.revSeconds, pinRadius: S.pinRadius, dedHeight: S.dedHeight, dedB: S.dedB, dedFont: S.dedFont, voices: S.voices, roll: S.roll, offset: a.offset || 0, exact: a.exact || 0, adjusted: a.adjusted || 0, noteCount: a.noteCount || 0, notesUsed: a.notesUsed || [], pinCount: mesh.pinCount, check: mesh.check, partition: p, partitionB: pb, albumId: opts.albumId || null, albumIndex: opts.albumIndex || null, albumCount: opts.albumCount || null, filename: S.midName,
        stl: GEOM.toSTL(mesh.positions, title), scad: GEOM.toSCAD(o), fpr: FP.toFpr(p, title) + (pb ? "\n" + FP.toFpr(pb, titleB) : "") };
      await STORE.put("records", rec);
      if (!opts.silent) { S.result = rec; showResult(rec, mesh.positions); toast(`Record #${recordNo} pressed — ${mesh.pinCount} pins, ${mesh.check.ok ? "watertight" : "check mesh"}`); }
      await loadShelf();
      return { rec, positions: mesh.positions };
    } catch (e) { console.error(e); toast("Pressing failed: " + e.message, true); return null; } finally { busy(null); }
  }
  async function testDisc() { const p = FP.chordTestPartition(S.comb); const saved = { v: S.voices }; S.voices = 3; const r = await press({ partition: p, partitionB: null, title: "CHORD TEST 1-2-3", analysis: { duration: S.revSeconds, noteCount: p.reduce((s, r) => s + r.filter(Boolean).length, 0), notesUsed: [] } }); S.voices = saved.v; if (r) toast("Test disc: beats 2–14 single notes · 30–42 two-note chords · 58–70 triads. Print it, then note which section played cleanly below."); }

  // ---------- results + 3D ----------
  let three = null;
  async function viewer(positions) {
    const box = $("#viewer"); box.innerHTML = ""; if (!positions) { box.append(h("div", { class: "hint", style: "padding:20px" }, "Press a record to see it here in 3D.")); return; }
    try {
      const THREE = await import("https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"); const { OrbitControls } = await import("https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js");
      const W = box.clientWidth, H = box.clientHeight; const renderer = new THREE.WebGLRenderer({ antialias: true }); renderer.setSize(W, H); renderer.setPixelRatio(Math.min(2, devicePixelRatio)); box.append(renderer.domElement);
      const scene = new THREE.Scene(); scene.background = new THREE.Color("#F4F1EA"); const cam = new THREE.PerspectiveCamera(42, W / H, 0.5, 1000); cam.position.set(0, 95, 95);
      scene.add(new THREE.AmbientLight(0xffffff, 0.65)); const d1 = new THREE.DirectionalLight(0xffffff, 1.15); d1.position.set(50, 90, 40); scene.add(d1); const d2 = new THREE.DirectionalLight(0xffffff, 0.4); d2.position.set(-50, 30, -40); scene.add(d2); const graze = new THREE.DirectionalLight(0xffffff, 1.6); graze.position.set(60, 12, 20); graze.visible = false; scene.add(graze);
      const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(positions, 3)); geo.computeVertexNormals(); geo.center(); const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: "#B9A9E3", roughness: 0.55, metalness: 0.05, flatShading: true })); mesh.rotation.x = -Math.PI / 2; scene.add(mesh);
      const controls = new OrbitControls(cam, renderer.domElement); controls.autoRotate = true; controls.autoRotateSpeed = 0.8; controls.minDistance = 12; controls.maxDistance = 240;
      let alive = true; const loop = () => { if (!alive) return; controls.update(); renderer.render(scene, cam); requestAnimationFrame(loop); }; loop();
      const bar = h("div", { style: "position:absolute;top:10px;right:10px", class: "seg" }); const views = { disc: [0, 95, 95], label: [0, 70, 0.01] }; let cur = "disc";
      const drawBar = () => { bar.innerHTML = ""; for (const [k, l] of [["disc", "FULL DISC"], ["label", "READ LABEL"]]) bar.append(h("button", { class: cur === k ? "on" : "", "data-testid": `viewer-${k}`, onclick: () => { cur = k; cam.position.set(...views[k]); controls.target.set(0, 0, 0); controls.autoRotate = k === "disc"; graze.visible = k === "label"; controls.update(); drawBar(); } }, l)); };
      drawBar(); box.append(bar);
      if (three) three.dispose(); three = { dispose() { alive = false; renderer.dispose(); } };
    } catch (e) { box.append(h("div", { class: "hint", style: "padding:20px" }, "3D preview needs an internet connection the first time (three.js). STL downloads still work.")); }
  }
  function showResult(rec, positions) {
    const el = $("#result"); el.innerHTML = ""; if (!rec) { el.append(h("div", { class: "hint" }, "Nothing pressed yet.")); viewer(null); return; }
    const dl = (label, blob, name, cls = "") => h("button", { class: "btn " + cls, "data-testid": `download-${label.split(" ")[0].toLowerCase()}`, onclick: () => STORE.download(blob instanceof Blob ? blob : new Blob([blob], { type: "text/plain" }), name) }, label);
    const base = `${rec.recordNo}-${STORE.safeName(rec.title)}`;
    el.append(h("div", { class: "status", "data-testid": "result-status" }, h("b", {}, `RECORD #${rec.recordNo} · ${rec.title}${rec.twoSided ? " / " + rec.titleB : ""}`), ` — ${rec.pinCount} pins · ${rec.thickness} mm · ${rec.check.triangles} triangles · `, h("span", { class: rec.check.ok ? "ok" : "bad" }, rec.check.ok ? "WATERTIGHT ✓" : "MESH " + rec.check.status), ` · ${Math.round(rec.stl.size / 1024)} KB`),
      h("div", { class: "row" }, dl("STL (print this)", rec.stl, `${base}.stl`, "teal"), dl("SCAD (OpenSCAD)", rec.scad, `${base}.scad`), dl("FPR (tracker)", rec.fpr, `${base}.fpr`), dl("LABEL card (SVG)", new Blob([GEOM.labelCard(rec, rec.albumIndex ? [rec.albumIndex, rec.albumCount] : null)], { type: "image/svg+xml" }), `${base}-label.svg`),
        h("button", { class: "btn navy", "data-testid": "download-pack", onclick: async () => STORE.download(await STORE.zip([[`${base}.stl`, rec.stl], [`${base}.scad`, rec.scad], [`${base}.fpr`, rec.fpr], [`${base}-label.svg`, GEOM.labelCard(rec)], [`${base}-README.txt`, readme(rec)]]), `${base}-print-pack.zip`) }, "PRINT PACK (.ZIP)")));
    if (positions) viewer(positions); else { const blob = rec.stl; blob.arrayBuffer().then((buf) => { const dv = new DataView(buf), n = dv.getUint32(80, true), pos = new Float32Array(n * 9); for (let t = 0; t < n; t++) for (let k = 0; k < 9; k++) pos[t * 9 + k] = dv.getFloat32(84 + t * 50 + 12 + k * 4, true); viewer(pos); }); }
  }
  const readme = (rec) => `Fisher-Price Record Maker — Record #${rec.recordNo} "${rec.title}"\n${FP.DEDICATION} · © 2026 Russ Campbell\n\nPrint the STL flat, label side up, 0.2 mm layers or finer, 100% infill not needed (3+ walls). Pins are ${rec.pinRadius} mm triangles; clean stringing off them before the first play.\nSCAD = editable OpenSCAD source · FPR = tune-tracker text · label.svg = 100 x 60 mm sleeve card.\n${rec.pinCount} pins · ${rec.noteCount} notes · key shift ${rec.offset} · ${rec.duration}s window · side gap for two-sided: flip the disc.\n`;

  // ---------- album ----------
  async function planAlbum() { if (!S.mid) { toast("Load a MIDI file first", true); return; } busy("Planning the album…"); await new Promise((r) => setTimeout(r, 30)); try { S.album = FP.planSong(S.mid, S.comb, S.tracks, S.skyline, 0, S.revSeconds, S.roll, S.autoTranspose, S.offset, S.voices > 1, S.voices); drawAlbum(); } catch (e) { toast(e.message, true); } finally { busy(null); } }
  function drawAlbum() { const el = $("#album"); el.innerHTML = ""; const a = S.album; if (!a) { el.append(h("div", { class: "hint" }, "Cut the whole MIDI into consecutive discs (one revolution each).")); return; } const n = a.sides.length, discs = S.twoSided ? Math.ceil(n / 2) : n;
    el.append(h("div", { class: "status" }, `${a.noteCount} notes → ${n} sides → ${discs} disc${discs === 1 ? "" : "s"} · ${a.duration}s per side (${Math.round((a.duration / S.revSeconds) * 100)}% tempo) · key shift ${a.offset}`), h("div", { class: "progress" }, h("i", { id: "album-bar", style: "width:0" })),
      h("ol", { class: "mono", id: "album-list" }, a.sides.map((s, i) => h("li", {}, `side ${i + 1}: ${s.noteCount} notes · ${s.exact} exact · ${s.staggered} rolled · ${s.dropped} dropped`))),
      h("div", { class: "row" }, h("button", { class: "btn primary", "data-testid": "album-press", onclick: pressAlbum }, `PRESS ALL ${discs} DISCS`), h("button", { class: "btn", "data-testid": "album-play", onclick: () => { if (S.playing) { S.playing.stop(); S.playing = null; return; } S.playing = AUDIO.playSides(a.sides.map((s) => s.partition), S.comb.notes, S.revSeconds, () => {}, () => { S.playing = null; }); } }, "▶ PLAY WHOLE SONG"), h("button", { class: "btn", onclick: () => STORE.download(AUDIO.renderWav(a.sides.map((s) => s.partition), S.comb.notes, S.revSeconds), `${STORE.safeName(S.title)}-album-8kHz.wav`) }, "WAV 8 kHz")));
  }
  async function pressAlbum() { const a = S.album; if (!a) return; const albumId = STORE.uuid(), title = S.title || "Album", n = a.sides.length, discs = S.twoSided ? Math.ceil(n / 2) : n; const made = []; let no = Number(S.recordNo) || (await STORE.nextRecordNo(""));
    for (let d = 0; d < discs; d++) { const sa = S.twoSided ? a.sides[d * 2] : a.sides[d], sb = S.twoSided ? a.sides[d * 2 + 1] : null; const r = await press({ partition: sa.partition, partitionB: sb ? sb.partition : null, title: `${title} ${d + 1}/${discs}`, analysis: { ...sa, duration: a.duration }, recordNo: no + d, albumId, albumIndex: d + 1, albumCount: discs, silent: true }); if (!r) return; made.push(r.rec); $("#album-bar").style.width = `${Math.round(((d + 1) / discs) * 100)}%`; }
    await STORE.put("albums", { id: albumId, title, createdAt: new Date().toISOString(), discs: made.map((r) => ({ id: r.id, recordNo: r.recordNo, title: r.title })), duration: a.duration, offset: a.offset });
    toast(`Album pressed: ${discs} discs, records #${no}–#${no + discs - 1}`); S.result = made[0]; showResult(made[0]); await loadShelf();
    $("#album").append(h("div", { class: "row" }, h("button", { class: "btn teal", "data-testid": "album-zip", onclick: () => albumZip(albumId) }, "DOWNLOAD ALBUM ZIP"), h("button", { class: "btn", "data-testid": "album-sleeves", onclick: () => sleeveSheet(albumId) }, "PRINT SLEEVE SHEET")));
  }
  async function albumDocs(albumId) { const album = await STORE.get("albums", albumId); const docs = []; for (const d of album.discs) { const r = await STORE.get("records", d.id); if (r) docs.push(r); } return { album, docs }; }
  async function albumZip(albumId) { const { album, docs } = await albumDocs(albumId); const files = []; const lines = [`${album.title} — ${docs.length} discs, play in this order:`]; docs.forEach((r, i) => { const stem = `${String(i + 1).padStart(2, "0")}-${r.recordNo}-${STORE.safeName(r.title)}`; files.push([`${stem}.stl`, r.stl], [`scad/${stem}.scad`, r.scad], [`fpr/${stem}.fpr`, r.fpr], [`sleeves/${stem}-label.svg`, GEOM.labelCard(r, [i + 1, docs.length])]); lines.push(`  Record #${r.recordNo}  ${stem}.stl — ${r.pinCount} pins${r.twoSided ? " (two-sided: flip to continue)" : ""}`); }); files.push(["sleeves/sleeve-sheet.html", sleeveHtml(album, docs)], ["README.txt", lines.join("\n") + `\n\n${FP.DEDICATION} · © 2026 Russ Campbell\n`]); STORE.download(await STORE.zip(files), `${STORE.safeName(album.title)}-album.zip`); }
  const sleeveHtml = (album, docs) => { const cards = docs.map((r, i) => GEOM.labelCard(r, [i + 1, docs.length])); const pages = []; for (let p = 0; p < cards.length; p += 8) pages.push(`<div class="page">${cards.slice(p, p + 8).join("\n")}</div>`); return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(album.title)} — sleeve labels</title><style>@page{size:A4 portrait;margin:10mm}body{margin:0;font-family:Arial,sans-serif;color:#1D3557}.page{width:190mm;display:grid;grid-template-columns:1fr 1fr;gap:6mm 8mm;padding:4mm 0;page-break-after:always}svg{width:90mm;height:54mm;display:block}.bar{display:flex;gap:8px;align-items:center;margin-bottom:4mm}button{font:700 12px Arial;padding:6px 12px;border:2px solid #1D3557;background:#E9C46A;border-radius:6px;cursor:pointer}@media print{.bar{display:none}}</style></head><body><div class="bar"><h1 style="font-size:14px;margin:0">${esc(album.title)} — ${docs.length} numbered sleeve labels</h1><button onclick="window.print()">PRINT</button></div><p style="font-size:10px;color:#457B9D">Cut along the card borders (100 × 60 mm). Play order: ${docs.map((r) => "#" + r.recordNo).join(" → ")}. ${esc(FP.DEDICATION)} · © 2026 Russ Campbell</p>${pages.join("\n")}</body></html>`; };
  async function sleeveSheet(albumId) { const { album, docs } = await albumDocs(albumId); const w = window.open("", "_blank"); if (!w) { STORE.download(new Blob([sleeveHtml(album, docs)], { type: "text/html" }), "sleeve-sheet.html"); return; } w.document.write(sleeveHtml(album, docs)); w.document.close(); }

  // ---------- shelf ----------
  async function loadShelf() { S.history = await STORE.records(); drawShelf(); }
  function drawShelf() {
    const el = $("#shelf"); el.innerHTML = ""; const rs = S.history, q = S.shelfQ.trim().toLowerCase(); const hit = (r) => !q || String(r.recordNo) === q.replace(/^#/, "") || `${r.title} ${r.titleB || ""}`.toLowerCase().includes(q);
    const albums = new Map(); rs.filter((r) => r.albumId).forEach((r) => { if (!albums.has(r.albumId)) albums.set(r.albumId, []); albums.get(r.albumId).push(r); });
    el.append(h("div", { class: "row" }, h("input", { type: "text", placeholder: "search title or #number", style: "width:220px", "data-testid": "shelf-search", value: S.shelfQ, oninput: (e) => { S.shelfQ = e.target.value; drawShelf(); } }), h("span", { class: "mono" }, `${rs.length} records pressed${q ? ` · ${rs.filter(hit).length} hits` : ""}`), h("span", { class: "grow" }), h("button", { class: "btn sm primary", "data-testid": "backup-start", onclick: backup }, "⬇ BACKUP ALL RECORDS (.ZIP)"), h("button", { class: "btn sm", "data-testid": "restore-start", onclick: () => $("#restore-file").click() }, "⬆ RESTORE")));
    if (albums.size) { const wrap = h("div", { style: "margin:8px 0" }); for (const [id, list] of albums) { list.sort((a, b) => (a.albumIndex || 0) - (b.albumIndex || 0)); const name = list[0].title.replace(/\s+\d+\/\d+$/, ""); wrap.append(h("div", { class: "row" }, h("button", { class: "btn sm" + (S.shelfFocus === id ? " on" : ""), "data-testid": `shelf-album-${id}`, onclick: () => { S.shelfFocus = S.shelfFocus === id ? null : id; drawShelf(); } }, `ALBUM · ${name}${S.shelfFocus === id ? " ✕" : ""}`), list.map((r, i) => h("span", { class: "pill", style: `border-left-color:${GEOM.ALBUM_COLOURS[(r.albumIndex - 1) % 10]}`, onclick: () => openRecord(r.id) }, `#${r.recordNo} · ${r.albumIndex}/${r.albumCount}`)), h("button", { class: "btn sm teal", onclick: () => albumZip(id) }, "ZIP"), h("button", { class: "btn sm", onclick: () => sleeveSheet(id) }, "SLEEVES"))); } el.append(wrap); }
    const shelf = h("div", { class: "shelfwrap" }); rs.slice().sort((a, b) => (a.recordNo || 0) - (b.recordNo || 0)).forEach((r) => { const lit = (!S.shelfFocus || r.albumId === S.shelfFocus) && hit(r); shelf.append(h("button", { class: "rec" + (lit ? "" : " dim") + (S.result && S.result.id === r.id ? " open" : ""), "data-testid": `shelf-record-${r.recordNo}`, title: `${r.title}${r.twoSided ? " / " + r.titleB : ""} — click to open`, style: r.albumId ? `background:${GEOM.ALBUM_COLOURS[((r.albumIndex || 1) - 1) % 10]}` : "", onclick: () => openRecord(r.id), oncontextmenu: async (e) => { e.preventDefault(); if (confirm(`Delete record #${r.recordNo} "${r.title}"?`)) { await STORE.del("records", r.id); loadShelf(); } } }, r.recordNo, r.albumId ? h("small", {}, `${r.albumIndex}/${r.albumCount}`) : null)); });
    el.append(shelf, h("div", { class: "hint" }, "Click a record to open it · right-click to delete · album discs share a colour with their sleeve cards."));
  }
  async function openRecord(id) { const r = await STORE.get("records", id); if (!r) return; S.result = r; S.title = r.title; S.titleB = r.titleB || ""; S.twoSided = !!r.twoSided; S.thickness = r.thickness; S.pinRadius = r.pinRadius; S.dedHeight = r.dedHeight; S.dedFont = r.dedFont; S.voices = r.voices; S.roll = r.roll; S.analysis = { partition: r.partition, noteCount: r.noteCount, exact: r.exact, adjusted: r.adjusted, offset: r.offset, notesUsed: r.notesUsed, duration: r.duration }; S.analysisB = r.partitionB ? { partition: r.partitionB, noteCount: 0, exact: 0, adjusted: 0, offset: 0, notesUsed: [] } : null; S.side = "a"; $("#title").value = S.title; $("#titleb").value = S.titleB; settings(); $("#sideb-wrap").classList.toggle("hidden", !S.twoSided); $("#side-seg").classList.toggle("hidden", !S.twoSided); drawGrid(); showResult(r); drawShelf(); window.scrollTo({ top: 0, behavior: "smooth" }); }
  async function backup() { busy("Packing every record…"); try { const rs = await STORE.all("records"), albums = await STORE.all("albums"), settings = await STORE.all("settings"); const files = [], index = []; for (const r of rs) { const stem = `${r.recordNo}-${STORE.safeName(r.title)}-${r.id.slice(0, 6)}`; const { stl, scad, fpr, ...meta } = r; files.push([`records/${stem}/${stem}.stl`, stl], [`records/${stem}/${stem}.scad`, scad], [`records/${stem}/${stem}.fpr`, fpr], [`records/${stem}/${stem}-label.svg`, GEOM.labelCard(r, r.albumIndex ? [r.albumIndex, r.albumCount] : null)], [`records/${stem}/${stem}.json`, JSON.stringify(meta, null, 1)]); index.push(`#${r.recordNo}  ${r.title}  —  records/${stem}/`); } files.push(["albums.json", JSON.stringify(albums, null, 1)], ["settings.json", JSON.stringify(settings, null, 1)], ["README.txt", `Fisher-Price Record Maker backup — ${new Date().toISOString()}\n${FP.DEDICATION} · © 2026 Russ Campbell\n${rs.length} records, ${albums.length} albums. Restore with the RESTORE button (pick this ZIP).\n\n${index.join("\n")}\n`]); STORE.download(await STORE.zip(files), `fisher-price-records-backup-${new Date().toISOString().slice(0, 10)}.zip`); toast(`Backup: ${rs.length} records`); } catch (e) { toast("Backup failed: " + e.message, true); } finally { busy(null); } }
  // minimal ZIP reader for restore (STORE-method zips written by this app)
  async function restore(file) { busy("Restoring…"); try { const buf = await file.arrayBuffer(), dv = new DataView(buf), u8 = new Uint8Array(buf), dec = new TextDecoder(); let p = 0, n = 0; const metas = new Map(), blobs = new Map();
      while (p + 30 <= u8.length && dv.getUint32(p, true) === 0x04034b50) { const comp = dv.getUint16(p + 8, true), size = dv.getUint32(p + 18, true), nl = dv.getUint16(p + 26, true), xl = dv.getUint16(p + 28, true); const name = dec.decode(u8.slice(p + 30, p + 30 + nl)); const data = u8.slice(p + 30 + nl + xl, p + 30 + nl + xl + size); p += 30 + nl + xl + size; if (comp !== 0) continue; if (name.endsWith(".json") && name.startsWith("records/")) metas.set(name.replace(/\.json$/, ""), JSON.parse(dec.decode(data))); else if (name.startsWith("records/")) blobs.set(name, data); else if (name === "albums.json") for (const a of JSON.parse(dec.decode(data))) await STORE.put("albums", a); else if (name === "settings.json") for (const s of JSON.parse(dec.decode(data))) await STORE.put("settings", s); }
      for (const [stem, meta] of metas) { const rec = { ...meta, stl: new Blob([blobs.get(`${stem}.stl`) || new Uint8Array()], { type: "model/stl" }), scad: dec.decode(blobs.get(`${stem}.scad`) || new Uint8Array()), fpr: dec.decode(blobs.get(`${stem}.fpr`) || new Uint8Array()) }; await STORE.put("records", rec); n++; }
      toast(`Restored ${n} records`); await loadShelf(); } catch (e) { toast("Restore failed: " + e.message, true); } finally { busy(null); } }

  // ---------- test-disc notes → default voices ----------
  async function testNotes() { const el = $("#testnotes"); el.innerHTML = ""; const d = (await STORE.settings.get("defaults", null)) || {}; let pick = d.voices || null; const note = h("textarea", { rows: 2, placeholder: "e.g. two-note section rang clean, triads buzzed on the low tines", "data-testid": "test-result-note" }, d.note || ""); const segEl = h("div", { class: "seg" }); const draw = () => { segEl.innerHTML = ""; [[1, "ONE"], [2, "TWO"], [3, "THREE"]].forEach(([v, l]) => segEl.append(h("button", { class: pick === v ? "on" : "", "data-testid": `test-result-${v}`, onclick: () => { pick = v; draw(); } }, l))); }; draw();
    el.append(h("div", { class: "mono" }, "AFTER PRINTING the chord test disc — which section played cleanly?"), h("div", { class: "row" }, segEl, h("button", { class: "btn sm teal", "data-testid": "test-result-save", onclick: async () => { if (!pick) return; await STORE.settings.set("defaults", { voices: pick, note: note.value, testedAt: new Date().toISOString() }); S.voices = pick; settings(); toast(`Default "notes at once" = ${["", "ONE", "TWO", "THREE"][pick]}`); testNotes(); } }, "SAVE AS DEFAULT")), note, d.voices ? h("div", { class: "hint", "data-testid": "test-result-saved" }, `Default: ${["", "ONE", "TWO", "THREE"][d.voices]} at once · saved ${new Date(d.testedAt).toLocaleDateString()}${d.note ? ` · “${d.note}”` : ""}`) : null); }

  // ---------- boot ----------
  async function boot() {
    splash(); soundCheck();
    const d = await STORE.settings.get("defaults", null); if (d && d.voices) S.voices = d.voices;
    settings(); renderTracks(); drawGrid(); showResult(null); drawAlbum(); testNotes(); loadShelf();
    const lib = $("#library"); FP.LIBRARY.forEach(([t], i) => lib.append(h("div", { class: "row" }, h("button", { class: "btn sm tune-play", id: `tune-play-${i}`, "data-testid": `library-play-${i}`, onclick: () => playTune(i) }, "▶"), h("button", { class: "btn sm grow", style: "justify-content:flex-start", "data-testid": `library-${i}`, onclick: () => pickTune(i) }, t))));
    $("#file").onchange = (e) => e.target.files[0] && loadFile(e.target.files[0]);
    document.body.addEventListener("dragover", (e) => e.preventDefault()); document.body.addEventListener("drop", (e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) loadFile(f); });
    $("#title").oninput = (e) => { S.title = e.target.value; }; $("#titleb").oninput = (e) => { S.titleB = e.target.value; };
    $("#start").oninput = (e) => { S.start = Number(e.target.value); $("#start-val").textContent = `${S.start.toFixed(1)}s`; }; $("#start").onchange = autoFit;
    $("#grid").addEventListener("pointerdown", gridClick); window.addEventListener("resize", () => drawGrid());
    $("#play").onclick = togglePlay; $("#review-btn").onclick = reviewWav; $("#press").onclick = () => press(); $("#clear").onclick = () => { setPart(S.comb.notes.map(() => Array(FP.MAX_BEAT).fill(false))); drawGrid(); };
    $("#testdisc").onclick = testDisc; $("#album-plan").onclick = planAlbum; $("#restore-file").onchange = (e) => e.target.files[0] && restore(e.target.files[0]);
    $$("#side-seg button").forEach((b) => (b.onclick = () => { S.side = b.dataset.side; $$("#side-seg button").forEach((x) => x.classList.toggle("on", x === b)); drawGrid(); }));
    GEOM.ready(() => {}).then(() => fontPreviews()).catch(() => {});
  }
  document.addEventListener("DOMContentLoaded", boot);
})();
