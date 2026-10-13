export const NOTES = [67, 72, 74, 76, 79, 81, 83, 84, 86, 88, 89, 91, 93, 95, 96, 98];
// pitches 7..12 (C6..A6 in Fred's notation) each have two physical tines on the 22-tine comb
export const TWIN_TINE = new Set([7, 8, 9, 10, 11, 12]);
export const TINE_COUNT = 22;
// physical tine numbers (1-22, low to high) for each pitch row
export const TINES = [[1], [2], [3], [4], [5], [6], [7], [8, 9], [10, 11], [12, 13], [14, 15], [16, 17], [18, 19], [20], [21], [22]];
// the real comb sounds a major third below Fred's C-major notation (A-flat major)
export const REAL_PITCH_OFFSET = -4;
export const MAX_BEAT = 86;
export const TOY_REV_SECONDS = 25;

const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
export const noteName = (m) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;
export const midiToFreq = (m) => 440 * Math.pow(2, (m - 69) / 12);
export const clonePartition = (p) => p.map((r) => [...r]);
export const countNotes = (p) => p.reduce((s, r) => s + r.filter(Boolean).length, 0);
export const speedPct = (duration, rev) => Math.round((duration / rev) * 100);
export const SIDE_GAP = 0.8;

// 16 pitch rows -> 22 physical tracks (mirrors fisher_price.to_physical)
export const toPhysical = (p) => {
  const beats = p[0].length;
  const out = Array.from({ length: TINE_COUNT }, () => Array(beats).fill(false));
  const split = (first, second, row) => {
    let onSecond = false;
    row.forEach((on, i) => { if (on) { out[onSecond ? second : first][i] = true; onSecond = !onSecond; } });
  };
  p.forEach((row, tone) => {
    const t = TINES[tone].map((n) => n - 1);
    if (t.length === 2) split(t[0], t[1], row); else out[t[0]] = [...row];
  });
  return out;
};
// pitch row index for each physical track (0-21)
export const TRACK_TONE = TINES.flatMap((ts, tone) => ts.map(() => tone));

// cells where a single-tine pitch is asked to play on consecutive beats (disc wraps)
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

export const CARD = "bg-white border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl";
export const BTN_LIFT =
  "transition-[transform,box-shadow] duration-150 hover:-translate-y-1 hover:shadow-[6px_6px_0_0_#1D3557] active:translate-y-1 active:shadow-[2px_2px_0_0_#1D3557]";
export const BTN_BASE = `font-sans font-black tracking-tight rounded-xl border-2 border-[#1D3557] flex items-center justify-center gap-2 shadow-[4px_4px_0_0_#1D3557] ${BTN_LIFT}`;
export const BTN_DISABLED =
  "bg-[#E9C46A]/50 text-[#1D3557]/50 cursor-not-allowed shadow-[2px_2px_0_0_#1D3557] hover:translate-y-0 hover:shadow-[2px_2px_0_0_#1D3557]";
