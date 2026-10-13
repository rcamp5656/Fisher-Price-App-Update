import { useCallback, useEffect, useRef, useState } from "react";
import { NOTES, MAX_BEAT, SIDE_GAP, REAL_PITCH_OFFSET, midiToFreq } from "../lib/fp";

function pluck(ctx, dest, freq, when) {
  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, when);
  env.gain.exponentialRampToValueAtTime(0.5, when + 0.004);
  env.gain.exponentialRampToValueAtTime(0.0001, when + 1.8);
  const fund = ctx.createOscillator();
  fund.type = "sine";
  fund.frequency.value = freq;
  const bright = ctx.createOscillator();
  bright.type = "sine";
  bright.frequency.value = freq * 4;
  const brightEnv = ctx.createGain();
  brightEnv.gain.setValueAtTime(0.18, when);
  brightEnv.gain.exponentialRampToValueAtTime(0.0001, when + 0.35);
  fund.connect(env);
  bright.connect(brightEnv);
  brightEnv.connect(env);
  env.connect(dest);
  fund.start(when);
  bright.start(when);
  fund.stop(when + 1.9);
  bright.stop(when + 0.5);
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
    const sideLen = revSeconds + SIDE_GAP;
    startRef.current = t0;
    revRef.current = revSeconds;
    sequence.forEach((partition, i) => {
      const base = t0 + i * sideLen;
      partition.forEach((row, tone) =>
        row.forEach((on, beat) => {
          if (on) pluck(ctx, master, midiToFreq(NOTES[tone] + REAL_PITCH_OFFSET), base + beat * beatSec);
        })
      );
      if (i > 0) timersRef.current.push(setTimeout(() => setSideIdx(i), (i * sideLen + 0.1) * 1000));
    });
    setPlaying(true);
    setSideIdx(0);
    const total = (sequence.length * sideLen + 0.1) * 1000;
    timersRef.current.push(setTimeout(() => {
      if (loopRef.current) playRef.current();
      else stop();
    }, total));
  }, [sequence, revSeconds, stop]);
  playRef.current = play;

  // {side, beat} of the playhead, or null when idle
  const getPos = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return null;
    const el = ctx.currentTime - startRef.current;
    const sideLen = revRef.current + SIDE_GAP;
    const side = Math.floor(el / sideLen);
    return { side, beat: ((el - side * sideLen) / revRef.current) * MAX_BEAT };
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
