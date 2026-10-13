import { useCallback, useEffect, useRef, useState } from "react";
import { NOTES, MAX_BEAT, SIDE_GAP, REAL_PITCH_OFFSET, midiToFreq } from "../lib/fp";

// Music-box tine: strong fundamental, decaying inharmonic partials, soft pluck transient
const PARTIALS = [[1, 1.0, 1.9], [2.0, 0.45, 1.0], [3.01, 0.22, 0.55], [4.16, 0.12, 0.28]];
export function pluck(ctx, dest, freq, when) {
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

// One AudioContext for the whole app (Chrome/Edge on Windows go silent when contexts are
// opened and closed per play). Every player gets its own Channel = a gain node on the master bus.
const VOLUME_KEY = "fp-volume";
let shared = null;
let master = null;
const watchers = new Set();
const notify = () => watchers.forEach((fn) => fn());
export const getVolume = () => {
  const v = Number(localStorage.getItem(VOLUME_KEY));
  return Number.isFinite(v) && localStorage.getItem(VOLUME_KEY) !== null ? Math.min(1, Math.max(0, v)) : 0.8;
};
export function setVolume(v) {
  localStorage.setItem(VOLUME_KEY, String(v));
  if (master) master.gain.setTargetAtTime(v * 1.5, shared.currentTime, 0.02);
  notify();
}
export function audioEngine() {
  if (!shared || shared.state === "closed") {
    shared = new (window.AudioContext || window.webkitAudioContext)();
    master = shared.createGain();
    master.gain.value = getVolume() * 1.5;
    master.connect(shared.destination);
    shared.onstatechange = notify;
    notify();
  }
  if (shared.state === "suspended") shared.resume().then(notify, notify);
  return shared;
}
// "idle" (not created yet) · "running" · "suspended" (browser blocked it) · "closed"
export const audioState = () => (shared ? shared.state : "idle");
export const audioSampleRate = () => (shared ? shared.sampleRate : 0);
export function watchAudio(fn) { watchers.add(fn); return () => watchers.delete(fn); }
if (typeof window !== "undefined") {
  ["pointerdown", "keydown", "touchend"].forEach((ev) => window.addEventListener(ev, () => audioEngine(), { passive: true, capture: true }));
}

class Channel {
  constructor() {
    this.ctx = audioEngine();
    this.destination = this.ctx.createGain();
    this.destination.connect(master);
  }
  get currentTime() { return this.ctx.currentTime; }
  get state() { return this.ctx.state; }
  get sampleRate() { return this.ctx.sampleRate; }
  createGain() { return this.ctx.createGain(); }
  createOscillator() { return this.ctx.createOscillator(); }
  createBiquadFilter() { return this.ctx.createBiquadFilter(); }
  createBufferSource() { return this.ctx.createBufferSource(); }
  createBuffer(...a) { return this.ctx.createBuffer(...a); }
  resume() { return this.ctx.resume(); }
  close() {
    const g = this.destination;
    g.gain.cancelScheduledValues(this.ctx.currentTime);
    g.gain.setTargetAtTime(0, this.ctx.currentTime, 0.01);
    setTimeout(() => g.disconnect(), 80);
  }
}
export const newCtx = () => new Channel();

// short test pluck so the user can confirm the browser is letting sound through
export function testTone() {
  const ch = newCtx();
  pluck(ch, ch.destination, midiToFreq(84 + REAL_PITCH_OFFSET), ch.currentTime + 0.02);
  pluck(ch, ch.destination, midiToFreq(88 + REAL_PITCH_OFFSET), ch.currentTime + 0.25);
  pluck(ch, ch.destination, midiToFreq(91 + REAL_PITCH_OFFSET), ch.currentTime + 0.5);
  setTimeout(() => ch.close(), 3000);
}

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

  const play = useCallback((from = null) => {
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
    const fromSide = from && Number.isInteger(from.side) ? from.side : 0;
    const fromBeat = from && Number.isFinite(from.beat) ? Math.max(0, Math.floor(from.beat)) : null;
    let cursor = 0;
    const layout = sequence.map((partition, i) => {
      if (i < fromSide) return { first: 0, start: 0, len: 0, skip: true };
      const beats = [];
      partition.forEach((row) => row.forEach((on, b) => { if (on && !(i === fromSide && fromBeat !== null && b < fromBeat)) beats.push(b); }));
      let first = beats.length ? Math.min(...beats) : 0;
      if (i === fromSide && fromBeat !== null) first = fromBeat;
      const last = beats.length ? Math.max(...beats) : first;
      const len = (last - first + 1) * beatSec + 1.2;
      const entry = { first, start: cursor, len, skip: false };
      cursor += len + SIDE_GAP;
      return entry;
    });
    layoutRef.current = layout;
    sequence.forEach((partition, i) => {
      const { first, start, skip } = layout[i];
      if (skip) return;
      partition.forEach((row, tone) =>
        row.forEach((on, beat) => {
          if (on && beat >= first) pluck(ctx, master, midiToFreq(NOTES[tone] + REAL_PITCH_OFFSET), t0 + start + (beat - first) * beatSec);
        })
      );
      if (i > fromSide) timersRef.current.push(setTimeout(() => setSideIdx(i), (start + 0.1) * 1000));
    });
    setPlaying(true);
    setSideIdx(fromSide);
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
    let side = layout.findIndex((l) => !l.skip && el < l.start + l.len + SIDE_GAP);
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
