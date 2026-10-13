// ===== audio.js — toy-voice synth, sequence player, 8 kHz WAV render =====
const AUDIO = (() => {
  let ctx = null, master = null; const watchers = new Set();
  const notify = () => watchers.forEach((f) => f());
  const getVolume = () => { const v = Number(localStorage.getItem("fp-volume")); return localStorage.getItem("fp-volume") === null || !Number.isFinite(v) ? 0.8 : v; };
  function engine() { if (!ctx) { ctx = new (window.AudioContext || window.webkitAudioContext)(); master = ctx.createGain(); master.gain.value = getVolume() * 1.5; master.connect(ctx.destination); ctx.onstatechange = notify; notify(); } if (ctx.state === "suspended") ctx.resume().then(notify, notify); return ctx; }
  ["pointerdown", "keydown", "touchend"].forEach((ev) => window.addEventListener(ev, () => engine(), { passive: true, capture: true }));
  function setVolume(v) { localStorage.setItem("fp-volume", String(v)); if (master) master.gain.setTargetAtTime(v * 1.5, ctx.currentTime, 0.02); notify(); }
  const PARTIALS = [[1, 1.0, 1.9], [2.0, 0.45, 1.0], [3.01, 0.22, 0.55], [4.16, 0.12, 0.28]];
  const midiToFreq = (m) => 440 * Math.pow(2, (m - 69) / 12);
  function pluck(dest, freq, when) {
    const c = engine(), out = c.createGain(); out.gain.value = 0.3; out.connect(dest);
    const ring = Math.min(1.8, Math.max(0.7, 700 / freq));
    for (const [ratio, g, decay] of PARTIALS) { const o = c.createOscillator(); o.type = "sine"; o.frequency.value = freq * ratio; const env = c.createGain(); env.gain.setValueAtTime(0.0001, when); env.gain.linearRampToValueAtTime(g, when + 0.003); env.gain.exponentialRampToValueAtTime(0.0001, when + decay * ring); o.connect(env); env.connect(out); o.start(when); o.stop(when + decay * ring + 0.05); }
    const noise = c.createBufferSource(), buf = c.createBuffer(1, 256, c.sampleRate), d = buf.getChannelData(0); for (let i = 0; i < 256; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / 256); noise.buffer = buf; const ng = c.createGain(); ng.gain.value = 0.15; noise.connect(ng); ng.connect(out); noise.start(when);
  }
  function channel() { const c = engine(), g = c.createGain(); g.connect(master); return { ctx: c, dest: g, close() { g.gain.cancelScheduledValues(c.currentTime); g.gain.setTargetAtTime(0, c.currentTime, 0.01); setTimeout(() => g.disconnect(), 80); } }; }
  // play one or more sides (partitions) at toy speed; onTick(sideIdx, beat) drives the playhead
  function playSides(sides, notes, revSeconds, onTick, onEnd, startBeat = 0) {
    const ch = channel(), t0 = ch.ctx.currentTime + 0.05, beatSec = revSeconds / FP.MAX_BEAT, gap = 0.8;
    let cursor = 0; const schedule = [];
    sides.forEach((p, si) => { p.forEach((row, tone) => row.forEach((on, b) => { if (!on) return; const t = cursor + b * beatSec - (si === 0 ? startBeat * beatSec : 0); if (t < 0) return; schedule.push([t, si, b]); pluck(ch.dest, midiToFreq(notes[tone] + FP.REAL_PITCH_OFFSET), t0 + t); })); cursor += revSeconds + gap - (si === 0 ? startBeat * beatSec : 0); });
    const total = cursor + 1.0; let raf, stopped = false;
    const tick = () => { if (stopped) return; const el = ch.ctx.currentTime - t0; if (el > total) { stop(); onEnd && onEnd(); return; } let acc = 0; for (let si = 0; si < sides.length; si++) { const len = revSeconds + gap - (si === 0 ? startBeat * beatSec : 0); if (el < acc + len) { const beat = Math.min(FP.MAX_BEAT - 1, Math.floor((el - acc) / beatSec) + (si === 0 ? startBeat : 0)); onTick(si, beat); break; } acc += len; } raf = requestAnimationFrame(tick); };
    const stop = () => { stopped = true; cancelAnimationFrame(raf); ch.close(); };
    tick();
    return { stop, duration: total };
  }
  function tap(midi) { const ch = channel(); pluck(ch.dest, midiToFreq(midi + FP.REAL_PITCH_OFFSET), ch.ctx.currentTime + 0.01); setTimeout(() => ch.close(), 2500); }
  function testTone() { [84, 88, 91].forEach((m, i) => setTimeout(() => tap(m), i * 230)); }
  // whole song as the toy plays it: 8 kHz mono 16-bit WAV
  function renderWav(sides, notes, revSeconds, rate = FP.RENDER_RATE, sideGap = 0.6) {
    const beatSec = revSeconds / FP.MAX_BEAT, onsets = []; let cursor = 0;
    for (const p of sides) { p.forEach((row, tone) => row.forEach((on, b) => { if (on) onsets.push([cursor + b * beatSec, notes[tone] + FP.REAL_PITCH_OFFSET]); })); cursor += revSeconds + sideGap; }
    const total = Math.floor((cursor + 1.5) * rate), audio = new Float32Array(total), n = Math.floor(1.2 * rate);
    const env = new Float32Array(n); for (let i = 0; i < n; i++) { const t = i / rate; env[i] = Math.exp(-t * 4.5) * (1 - Math.exp(-t * 400)); }
    for (const [when, midi] of onsets) { const f0 = midiToFreq(midi), i0 = Math.floor(when * rate), seg = Math.min(n, total - i0); if (seg <= 0) continue;
      for (let i = 0; i < seg; i++) { const t = i / rate; let v = 0; for (const [k, amp, dec] of [[1, 1.0, 1.0], [2.76, 0.35, 2.2], [5.4, 0.12, 3.5]]) if (f0 * k < rate / 2) v += amp * Math.sin(2 * Math.PI * f0 * k * t) * Math.exp(-t * dec * 2); audio[i0 + i] += v * env[i]; } }
    let peak = 0; for (const v of audio) peak = Math.max(peak, Math.abs(v)); peak = peak || 1;
    const buf = new ArrayBuffer(44 + total * 2), dv = new DataView(buf); const w = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); dv.setUint32(4, 36 + total * 2, true); w(8, "WAVE"); w(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, rate, true); dv.setUint32(28, rate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); w(36, "data"); dv.setUint32(40, total * 2, true);
    for (let i = 0; i < total; i++) dv.setInt16(44 + i * 2, Math.round((audio[i] / peak) * 0.85 * 32767), true);
    return new Blob([buf], { type: "audio/wav" });
  }
  const state = () => (ctx ? ctx.state : "idle"), sampleRate = () => (ctx ? ctx.sampleRate : 0), watch = (f) => { watchers.add(f); return () => watchers.delete(f); };
  return { engine, playSides, tap, testTone, renderWav, getVolume, setVolume, state, sampleRate, watch };
})();
