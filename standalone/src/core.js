// ===== core.js — comb, MIDI parsing, grid mapping (port of backend/fisher_price.py) =====
const FP = (() => {
  const R_STOCK = 60.58, O_DRIVE = 21.8, R_DRIVE = 1.55, H_INSET = 1.0, R_INSET = 25.6, H_GROOVE = 1.2, OVERLAP = 0.2;
  const R_CENTER = 3.22, HEAD_OFFSET = 2.0, R_PIN = 0.9, PIN_BASE_RATIO = 2.0, PIN_BASE_MAX = 1.9, PIN_SINK = 0.5;
  const GROOVE_INNERS = [28.15, 30.89, 33.71, 36.425, 39.225, 42, 44.825, 47.555, 50.315, 53.11, 55.9];
  const FACTORY_TRACKS = [67, 72, 74, 76, 79, 81, 83, 84, 84, 86, 86, 88, 88, 89, 89, 91, 91, 93, 93, 95, 96, 98];
  const TRACK_RADIUS = [28.65, 29.65, 31.39, 32.39, 34.21, 35.21, 36.925, 37.925, 39.725, 40.725, 42.5, 43.5, 45.325, 46.325, 48.055, 49.055, 50.815, 51.815, 53.61, 54.61, 56.4, 57.4];
  const MAX_BEAT = 86, TRACKS_COUNT = 22, MIN_PIN_ARC_MM = 2.0, LEAN_BEATS = 4, TEMPO_PENALTY = 12, DRUM_CHANNEL = 9;
  const REAL_PITCH_OFFSET = -4, RENDER_RATE = 8000;
  const DEDICATION = "Dedicated To My Fiancée Barbara", DED_R = 12.0, DED_H = 2.4, DED_ARC = 240, DED_CENTRE = 0;
  const LABEL_R = 16.3, LABEL_MAX_H = 4.6, LABEL_MAX_ARC = 300, ARC_CENTRE = Math.PI, MARK_R = 8.5, MARK_H = 4.0, H_TEXT = 0.6;
  const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const SEMI = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const noteName = (m) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;
  const noteToMidi = (s) => { const m = /^([A-Ga-g])([#b♯♭]?)(-?\d)$/.exec(String(s).trim()); if (!m) return null; const acc = m[2] === "#" || m[2] === "♯" ? 1 : m[2] ? -1 : 0; return (Number(m[3]) + 1) * 12 + SEMI[m[1].toUpperCase()] + acc; };
  const pinBase = (d) => Math.round(Math.min(PIN_BASE_MAX, PIN_BASE_RATIO * d) * 1000) / 1000;

  class Comb {
    constructor(tracks) {
      if (tracks.length !== TRACKS_COUNT) throw new Error("a comb has 22 tines");
      this.tracks = tracks.map(Number);
      this.notes = [...new Set(this.tracks)].sort((a, b) => a - b);
      this.tines = this.notes.map((n) => this.tracks.map((t, i) => (t === n ? i : -1)).filter((i) => i >= 0));
      this.twins = new Set(this.tines.map((g, i) => (g.length > 1 ? i : -1)).filter((i) => i >= 0));
    }
    get tones() { return this.notes.length; }
    get factory() { return this.tracks.join() === FACTORY_TRACKS.join(); }
  }
  const DEFAULT_COMB = new Comb(FACTORY_TRACKS);

  // ---------- Standard MIDI file parser ----------
  function parseMidi(buf) {
    const d = new DataView(buf), u8 = new Uint8Array(buf);
    let p = 0;
    const str = (n) => { let s = ""; for (let i = 0; i < n; i++) s += String.fromCharCode(u8[p + i]); p += n; return s; };
    const u32 = () => { const v = d.getUint32(p); p += 4; return v; };
    const u16 = () => { const v = d.getUint16(p); p += 2; return v; };
    const vlq = () => { let v = 0, b; do { b = u8[p++]; v = (v << 7) | (b & 0x7f); } while (b & 0x80); return v; };
    if (str(4) !== "MThd") throw new Error("Not a MIDI file");
    const hlen = u32(); const fmt = u16(), ntr = u16(), div = u16(); p += hlen - 6;
    const tracks = [];
    for (let t = 0; t < ntr && p < u8.length; t++) {
      if (str(4) !== "MTrk") break;
      const len = u32(), end = p + len; let tick = 0, status = 0; const ev = []; let name = "", program = null, channels = new Set();
      while (p < end) {
        tick += vlq(); let b = u8[p];
        if (b === 0xff) { p++; const type = u8[p++]; const l = vlq(); const s = p; p += l;
          if (type === 0x51) ev.push({ tick, tempo: (u8[s] << 16) | (u8[s + 1] << 8) | u8[s + 2] });
          else if (type === 0x03 && !name) name = String.fromCharCode(...u8.slice(s, p));
          continue; }
        if (b === 0xf0 || b === 0xf7) { p++; p += vlq(); continue; }
        if (b & 0x80) { status = b; p++; }
        const hi = status & 0xf0, ch = status & 0x0f;
        if (hi === 0x90 || hi === 0x80) { const n = u8[p++], v = u8[p++]; if (hi === 0x90 && v > 0) { ev.push({ tick, note: n, ch }); channels.add(ch); } }
        else if (hi === 0xc0) { program = u8[p++]; if (program !== null) channels.add(ch); }
        else if (hi === 0xd0) p += 1; else p += 2;
      }
      p = end; tracks.push({ ev, name, program, channels });
    }
    const tempos = tracks.flatMap((t) => t.ev.filter((e) => e.tempo)).sort((a, b) => a.tick - b.tick);
    if (!tempos.length || tempos[0].tick > 0) tempos.unshift({ tick: 0, tempo: 500000 });
    const toSec = (tick) => { let s = 0, lt = 0, tempo = tempos[0].tempo; for (const te of tempos) { if (te.tick > tick) break; s += ((te.tick - lt) * tempo) / div / 1e6; lt = te.tick; tempo = te.tempo; } return s + ((tick - lt) * tempo) / div / 1e6; };
    const all = []; let length = 0;
    tracks.forEach((tr, ti) => tr.ev.forEach((e) => { if (e.note !== undefined) { const t = toSec(e.tick); all.push([t, e.note, e.ch, ti]); if (t > length) length = t; } }));
    all.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    return { tracks, events: all, length: length + 1 };
  }
  const GM = "Grand Piano,Bright Piano,Electric Grand,Honky-tonk Piano,Electric Piano 1,Electric Piano 2,Harpsichord,Clavinet,Celesta,Glockenspiel,Music Box,Vibraphone,Marimba,Xylophone,Tubular Bells,Dulcimer,Drawbar Organ,Percussive Organ,Rock Organ,Church Organ,Reed Organ,Accordion,Harmonica,Tango Accordion,Nylon Guitar,Steel Guitar,Jazz Guitar,Clean Guitar,Muted Guitar,Overdriven Guitar,Distortion Guitar,Guitar Harmonics,Acoustic Bass,Finger Bass,Pick Bass,Fretless Bass,Slap Bass 1,Slap Bass 2,Synth Bass 1,Synth Bass 2,Violin,Viola,Cello,Contrabass,Tremolo Strings,Pizzicato Strings,Harp,Timpani,String Ensemble 1,String Ensemble 2,Synth Strings 1,Synth Strings 2,Choir Aahs,Voice Oohs,Synth Voice,Orchestra Hit,Trumpet,Trombone,Tuba,Muted Trumpet,French Horn,Brass Section,Synth Brass 1,Synth Brass 2,Soprano Sax,Alto Sax,Tenor Sax,Baritone Sax,Oboe,English Horn,Bassoon,Clarinet,Piccolo,Flute,Recorder,Pan Flute,Blown Bottle,Shakuhachi,Whistle,Ocarina,Square Lead,Sawtooth Lead,Calliope Lead,Chiff Lead,Charang Lead,Voice Lead,Fifths Lead,Bass + Lead,New Age Pad,Warm Pad,Polysynth Pad,Choir Pad,Bowed Pad,Metallic Pad,Halo Pad,Sweep Pad,Rain,Soundtrack,Crystal,Atmosphere,Brightness,Goblins,Echoes,Sci-Fi,Sitar,Banjo,Shamisen,Koto,Kalimba,Bagpipe,Fiddle,Shanai,Tinkle Bell,Agogo,Steel Drums,Woodblock,Taiko Drum,Melodic Tom,Synth Drum,Reverse Cymbal,Guitar Fret Noise,Breath Noise,Seashore,Bird Tweet,Telephone,Helicopter,Applause,Gunshot".split(",");

  // track summaries + melody confidence (how melody-like each track is)
  function scanTracks(mid) {
    const out = [];
    mid.tracks.forEach((tr, ti) => {
      const notes = mid.events.filter((e) => e[3] === ti && e[2] !== DRUM_CHANNEL);
      const drums = mid.events.some((e) => e[3] === ti && e[2] === DRUM_CHANNEL);
      if (!notes.length) return;
      const pitches = notes.map((e) => e[1]);
      const mean = pitches.reduce((a, b) => a + b, 0) / pitches.length;
      const times = new Map(); notes.forEach((e) => { const k = Math.round(e[0] * 20); times.set(k, (times.get(k) || 0) + 1); });
      const poly = [...times.values()].filter((c) => c > 1).length / times.size;
      const span = Math.max(...pitches) - Math.min(...pitches);
      const dur = notes[notes.length - 1][0] - notes[0][0] || 1;
      const density = notes.length / dur;
      let conf = 50 + Math.max(-25, Math.min(25, (mean - 60) * 1.2)) - poly * 40 - (span > 30 ? 10 : 0) - (density > 8 ? 15 : density < 0.5 ? 10 : 0);
      if (/melod|lead|vocal|voice|tune|sing/i.test(tr.name)) conf += 15;
      if (/bass|drum|perc|pad|chord|accomp|rhythm/i.test(tr.name)) conf -= 20;
      out.push({ index: ti, name: tr.name || `Track ${ti + 1}`, instrument: tr.program !== null ? GM[tr.program] || "" : "", notes: notes.length, mean: Math.round(mean), range: [noteName(Math.min(...pitches)), noteName(Math.max(...pitches))], poly: Math.round(poly * 100), drums, confidence: Math.max(1, Math.min(99, Math.round(conf))) });
    });
    out.sort((a, b) => b.confidence - a.confidence);
    return out;
  }
  function skyline(events, bucket = 0.05) { const m = new Map(); for (const [t, n] of events) { const k = Math.round(t / bucket); if (!m.has(k) || m.get(k)[1] < n) m.set(k, [t, n]); } return [...m.values()].sort((a, b) => a[0] - b[0]); }
  function midiEvents(mid, duration, start = 0, tracks = null, sky = false) {
    const sel = tracks && tracks.length ? new Set(tracks) : null;
    let ev = mid.events.filter((e) => e[2] !== DRUM_CHANNEL && e[0] >= start && e[0] < start + duration && (!sel || sel.has(e[3]))).map((e) => [e[0] - start, e[1]]);
    if (sky && ev.length) ev = skyline(ev);
    return ev;
  }

  // ---------- transposition ----------
  function chooseTransposition(notes, comb = DEFAULT_COMB, tol = 0.15) {
    const allowed = new Set(comb.notes), lo = comb.notes[0], hi = comb.notes[comb.notes.length - 1], n = notes.length;
    if (!n) return 0;
    const fit = (o) => { let ex = 0, dist = 0; for (const x of notes) { if (allowed.has(x + o)) ex++; dist += Math.min(...comb.notes.map((a) => Math.abs(x + o - a))); } return [ex, dist]; };
    if (fit(0)[0] >= n * (1 - tol)) return 0;
    let best = null;
    const gt = (a, b) => { for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] > b[i]; return false; };
    for (let o = -36; o <= 36; o++) { const avg = notes.reduce((a, b) => a + b, 0) / n + o; if (avg < lo - 6 || avg > hi + 6) continue; const [ex, dist] = fit(o); const sc = [ex, o % 12 === 0 ? 1 : 0, -Math.abs(o), -dist]; if (!best || gt(sc, best[0])) best = [sc, o]; }
    if (!best) return 0;
    for (const o of [-12, 12, -24, 24]) if (fit(o)[0] >= best[0][0] - Math.max(1, Math.floor(n * tol))) return o;
    return best[1];
  }
  function transpositionCandidates(notes, comb = DEFAULT_COMB, k = 4) {
    if (!notes.length) return [0];
    const allowed = new Set(comb.notes), lo = comb.notes[0], hi = comb.notes[comb.notes.length - 1];
    const scored = [];
    for (let o = -36; o <= 36; o++) { let ex = 0, inside = 0; for (const n of notes) { if (allowed.has(n + o)) ex++; if (n + o >= lo && n + o <= hi) inside++; } scored.push([ex + 0.5 * inside, o % 12 === 0 ? 1 : 0, -Math.abs(o), o]); }
    scored.sort((a, b) => b[0] - a[0] || b[1] - a[1] || b[2] - a[2] || b[3] - a[3]);
    const out = [chooseTransposition(notes, comb)];
    for (const s of scored) { if (!out.includes(s[3])) out.push(s[3]); if (out.length >= k) break; }
    return out;
  }
  const snapNote = (m, comb) => comb.notes.reduce((b, a) => (Math.abs(a - m) < Math.abs(b - m) ? a : b));

  // ---------- placement rules ----------
  function gapBeats(tone, comb, beats) { const r = Math.min(...comb.tines[tone].map((t) => TRACK_RADIUS[t])); const gap = Math.max(1, Math.ceil(MIN_PIN_ARC_MM / ((2 * Math.PI * r) / beats))); return comb.tines[tone].length === 1 ? Math.max(gap, 2) : gap; }
  function canPlace(p, tone, b, comb, mono = true) {
    const beats = p[0].length;
    if (mono && p.some((row) => row[b])) return false;
    if (!mono && p[tone][b]) return false;
    const row = p[tone], g = gapBeats(tone, comb, beats);
    for (let d = 1; d < g; d++) if (row[(b - d + beats) % beats] || row[(b + d) % beats]) return false;
    return true;
  }
  function nearestFree(p, tone, b, comb, mono = true, reach = 8) { const beats = p[0].length; for (let d = 1; d <= reach; d++) for (const nb of [b + d, b - d]) if (nb >= 0 && nb < beats && canPlace(p, tone, nb, comb, mono)) return nb; return null; }
  function slide(p, tone, b, comb, prefer, mono = true) {
    const beats = p[0].length; p[tone][b] = false;
    const c = []; for (let d = 1; d < LEAN_BEATS; d++) c.push(b + prefer * d);
    for (let d = LEAN_BEATS; d < beats; d++) c.push(b + prefer * d, b - prefer * d);
    for (let d = 1; d < LEAN_BEATS; d++) c.push(b - prefer * d);
    for (const nb of c) if (nb >= 0 && nb < beats && canPlace(p, tone, nb, comb, mono)) { p[tone][nb] = true; return true; }
    return false;
  }
  function limitVoices(p, voices, comb, roll = "before", reach = 4) {
    const beats = p[0].length, prefer = roll === "after" ? 1 : -1, load = []; for (let b = 0; b < beats; b++) load.push(p.reduce((s, r) => s + (r[b] ? 1 : 0), 0));
    let moved = 0, dropped = 0;
    for (let b = 0; b < beats; b++) {
      const hits = []; p.forEach((r, t) => { if (r[b]) hits.push(t); });
      if (hits.length <= voices) continue;
      const keep = new Set([hits[hits.length - 1]].concat(voices >= 2 ? [hits[0]] : []));
      const mid = (hits[0] + hits[hits.length - 1]) / 2;
      hits.slice(1, -1).sort((x, y) => Math.abs(x - mid) - Math.abs(y - mid)).slice(0, Math.max(0, voices - 2)).forEach((t) => keep.add(t));
      for (const t of hits) { if (keep.has(t)) continue; p[t][b] = false; load[b]--; let placed = false;
        for (let d = 1; d <= reach && !placed; d++) for (const nb of [b + prefer * d, b - prefer * d]) if (nb >= 0 && nb < beats && load[nb] < voices && canPlace(p, t, nb, comb, false)) { p[t][nb] = true; load[nb]++; placed = true; break; }
        if (placed) moved++; else dropped++; }
    }
    return [moved, dropped];
  }
  function staggerPartition(p, comb, roll = "before") { const beats = p[0].length, prefer = roll === "after" ? 1 : -1; let moved = 0; for (let b = 0; b < beats; b++) { const hits = []; p.forEach((r, t) => { if (r[b]) hits.push(t); }); for (const t of hits.slice(0, -1)) { slide(p, t, b, comb, prefer); moved++; } } return moved; }
  function makePlayable(p, comb) { let slid = 0, dropped = 0; const beats = p[0].length; for (let tone = 0; tone < p.length; tone++) { const row = p[tone], gap = gapBeats(tone, comb, beats); if (gap < 2) continue; for (let b = 0; b < beats; b++) { let clash = false; for (let d = 1; d < gap; d++) if (row[(b - d + beats) % beats]) clash = true; if (row[b] && clash) { if (slide(p, tone, b, comb, 1)) slid++; else dropped++; } } } return [slid, dropped]; }

  function eventsToRecord(events, duration, autoTranspose = true, manualOffset = 0, comb = DEFAULT_COMB, stagger = true, roll = "before", voices = 16) {
    const p = comb.notes.map(() => Array(MAX_BEAT).fill(false));
    const raw = events.map((e) => e[1]);
    const offset = raw.length ? (autoTranspose ? chooseTransposition(raw, comb) : manualOffset) : 0;
    let exact = 0, adjusted = 0, merged = 0, staggered = 0; const used = new Set();
    for (const [t, n] of [...events].sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
      const m = n + offset, on = comb.notes.includes(m), snapped = on ? m : snapNote(m, comb);
      if (on) exact++; else adjusted++;
      const tone = comb.notes.indexOf(snapped);
      let beat = Math.max(0, Math.min(MAX_BEAT - 1, duration > 0 ? Math.round((t / duration) * MAX_BEAT) : 0));
      if (p[tone][beat]) { const nb = nearestFree(p, tone, beat, comb, stagger); if (nb === null) { merged++; continue; } beat = nb; staggered++; }
      p[tone][beat] = true; used.add(snapped);
    }
    const partitionMidi = p.map((r) => [...r]);
    let dropped = 0;
    if (stagger) staggered += staggerPartition(p, comb, roll); else { const [mv, dr] = limitVoices(p, voices, comb, roll); staggered += mv; dropped = dr; }
    const [slid, dr2] = makePlayable(p, comb); dropped += dr2; staggered += slid;
    return { partition: p, partitionMidi, dropped, offset, exact, adjusted, merged, staggered, notesUsed: [...used].sort((a, b) => a - b), noteCount: events.length };
  }

  // ---------- fit scoring + tempo auto-fit ----------
  function compareFit(events, offset, p, duration, revSeconds, comb) {
    if (!events.length) return { score: 0, matched: 0, timingMs: 0, tempo: duration / revSeconds };
    const bs = duration / MAX_BEAT; let matched = 0, err = 0;
    for (const [t, n] of events) { const m = n + offset, tone = comb.notes.indexOf(comb.notes.includes(m) ? m : snapNote(m, comb)); const b = Math.max(0, Math.min(MAX_BEAT - 1, Math.round(t / bs))); let hit = -1; for (let d = 0; d <= 2 && hit < 0; d++) for (const nb of [b + d, b - d]) if (nb >= 0 && nb < MAX_BEAT && p[tone][nb]) { hit = nb; break; } if (hit >= 0) { matched++; err += Math.abs(hit * bs - t); } }
    const score = Math.max(0, 100 * (matched / events.length) - 0.3 * ((err / Math.max(1, matched)) / bs) * 100 / 3 - TEMPO_PENALTY * Math.abs(duration / revSeconds - 1));
    return { score: Math.round(score * 10) / 10, matched, timingMs: Math.round((err / Math.max(1, matched)) * 1000), tempo: Math.round((duration / revSeconds) * 1000) / 1000 };
  }
  function autoFit(mid, start, revSeconds, comb, roll, autoTranspose, manualOffset, tracks, sky, chords, voices, maxTries = 1500) {
    const tempoRange = 0.35, nudge = 0.5, dLo = revSeconds * (1 - tempoRange), dHi = revSeconds * (1 + tempoRange), base = Math.max(0, start - nudge);
    const all = midiEvents(mid, dHi + 2 * nudge, base, tracks, sky);
    if (!all.length) { const rec = eventsToRecord([], revSeconds, autoTranspose, manualOffset, comb, true, roll); rec.events = []; rec.fit = { score: 0, tries: 0, duration: revSeconds, start, tempo: 1, matched: 0, timingMs: 0, offset: 0 }; return rec; }
    const notes = all.map((e) => e[1]);
    const offsets = autoTranspose ? transpositionCandidates(notes, comb) : [manualOffset];
    const offset = offsets[0];
    const tones = notes.map((n) => { const m = n + offset; return comb.notes.indexOf(comb.notes.includes(m) ? m : snapNote(m, comb)); });
    const single = comb.notes.map((_, t) => comb.tines[t].length === 1);
    const quick = (delta, dur) => { const bs = dur / MAX_BEAT; const keys = new Set(); const perBeat = new Map(); let n = 0, err = 0; const list = [];
      for (let i = 0; i < all.length; i++) { const tt = all[i][0] - delta; if (tt < 0 || tt >= dur) continue; n++; const b = Math.max(0, Math.min(MAX_BEAT - 1, Math.round(tt / bs))); err += Math.abs(b * bs - tt) / bs; const k = tones[i] * MAX_BEAT + b; if (!keys.has(k)) { keys.add(k); list.push(k); perBeat.set(b, (perBeat.get(b) || 0) + 1); } }
      if (!n) return -1; const merged = n - keys.size; let ch = 0; perBeat.forEach((c) => { ch += c - 1; }); list.sort((a, b) => a - b); let rep = 0; for (let i = 1; i < list.length; i++) { const kt = Math.floor(list[i] / MAX_BEAT), kb = list[i] % MAX_BEAT, pt = Math.floor(list[i - 1] / MAX_BEAT), pb = list[i - 1] % MAX_BEAT; if (kt === pt && kb - pb === 1 && single[kt]) rep++; }
      return 100 * (1 - (0.5 * (merged + ch + rep)) / n - 0.3 * (err / n)) - TEMPO_PENALTY * Math.abs(dur / revSeconds - 1); };
    const deltas = []; for (let d = 0; d <= 2 * nudge + 1e-9; d += 0.05) deltas.push(d);
    const refine = Math.min(60, Math.max(10, Math.floor(maxTries / 10)));
    const nDur = Math.max(1, Math.floor((maxTries - 2 * refine - 4) / deltas.length));
    const durs = []; for (let i = 0; i < nDur; i++) durs.push(dLo + ((dHi - dLo) * i) / Math.max(1, nDur - 1));
    const coarse = []; for (const d of deltas) for (const u of durs) coarse.push([quick(d, u), d, u]);
    coarse.sort((a, b) => b[0] - a[0]); let tries = coarse.length;
    const full = (delta, dur, off = offset) => { const ev = all.filter((e) => e[0] - delta >= 0 && e[0] - delta < dur).map((e) => [e[0] - delta, e[1]]); const rec = eventsToRecord(ev, dur, false, off, comb, !chords, roll, voices); const fit = compareFit(ev, off, rec.partition, dur, revSeconds, comb); return [fit.score, delta, dur, rec, fit, ev]; };
    let best = null;
    for (const [, d, u] of coarse.slice(0, refine)) { const c = full(d, u); tries++; if (!best || c[0] > best[0]) best = c; if (best[0] >= 99.5) break; }
    if (best[0] < 99.5) { const [, d0, u0] = best; for (let dd = -0.05; dd <= 0.051; dd += 0.01) for (let du = -0.1; du <= 0.101; du += 0.02) { const d = d0 + dd, u = u0 + du; if (d >= 0 && d <= 2 * nudge && u >= dLo && u <= dHi) { const c = full(d, u); tries++; if (c[0] > best[0]) best = c; } } }
    for (const off of offsets.slice(1)) { const c = full(best[1], best[2], off); tries++; if (c[0] > best[0]) best = c; }
    const [, delta, dur, rec, fit, ev] = best;
    rec.events = ev.sort((a, b) => a[0] - b[0]);
    rec.fit = { ...fit, tries, duration: Math.round(dur * 100) / 100, start: Math.round((base + delta) * 100) / 100, offset: rec.offset };
    return rec;
  }
  function analyze(mid, duration, start, autoTranspose, manualOffset, comb, roll, tracks, sky, chords, voices) {
    const ev = midiEvents(mid, duration, start, tracks, sky);
    const rec = eventsToRecord(ev, duration, autoTranspose, manualOffset, comb, !chords, roll, voices);
    rec.events = ev; rec.duration = duration; rec.start = start; rec.notesUsedNames = rec.notesUsed.map(noteName);
    return rec;
  }
  function planSong(mid, comb, tracks, sky, duration, revSeconds, roll, autoTranspose, manualOffset, chords, voices) {
    const all = midiEvents(mid, 36000, 0, tracks, sky);
    if (!all.length) throw new Error("No playable notes in the selected tracks");
    const first = all[0][0], last = all[all.length - 1][0];
    let start = Math.max(0, first - 0.2), fit = null;
    if (duration <= 0) { const rec = autoFit(mid, start, revSeconds, comb, roll, autoTranspose, manualOffset, tracks, sky, chords, voices); fit = rec.fit; duration = fit.duration; start = fit.start; }
    const offset = autoTranspose ? (fit ? fit.offset : chooseTransposition(all.map((e) => e[1]), comb)) : manualOffset;
    const n = Math.max(1, Math.ceil((last - start + 0.01) / duration));
    const sides = []; for (let k = 0; k < n; k++) sides.push(analyze(mid, duration, start + k * duration, false, offset, comb, roll, tracks, sky, chords, voices));
    return { sides, duration, start, offset, fit, noteCount: sides.reduce((s, x) => s + x.noteCount, 0) };
  }

  // ---------- physical layout ----------
  function toPhysical(p, comb, overrides = {}) {
    const beats = p[0].length, part22 = Array.from({ length: TRACKS_COUNT }, () => Array(beats).fill(false));
    comb.tines.forEach((tracks, tone) => { const row = p[tone]; if (tracks.length === 1) { part22[tracks[0]] = [...row]; return; } let onSecond = false;
      row.forEach((on, i) => { if (!on) return; let slot = overrides[`${tone}-${i}`]; if (slot === undefined || slot === null) slot = onSecond ? 1 : 0; slot = Number(slot) % tracks.length; part22[tracks[slot]][i] = true; onSecond = slot === 0; }); });
    return part22;
  }
  function getPins(part22) { const pins = [], beats = part22[0].length, na = (2 * Math.PI) / beats; for (let tr = 0; tr < TRACKS_COUNT; tr++) { const r = TRACK_RADIUS[tr], wall = tr % 2 === 0 ? r - 0.5 : r + 0.5, dir = tr % 2 === 0 ? 1 : -1; for (let b = 0; b < beats; b++) if (part22[tr][b]) pins.push({ wall, angle: na * b - HEAD_OFFSET / r, dir }); } return pins; }

  function chordTestPartition(comb = DEFAULT_COMB) {
    const p = comb.notes.map(() => Array(MAX_BEAT).fill(false)); const melody = [3, 4, 5, 3, 2, 1], h2 = [[1], [2], [3], [1], [0], [0]], h3 = [[1, 0], [2, 0], [3, 1], [1, 0], [0, 1], [0, 3]];
    for (const [sec, extra] of [[2, null], [30, h2], [58, h3]]) melody.forEach((tone, i) => { const b = sec + i * 2; p[tone][b] = true; if (extra) extra[i].forEach((t) => { p[t][b] = true; }); });
    return p;
  }
  const LIBRARY = [
    ["Twinkle Twinkle Little Star", "C5 C5 G5 G5 A5 A5 G5:2 F5 F5 E5 E5 D5 D5 C5:2 G5 G5 F5 F5 E5 E5 D5:2 G5 G5 F5 F5 E5 E5 D5:2 C5 C5 G5 G5 A5 A5 G5:2 F5 F5 E5 E5 D5 D5 C5:2"],
    ["Au Clair de la Lune", "C5 C5 C5 D5 E5:2 D5:2 C5 E5 D5 D5 C5:4 C5 C5 C5 D5 E5:2 D5:2 C5 E5 D5 D5 C5:4 D5 D5 D5 D5 A4:2 A4:2 D5 C5 B4 A4 G4:4"],
    ["Humpty Dumpty", "E5 G5 G5 E5 C5 D5 E5:2 F5 A5 A5 F5 D5 E5 F5:2 G5 G5 G5 E5 C5 D5 E5:2 F5 F5 F5 D5 B4 C5 D5:2 E5 F5 G5 A5 G5 F5 E5:2 D5 E5 F5 G5 F5 E5 D5:2 E5 F5 G5 A5 G5 F5 E5 D5 C5:3"],
    ["Jack and Jill", "G5 G5 A5 A5 B5 B5 C6:2 B5 B5 A5 A5 G5:3 G5 G5 A5 A5 B5 B5 C6:2 B5 B5 A5 A5 G5:3 D5 D5 E5 F5 G5 G5 A5:2 B5 B5 A5 G5 A5:3 G5 G5 A5 B5 C6 C6 B5 A5 G5:3"],
    ["Oh Where Has My Little Dog Gone", "G5:2 E5 C5:2 E5 G5:3 G5:2 E5 C5:2 E5 G5:3 A5 A5 A5 G5:2 F5 E5 E5 E5 D5:3 G5:2 E5 C5:2 E5 G5:3 A5:2 B5 C6:2 B5 A5 G5 F5 E5 D5 C5:3"],
    ["London Bridge", "G5 A5 G5 F5 E5 F5 G5:2 D5 E5 F5:2 E5 F5 G5:2 G5 A5 G5 F5 E5 F5 G5:2 D5:2 G5:2 E5 C5:3"],
    ["Edelweiss", "E5 G5 D6:3 C6 G5 F5:3 E5 E5 E5 F5 G5 A5:3 G5:3 E5 G5 D6:3 C6 G5 F5:3 E5 G5 G5 A5 B5 C6:3 C6:3 D6 G5 G5 B5 A5 G5 E5 G5 C6:3 A5 D6 C6 D6:3 B5 D6:3 E5 G5 D6:3 C6 G5 F5:3 E5 G5 G5 A5 B5 C6:3 C6:3"],
    ["Children's Prayer", "E5 D5 C5 D5 E5 E5 E5:2 D5 D5 D5:2 E5 G5 G5:2 E5 D5 C5 D5 E5 E5 E5 E5 D5 D5 E5 D5 C5:3 G5 G5 F5 D5 E5 E5 E5:2 G5 G5 F5 D5 E5 E5 E5:2 E5 D5 C5 D5 E5 E5 E5 E5 D5 D5 E5 D5 C5:3"],
    ["Camptown Races", "G5 G5 E5 G5 A5 G5 E5:2 E5 D5:3 E5 D5:3 G5 G5 E5 G5 A5 G5 E5:2 D5 E5 D5 C5:3 C5 E5 G5:3 A5 C6 A5 G5:3 G5 G5 E5 G5 A5 G5 E5:2 D5 E5 D5 C5:3"],
    ["Hickory Dickory Dock", "E5 D5 C5 E5 D5 C5:2 G5 A5 G5 F5 E5 D5:2 E5 F5 G5 A5 B5 C6:2 B5 A5 G5 F5 E5 D5 C5:3 E5 D5 C5 E5 D5 C5:2 G5 A5 G5 F5 E5 D5 C5:3"],
  ];
  function melodyEvents(melody, duration) { const steps = melody.split(/\s+/).map((tok) => { const [name, len] = tok.split(":"); return [noteToMidi(name), Number(len || 1)]; }); const total = steps.reduce((s, x) => s + x[1], 0), k = (duration * 0.96) / total; let t = 0; return steps.map(([m, l]) => { const e = [t * k, m]; t += l; return e; }); }
  const toFpr = (p, title) => p.map((r) => r.map((x) => (x ? "+" : "-")).join("")).join("\n") + "\n" + (title || "Untitled") + "\n";

  return { R_STOCK, O_DRIVE, R_DRIVE, H_INSET, R_INSET, H_GROOVE, OVERLAP, R_CENTER, HEAD_OFFSET, R_PIN, PIN_SINK, pinBase, GROOVE_INNERS, FACTORY_TRACKS, TRACK_RADIUS, MAX_BEAT, TRACKS_COUNT, REAL_PITCH_OFFSET, RENDER_RATE,
    DEDICATION, DED_R, DED_H, DED_ARC, DED_CENTRE, LABEL_R, LABEL_MAX_H, LABEL_MAX_ARC, ARC_CENTRE, MARK_R, MARK_H, H_TEXT, noteName, noteToMidi, Comb, DEFAULT_COMB,
    parseMidi, scanTracks, midiEvents, chooseTransposition, transpositionCandidates, eventsToRecord, compareFit, autoFit, analyze, planSong, toPhysical, getPins, chordTestPartition, LIBRARY, melodyEvents, toFpr, canPlace, gapBeats };
})();
