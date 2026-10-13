import { useCallback, useEffect, useRef, useState } from "react";
import { NOTES, MAX_BEAT, SIDE_GAP, REAL_PITCH_OFFSET, midiToFreq } from "../lib/fp";

// Music-box tine: strong fundamental, decaying inharmonic partials, soft pluck transient
const PARTIALS = [[1, 1.0, 1.9], [2.0, 0.45, 1.0], [3.01, 0.22, 0.55], [4.16, 0.12, 0.28]];
function pluck(ctx, dest, freq, when) {
  const out = ctx.createGain();
  out.gain.value = 0.3;
  out.connect(dest);
  const ring = Math.min(1.8, Math.max(0.7, 700 / freq));
  PARTIALS.forEach(([ratio, g, decay]) => {
    const o = ctx.createOscillator();
    o.type = "sine";
    o.frequency.value = freq * ratio;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, when);
    env.gain.linearRampToValueAtTime(g, when + 0.003);
    env.gain.exponentialRampToValueAtTime(0.0001, when + decay * ring);
    o.connect(env);
    env.connect(out);
    o.start(when);
    o.stop(when + decay * ring + 0.05);
  });
  const n = 256;
  const buf = ctx.createBuffer(1, n, ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / n);
  const noise = ctx.createBufferSource();
  noise.buffer = buf;
  const hp = ctx.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.value = 2500;
  const ng = ctx.createGain();
  ng.gain.value = 0.12;
  noise.connect(hp);
  hp.connect(ng);
  ng.connect(out);
  noise.start(when);
}

const newCtx = () => new (window.AudioContext || window.webkitAudioContext)();

// sequence: array of partitions played back to back (side A, then side B)
export function useMusicBox(sequence, revSeconds, loop) {
  const [playing, setPlaying] = useState(false);
  const [sideIdx, setSideIdx] = useState(0);
  const ctxRef = useRef(null);
  const startRef = useRef(0);
  const revRef = useRef(revSeconds);
  const timersRef = useRef([]);
  const tapCtxRef = useRef(null);
  const loopRef = useRef(loop);
  const playRef = useRef(null);
  loopRef.current = loop;

  const clearTimers = () => { timersRef.current.forEach(clearTimeout); timersRef.current = []; };

  const stop = useCallback(() => {
    clearTimers();
    if (ctxRef.current) ctxRef.current.close();
    ctxRef.current = null;
    setPlaying(false);
    setSideIdx(0);
  }, []);

  // playback jumps to the first used beat of each side and stops after the last one
  const layoutRef = useRef([]);

  const play = useCallback(() => {
    clearTimers();
    if (ctxRef.current) ctxRef.current.close();
    const ctx = newCtx();
    ctxRef.current = ctx;
    const master = ctx.createGain();
    master.gain.value = 0.6;
    master.connect(ctx.destination);
    const t0 = ctx.currentTime + 0.1;
    const beatSec = revSeconds / MAX_BEAT;
    startRef.current = t0;
    revRef.current = revSeconds;
    let cursor = 0;
    const layout = sequence.map((partition) => {
      const beats = [];
      partition.forEach((row) => row.forEach((on, b) => { if (on) beats.push(b); }));
      const first = beats.length ? Math.min(...beats) : 0;
      const last = beats.length ? Math.max(...beats) : 0;
      const len = (last - first + 1) * beatSec + 1.2;
      const entry = { first, start: cursor, len };
      cursor += len + SIDE_GAP;
      return entry;
    });
    layoutRef.current = layout;
    sequence.forEach((partition, i) => {
      const { first, start } = layout[i];
      partition.forEach((row, tone) =>
        row.forEach((on, beat) => {
          if (on) pluck(ctx, master, midiToFreq(NOTES[tone] + REAL_PITCH_OFFSET), t0 + start + (beat - first) * beatSec);
        })
      );
      if (i > 0) timersRef.current.push(setTimeout(() => setSideIdx(i), (start + 0.1) * 1000));
    });
    setPlaying(true);
    setSideIdx(0);
    timersRef.current.push(setTimeout(() => {
      if (loopRef.current) playRef.current();
      else stop();
    }, (cursor + 0.1) * 1000));
  }, [sequence, revSeconds, stop]);
  playRef.current = play;

  // {side, beat} of the playhead, or null when idle
  const getPos = useCallback(() => {
    const ctx = ctxRef.current;
    const layout = layoutRef.current;
    if (!ctx || !layout.length) return null;
    const el = ctx.currentTime - startRef.current;
    const beatSec = revRef.current / MAX_BEAT;
    let side = layout.findIndex((l) => el < l.start + l.len + SIDE_GAP);
    if (side < 0) side = layout.length - 1;
    const l = layout[side];
    return { side, beat: l.first + (el - l.start) / beatSec };
  }, []);

  const tap = useCallback((tone) => {
    if (!tapCtxRef.current) tapCtxRef.current = newCtx();
    const ctx = tapCtxRef.current;
    if (ctx.state === "suspended") ctx.resume();
    pluck(ctx, ctx.destination, midiToFreq(NOTES[tone] + REAL_PITCH_OFFSET), ctx.currentTime);
  }, []);

  useEffect(() => () => { stop(); tapCtxRef.current?.close(); }, [stop]);

  return { playing, sideIdx, play, stop, getPos, tap };
}
