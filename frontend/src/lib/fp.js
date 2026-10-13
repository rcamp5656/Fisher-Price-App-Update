export const NOTES = [67, 72, 74, 76, 79, 81, 83, 84, 86, 88, 89, 91, 93, 95, 96, 98];
// pitches 7..12 (C6..A6) each have two physical tines on the 22-tine comb
export const TWIN_TINE = new Set([7, 8, 9, 10, 11, 12]);
export const TINE_COUNT = 22;
export const MAX_BEAT = 86;
export const TOY_REV_SECONDS = 25;

const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
export const noteName = (m) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;
export const midiToFreq = (m) => 440 * Math.pow(2, (m - 69) / 12);
export const clonePartition = (p) => p.map((r) => [...r]);
export const countNotes = (p) => p.reduce((s, r) => s + r.filter(Boolean).length, 0);
export const speedPct = (duration, rev) => Math.round((duration / rev) * 100);

export const CARD = "bg-white border-2 border-[#1D3557] shadow-[4px_4px_0_0_#1D3557] rounded-xl";
export const BTN_LIFT =
  "transition-[transform,box-shadow] duration-150 hover:-translate-y-1 hover:shadow-[6px_6px_0_0_#1D3557] active:translate-y-1 active:shadow-[2px_2px_0_0_#1D3557]";
export const BTN_BASE = `font-sans font-black tracking-tight rounded-xl border-2 border-[#1D3557] flex items-center justify-center gap-2 shadow-[4px_4px_0_0_#1D3557] ${BTN_LIFT}`;
export const BTN_DISABLED =
  "bg-[#E9C46A]/50 text-[#1D3557]/50 cursor-not-allowed shadow-[2px_2px_0_0_#1D3557] hover:translate-y-0 hover:shadow-[2px_2px_0_0_#1D3557]";
