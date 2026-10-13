// Comb profile (live bindings — applyComb() re-points these for every importer)
export let NOTES = [67, 72, 74, 76, 79, 81, 83, 84, 86, 88, 89, 91, 93, 95, 96, 98];
export let TINES = [[1], [2], [3], [4], [5], [6], [7], [8, 9], [10, 11], [12, 13], [14, 15], [16, 17], [18, 19], [20], [21], [22]];
export let TWIN_TINE = new Set([7, 8, 9, 10, 11, 12]);
export let TRACK_TONE = TINES.flatMap((ts, tone) => ts.map(() => tone));
export let COMB_TRACKS = [67, 72, 74, 76, 79, 81, 83, 84, 84, 86, 86, 88, 88, 89, 89, 91, 91, 93, 93, 95, 96, 98];
export let COMB_FACTORY = true;
export const TINE_COUNT = 22;
export const MAX_BEAT = 86;
export const TOY_REV_SECONDS = 25;
// the real comb sounds a major third below Fred's C-major notation (A-flat major)
export const REAL_PITCH_OFFSET = -4;

export function applyComb(c) {
  NOTES = c.notes;
  TINES = c.tines;
  TWIN_TINE = new Set(c.twins);
  TRACK_TONE = TINES.flatMap((ts, tone) => ts.map(() => tone));
  COMB_TRACKS = c.tracks;
  COMB_FACTORY = !!c.factory;
}

