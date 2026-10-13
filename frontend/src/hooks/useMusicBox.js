import { useCallback, useEffect, useRef, useState } from "react";
import { NOTES, MAX_BEAT, midiToFreq } from "../lib/fp";

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

export function useMusicBox(partition, revSeconds) {
  const [playing, setPlaying] = useState(false);
  const ctxRef = useRef(null);
  const startRef = useRef(0);
  const beatSecRef = useRef(revSeconds / MAX_BEAT);
  const timerRef = useRef(null);
  const tapCtxRef = useRef(null);

  const stop = useCallback(() => {
    clearTimeout(timerRef.current);
    if (ctxRef.current) ctxRef.current.close();
    ctxRef.current = null;
    setPlaying(false);
  }, []);

  const play = useCallback(() => {
    stop();
    const ctx = newCtx();
    ctxRef.current = ctx;
    const master = ctx.createGain();
    master.gain.value = 0.6;
    master.connect(ctx.destination);
    const t0 = ctx.currentTime + 0.1;
    const beatSec = revSeconds / MAX_BEAT;
    startRef.current = t0;
    beatSecRef.current = beatSec;
    partition.forEach((row, tone) =>
      row.forEach((on, beat) => {
        if (on) pluck(ctx, master, midiToFreq(NOTES[tone]), t0 + beat * beatSec);
      })
    );
    setPlaying(true);
    timerRef.current = setTimeout(stop, (revSeconds + 1.5) * 1000);
  }, [partition, revSeconds, stop]);

  const getBeat = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return -1;
    return (ctx.currentTime - startRef.current) / beatSecRef.current;
  }, []);

  const tap = useCallback((tone) => {
    if (!tapCtxRef.current) tapCtxRef.current = newCtx();
    const ctx = tapCtxRef.current;
    if (ctx.state === "suspended") ctx.resume();
    pluck(ctx, ctx.destination, midiToFreq(NOTES[tone]), ctx.currentTime);
  }, []);

  useEffect(() => () => { stop(); tapCtxRef.current?.close(); }, [stop]);

  return { playing, play, stop, getBeat, tap };
}