const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const SEMI = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
export const noteName = (m) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;
export const noteToMidi = (s) => {
  const m = /^([A-Ga-g])([#b♯♭]?)(-?\d)$/.exec(String(s).trim());
  if (!m) return null;
  const acc = m[2] === "#" || m[2] === "♯" ? 1 : m[2] ? -1 : 0;
  return (Number(m[3]) + 1) * 12 + SEMI[m[1].toUpperCase()] + acc;
};
export const midiToFreq = (m) => 440 * Math.pow(2, (m - 69) / 12);
export const clonePartition = (p) => p.map((r) => [...r]);
export const countNotes = (p) => p.reduce((s, r) => s + r.filter(Boolean).length, 0);
export const emptyPartition = () => NOTES.map(() => Array(MAX_BEAT).fill(false));
export const speedPct = (duration, rev) => Math.round((duration / rev) * 100);
export const SIDE_GAP = 0.8;

// single-tine pitch asked to strike on consecutive beats (disc wraps)
export const repeatConflicts = (p) => {
  const s = new Set();
  p.forEach((row, tone) => {
    if (TWIN_TINE.has(tone)) return;
    for (let b = 0; b < row.length; b++) {
      const n = (b + 1) % row.length;
      if (row[b] && row[n]) { s.add(`${tone}-${b}`); s.add(`${tone}-${n}`); }
    }
  });
  return s;
};
// two notes on the same beat — the player plucks one tine at a time
export const chordConflicts = (p, voices = 1) => {
  const s = new Set();
  for (let b = 0; b < MAX_BEAT; b++) {
    const tones = [];
    p.forEach((row, tone) => { if (row[b]) tones.push(tone); });
    if (tones.length > voices) tones.forEach((t) => s.add(`${t}-${b}`));
  }
  return s;
};

// minimum beat spacing between two pins of one pitch (single tines need a rest beat)
const gapBeats = (tone) => (TWIN_TINE.has(tone) ? 1 : 2);
// one pin per beat on the whole disc + per-pitch spacing (disc wraps) — mirrors fisher_price._can_place
const canPlace = (p, tone, b) => {
  if (p.some((row) => row[b])) return false;
  for (let d = 1; d < gapBeats(tone); d++) {
    if (p[tone][(b - d + MAX_BEAT) % MAX_BEAT] || p[tone][(b + d) % MAX_BEAT]) return false;
  }
  return true;
};
// move the pin at (tone, b) to the nearest free beat, leaning `prefer` direction for the first LEAN_BEATS
const LEAN_BEATS = 4;
const slide = (p, tone, b, prefer) => {
  p[tone][b] = false;
  const cands = [];
  for (let d = 1; d < LEAN_BEATS; d++) cands.push(b + prefer * d);
  for (let d = LEAN_BEATS; d < MAX_BEAT; d++) cands.push(b + prefer * d, b - prefer * d);
  for (let d = 1; d < LEAN_BEATS; d++) cands.push(b - prefer * d);
  for (const nb of cands) {
    if (nb >= 0 && nb < MAX_BEAT && canPlace(p, tone, nb)) { p[tone][nb] = true; return true; }
  }
  return false;
};

// roll same-beat notes like the factory records: top note keeps the beat, lower ones lean before (default) or after it
export const staggerPartition = (p, roll = "before") => {
  const out = clonePartition(p);
  const prefer = roll === "after" ? 1 : -1;
  for (let b = 0; b < MAX_BEAT; b++) {
    const tones = [];
    out.forEach((row, t) => { if (row[b]) tones.push(t); });
    tones.slice(0, -1).forEach((t) => slide(out, t, b, prefer));
  }
  return out;
};

// a single tine can't strike on consecutive beats: slide the later strike to the nearest free beat
export const thinRepeats = (p) => {
  const out = clonePartition(p);
  out.forEach((row, tone) => {
    const gap = gapBeats(tone);
    if (gap < 2) return;
    for (let b = 0; b < MAX_BEAT; b++) {
      let clash = false;
      for (let d = 1; d < gap; d++) if (row[(b - d + MAX_BEAT) % MAX_BEAT]) clash = true;
      if (row[b] && clash) slide(out, tone, b, 1);
    }
  });
  return out;
};
export const grooveConflicts = repeatConflicts;
export const makePlayable = (p, roll = "before") => thinRepeats(staggerPartition(p, roll));
// cells that differ between the MIDI capture and the disc: moved = in MIDI only, placed = on disc only
export const diffPartitions = (midi, disc) => {
  const moved = new Set();
  const placed = new Set();
  if (!midi || !disc) return { moved, placed };
  disc.forEach((row, t) => row.forEach((on, b) => {
    const was = !!(midi[t] && midi[t][b]);
    if (was && !on) moved.add(`${t}-${b}`);
    if (on && !was) placed.add(`${t}-${b}`);
  }));
  return { moved, placed };
};

// pitch rows -> 22 physical tracks (mirrors fisher_price.to_physical, with twin overrides)
export const toPhysical = (p, overrides = {}) => {
  const beats = p[0].length;
  const out = Array.from({ length: TINE_COUNT }, () => Array(beats).fill(false));
  p.forEach((row, tone) => {
    const t = TINES[tone].map((n) => n - 1);
    if (t.length === 1) { out[t[0]] = [...row]; return; }
    let onSecond = false;
    row.forEach((on, i) => {
      if (!on) return;
      let slot = overrides[`${tone}-${i}`];
      if (slot == null) slot = onSecond ? 1 : 0;
      out[t[slot % t.length]][i] = true;
      onSecond = slot === 0;
    });
  });
  return out;
};

export const CARD = "bg-white border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl";
export const BTN_LIFT =
  "transition-[transform,box-shadow] duration-150 hover:-translate-y-1 hover:shadow-[6px_6px_0_0_#1D3557] active:translate-y-1 active:shadow-[2px_2px_0_0_#1D3557]";
export const BTN_BASE = `font-sans font-black tracking-tight rounded-xl border-2 border-[#1D3557] flex items-center justify-center gap-2 shadow-[4px_4px_0_0_#1D3557] ${BTN_LIFT}`;
export const BTN_DISABLED =
  "bg-[#E9C46A]/50 text-[#1D3557]/50 cursor-not-allowed shadow-[2px_2px_0_0_#1D3557] hover:translate-y-0 hover:shadow-[2px_2px_0_0_#1D3557]";
export const INPUT = "font-mono text-sm border-2 border-[#1D3557] rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#E63946]";
