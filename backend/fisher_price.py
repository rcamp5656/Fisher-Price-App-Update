"""
Fisher-Price Music Box Record generator.

Ports the geometry/algorithm from the "Fisher Price Music Box Record Creator"
(Fred's Fisher Price record creator template) to pure Python, producing a
printable STL for the vintage 1977 Fisher-Price Music Box Record Player.

The physical record is a flat disc with raised bumps ("pins") arranged in
concentric tracks. As the disc rotates, the pins pluck the music box tines.
"""
import bisect
import math
import io
import re
from typing import List, Dict, Tuple, Optional

import numpy as np
import trimesh

# ---------------------------------------------------------------------------
# Geometry constants (from res/fisher-price-template.scad)
# ---------------------------------------------------------------------------
R_STOCK = 60.58       # disc radius (mm)
O_DRIVE = 21.8        # drive-hole offset from centre
R_DRIVE = 1.55        # drive-hole radius
H_INSET = 1.0         # depth of the recessed label area (top & bottom)
R_INSET = 25.6        # radius of the recessed label area
H_GROOVE = 1.2        # depth of the note grooves
OVERLAP = 0.2         # modelling overlap to keep booleans manifold
R_CENTER = 3.22       # centre spindle hole radius
HEAD_OFFSET = 2.0     # angular lead of the playback head
R_PIN = 0.8           # pin height: apex protrusion into the groove
PIN_BASE = 1.6        # pin base length along the groove wall (flatter ramp, reads as part of the wall)
PIN_SINK = 0.5        # how deep the pin base is buried in the wall so slicers never open a seam

# Groove inner radii (11 grooves, each holds two note tracks)
GROOVE_INNERS = [28.15, 30.89, 33.71, 36.425, 39.225, 42,
                 44.825, 47.555, 50.315, 53.11, 55.9]

# Factory comb: MIDI pitch of each of the 22 tines (track 1..22, inner -> outer).
# Six pitches are duplicated on twin tines so fast repeats can play.
FACTORY_TRACKS = [67, 72, 74, 76, 79, 81, 83, 84, 84, 86, 86, 88, 88,
                  89, 89, 91, 91, 93, 93, 95, 96, 98]
TRACKS_COUNT = 22
MAX_BEAT = 86         # beats (angular steps) per full revolution


class Comb:
    """Pitch layout of a player's comb: 22 tracks -> unique pitch rows."""

    def __init__(self, tracks: List[int]):
        if len(tracks) != TRACKS_COUNT:
            raise ValueError(f"a comb has {TRACKS_COUNT} tines")
        self.tracks = [int(t) for t in tracks]
        self.notes = sorted(set(self.tracks))
        self.tines = [[i for i, t in enumerate(self.tracks) if t == n] for n in self.notes]
        self.twins = {i for i, g in enumerate(self.tines) if len(g) > 1}

    @property
    def tones(self) -> int:
        return len(self.notes)

    def to_dict(self) -> Dict:
        return {
            "tracks": self.tracks,
            "notes": self.notes,
            "names": [note_name(n) for n in self.notes],
            "tines": [[i + 1 for i in g] for g in self.tines],
            "twins": sorted(self.twins),
            "factory": self.tracks == FACTORY_TRACKS,
        }


DEFAULT_COMB = Comb(FACTORY_TRACKS)
NOTES = DEFAULT_COMB.notes
TONES_COUNT = DEFAULT_COMB.tones

# Radius of each of the 22 physical tracks
TRACK_RADIUS = [
    28.65, 29.65, 31.39, 32.39, 34.21, 35.21, 36.925, 37.925,
    39.725, 40.725, 42.5, 43.5, 45.325, 46.325, 48.055, 49.055,
    50.815, 51.815, 53.61, 54.61, 56.4, 57.4,
]

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(midi: int) -> str:
    return f"{_NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


# ---------------------------------------------------------------------------
# MIDI -> note events
# ---------------------------------------------------------------------------
GM_NAMES = (
    "Grand Piano,Bright Piano,Electric Grand,Honky-tonk Piano,Electric Piano 1,Electric Piano 2,Harpsichord,Clavinet,"
    "Celesta,Glockenspiel,Music Box,Vibraphone,Marimba,Xylophone,Tubular Bells,Dulcimer,"
    "Drawbar Organ,Percussive Organ,Rock Organ,Church Organ,Reed Organ,Accordion,Harmonica,Tango Accordion,"
    "Nylon Guitar,Steel Guitar,Jazz Guitar,Clean Guitar,Muted Guitar,Overdriven Guitar,Distortion Guitar,Guitar Harmonics,"
    "Acoustic Bass,Finger Bass,Pick Bass,Fretless Bass,Slap Bass 1,Slap Bass 2,Synth Bass 1,Synth Bass 2,"
    "Violin,Viola,Cello,Contrabass,Tremolo Strings,Pizzicato Strings,Harp,Timpani,"
    "String Ensemble 1,String Ensemble 2,Synth Strings 1,Synth Strings 2,Choir Aahs,Voice Oohs,Synth Voice,Orchestra Hit,"
    "Trumpet,Trombone,Tuba,Muted Trumpet,French Horn,Brass Section,Synth Brass 1,Synth Brass 2,"
    "Soprano Sax,Alto Sax,Tenor Sax,Baritone Sax,Oboe,English Horn,Bassoon,Clarinet,"
    "Piccolo,Flute,Recorder,Pan Flute,Blown Bottle,Shakuhachi,Whistle,Ocarina,"
    "Square Lead,Sawtooth Lead,Calliope Lead,Chiff Lead,Charang Lead,Voice Lead,Fifths Lead,Bass + Lead,"
    "New Age Pad,Warm Pad,Polysynth Pad,Choir Pad,Bowed Pad,Metallic Pad,Halo Pad,Sweep Pad,"
    "Rain,Soundtrack,Crystal,Atmosphere,Brightness,Goblins,Echoes,Sci-Fi,"
    "Sitar,Banjo,Shamisen,Koto,Kalimba,Bagpipe,Fiddle,Shanai,"
    "Tinkle Bell,Agogo,Steel Drums,Woodblock,Taiko Drum,Melodic Tom,Synth Drum,Reverse Cymbal,"
    "Guitar Fret Noise,Breath Noise,Seashore,Bird Tweet,Telephone,Helicopter,Applause,Gunshot"
).split(",")
DRUM_CHANNEL = 9


def _all_note_events(midi_bytes: bytes) -> List[Tuple[float, int, int, int]]:
    """Every note-on as (seconds, note, channel, track index), honouring the
    tempo map shared by all tracks."""
    import mido
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    tempos = []
    for tr in mid.tracks:
        tick = 0
        for msg in tr:
            tick += msg.time
            if msg.type == "set_tempo":
                tempos.append((tick, msg.tempo))
    tempos.sort()
    if not tempos or tempos[0][0] > 0:
        tempos.insert(0, (0, 500000))
    # cumulative seconds at each tempo change
    marks = [(0, 0.0, tempos[0][1])]
    for tick, tempo in tempos[1:]:
        ptick, psec, ptempo = marks[-1]
        marks.append((tick, psec + mido.tick2second(tick - ptick, mid.ticks_per_beat, ptempo), tempo))

    def to_sec(tick: int) -> float:
        k = bisect.bisect_right(marks, (tick, float("inf"), 0)) - 1
        mtick, msec, mtempo = marks[k]
        return msec + mido.tick2second(tick - mtick, mid.ticks_per_beat, mtempo)

    out = []
    for ti, tr in enumerate(mid.tracks):
        tick = 0
        for msg in tr:
            tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                out.append((to_sec(tick), msg.note, msg.channel, ti))
    out.sort()
    return out


def scan_tracks(midi_bytes: bytes) -> Dict:
    """Per-track summary for the track picker plus the most melody-like track."""
    import mido
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    events = _all_note_events(midi_bytes)
    total = max((t for t, *_ in events), default=0.0)
    tracks = []
    for ti, tr in enumerate(mid.tracks):
        ev = [e for e in events if e[3] == ti]
        if not ev:
            continue
        progs = [m.program for m in tr if m.type == "program_change"]
        chans = {c for _, _, c, _ in ev}
        drums = chans == {DRUM_CHANNEL}
        onsets = sorted({round(t, 2) for t, *_ in ev})
        span = (onsets[-1] - onsets[0]) if len(onsets) > 1 else 0.0
        poly = len(ev) / len(onsets)
        density = len(onsets) / max(span, 1.0)
        notes = [n for _, n, _, _ in ev]
        mean = sum(notes) / len(notes)
        # melody-likeness: monophonic, singable register (bass lines score ~0),
        # ~1-4 notes/s, varied pitches, lasts most of the song
        score = 0.0
        if not drums:
            variety = len(set(notes)) / max(1, min(len(notes), 40))
            score += 25 * max(0.0, 1 - (poly - 1) * 2)
            score += 15 * math.exp(-((mean - 72) / 16) ** 2)
            score += 25 * (1 - min(1.0, abs(math.log2(max(density, 0.05) / 2.0)) / 2.0))
            score += 10 * min(1.0, variety * 4)
            score += 15 * min(1.0, span / max(total, 1.0))
            score += 10 * min(1.0, len(ev) / max(total, 1.0))
            label = f"{tr.name} {GM_NAMES[progs[0]] if progs and 0 <= progs[0] < 128 else ''}".lower()
            is_bass = "bass" in label or (progs and 32 <= progs[0] <= 39) or mean < 55
            if is_bass:
                score *= 0.4  # a bass line is never the tune
            if any(k in label for k in ("melody", "lead", "vocal", "voice", "sing", "solo", "tune", "main")):
                score += 20
        step = max(1, len(ev) // 300)
        tracks.append({
            "index": ti,
            "name": tr.name or "",
            "instrument": "Drums" if drums else (GM_NAMES[progs[0]] if progs and 0 <= progs[0] < 128 else "Unknown"),
            "program": progs[0] if progs else None,
            "channels": sorted(chans),
            "drums": drums,
            "notes": len(ev),
            "onsets": len(onsets),
            "poly": round(poly, 2),
            "density": round(density, 2),
            "low": min(notes),
            "high": max(notes),
            "first": round(onsets[0], 2),
            "span": round(span, 1),
            "melody_score": round(score, 1),
            "strip": [[round(t, 2), n] for t, n, _, _ in ev[::step]],
        })
    melodic = [t for t in tracks if not t["drums"]]
    suggested = max(melodic, key=lambda t: t["melody_score"])["index"] if melodic else None
    title = ""
    for m in mid.tracks[0]:
        if m.type == "track_name" and m.name.strip():
            title = m.name.strip()
            break
    return {"tracks": tracks, "suggested": suggested, "total": round(total, 2), "title": title[:40],
            "events": [[round(t, 3), n, ti] for t, n, c, ti in events if c != DRUM_CHANNEL]}


def _skyline(events: List[Tuple[float, int]], bucket: float = 0.05) -> List[Tuple[float, int]]:
    """Top note per time bucket — the line a listener hears as 'the tune'."""
    top: Dict[int, Tuple[float, int]] = {}
    for t, n in events:
        key = int(round(t / bucket))
        if key not in top or n > top[key][1]:
            top[key] = (t, n)
    return sorted(top.values())


MELODY_GAP = 1.5  # a rest this long in the melody track gets filled from the other instruments


def _melody_fill(sel: List[Tuple[float, int]], others: List[Tuple[float, int]]) -> List[Tuple[float, int]]:
    """Where the melody track rests for more than MELODY_GAP, borrow the
    skyline of the other (non-bass) instruments, thinned to >= 0.25 s apart."""
    if not sel or not others:
        return sel
    sky = _skyline(others, 0.1)
    out = list(sel)
    times = sorted(t for t, _ in sel)
    for a, b in zip(times, times[1:]):
        if b - a < MELODY_GAP:
            continue
        last = -1.0
        for t, n in sky:
            if a + 0.3 <= t <= b - 0.3 and t - last >= 0.25:
                out.append((t, n))
                last = t
    return sorted(out)


def parse_midi_events(midi_bytes: bytes, duration: float,
                      start: float = 0.0, tracks: Optional[List[int]] = None,
                      skyline: bool = False, melody_fill: bool = False) -> List[Tuple[float, int]]:
    """Note-ons inside [start, start+duration) from the chosen tracks (all
    pitched tracks when None). Drums (channel 10) are never pitched notes on
    the toy and are skipped. `skyline` keeps only the top note of each chord;
    `melody_fill` patches rests in the chosen tracks with the other instruments."""
    sel = set(tracks) if tracks else None
    allev = [(t, n, c, ti) for t, n, c, ti in _all_note_events(midi_bytes)
             if c != DRUM_CHANNEL and start <= t < start + duration]
    events = [(t - start, n) for t, n, c, ti in allev if sel is None or ti in sel]
    if skyline and events:
        events = _skyline(events)
    if melody_fill and sel is not None:
        means: Dict[int, float] = {}
        for ti in {e[3] for e in allev}:
            ns = [n for _, n, _, x in allev if x == ti]
            means[ti] = sum(ns) / len(ns)
        others = [(t - start, n) for t, n, c, ti in allev if ti not in sel and means[ti] >= 55]
        events = _melody_fill(events, others)
    return events


def midi_length(midi_bytes: bytes) -> float:
    import mido
    return mido.MidiFile(file=io.BytesIO(midi_bytes)).length


def choose_transposition(notes: List[int], comb: Comb = DEFAULT_COMB,
                         tolerance: float = 0.15) -> int:
    """Key-faithful transposition: keep the MIDI's own pitches (offset 0) when
    at least (1 - tolerance) of the notes already sit on real tines; otherwise
    prefer octave shifts, then the smallest shift that fits the most notes."""
    allowed = set(comb.notes)
    lo, hi = min(comb.notes), max(comb.notes)
    n = len(notes)

    def fit(offset):
        exact = sum(1 for x in notes if x + offset in allowed)
        dist = sum(min(abs(x + offset - a) for a in comb.notes) for x in notes)
        return exact, dist

    exact0, _ = fit(0)
    if exact0 >= n * (1 - tolerance):
        return 0
    best = None
    for offset in range(-36, 37):
        avg = sum(notes) / n + offset
        if not (lo - 6 <= avg <= hi + 6):
            continue
        exact, dist = fit(offset)
        octave = offset % 12 == 0
        score = (exact, octave, -abs(offset), -dist)
        if best is None or score > best[0]:
            best = (score, offset)
    if best is None:
        return 0
    # settle for a nearby octave-only shift if it is almost as good
    best_exact = best[0][0]
    for offset in (-12, 12, -24, 24):
        if fit(offset)[0] >= best_exact - max(1, int(n * tolerance)):
            return offset
    return best[1]


def transposition_candidates(notes: List[int], comb: Comb = DEFAULT_COMB, k: int = 4) -> List[int]:
    """Best few shifts (tines up or down) ranked by how many melody notes land
    exactly on a tine, then by staying inside the comb's range, then smallest."""
    if not notes:
        return [0]
    allowed = set(comb.notes)
    lo, hi = min(comb.notes), max(comb.notes)
    scored = []
    for offset in range(-36, 37):
        shifted = [n + offset for n in notes]
        exact = sum(1 for x in shifted if x in allowed)
        inside = sum(1 for x in shifted if lo <= x <= hi)
        scored.append((exact + 0.5 * inside, offset % 12 == 0, -abs(offset), offset))
    scored.sort(reverse=True)
    out = [choose_transposition(notes, comb)]
    for *_, offset in scored:
        if offset not in out:
            out.append(offset)
        if len(out) >= k:
            break
    return out


def snap_note(midi: int, comb: Comb = DEFAULT_COMB) -> int:
    return min(comb.notes, key=lambda a: abs(a - midi))


def events_to_record(events: List[Tuple[float, int]], duration: float,
                     auto_transpose: bool = True,
                     manual_offset: int = 0,
                     comb: Comb = DEFAULT_COMB,
                     stagger: bool = True, roll: str = "before", voices: int = 16) -> Dict:
    """Quantize note events onto a tones x MAX_BEAT grid. The player can only
    pluck one tine per beat, so simultaneous notes are staggered onto the
    nearest free beat (like the factory records)."""
    partition = [[False] * MAX_BEAT for _ in range(comb.tones)]
    col_used = [False] * MAX_BEAT
    raw_notes = [n for _, n in events]

    offset = 0
    if raw_notes:
        offset = choose_transposition(raw_notes, comb) if auto_transpose else manual_offset

    exact = adjusted = merged = staggered = 0
    used = set()
    for t, n in sorted(events):
        m = n + offset
        snapped = m if m in comb.notes else snap_note(m, comb)
        if m in comb.notes:
            exact += 1
        else:
            adjusted += 1
        tone = comb.notes.index(snapped)
        beat = round(t / duration * MAX_BEAT) if duration > 0 else 0
        beat = max(0, min(MAX_BEAT - 1, beat))
        if partition[tone][beat]:
            # same pitch twice on one beat: stagger it to the nearest free beat instead of merging
            nb = _nearest_free(partition, tone, beat, comb, mono=stagger)
            if nb is None:
                merged += 1  # the disc is full around here — nothing we can do
                continue
            beat = nb
            staggered += 1
        partition[tone][beat] = True
        col_used[beat] = True
        used.add(snapped)

    partition_midi = [list(r) for r in partition]
    if stagger:
        staggered += stagger_partition(partition, comb, roll)
        dropped = 0
    else:
        moved, dropped = limit_voices(partition, voices, comb, roll)
        staggered += moved
    slid, dropped2 = make_playable(partition, comb)
    dropped += dropped2
    staggered += slid

    return {
        "partition": partition,
        "partition_midi": partition_midi,
        "dropped": dropped,
        "offset": offset,
        "exact": exact,
        "adjusted": adjusted,
        "merged": merged,
        "staggered": staggered,
        "notes_used": sorted(used),
        "note_count": len(events),
    }


TEMPO_PENALTY = 12  # score points lost per 100 % tempo change, so the original speed wins ties


def _event_tone(note: int, offset: int, comb: Comb) -> int:
    m = note + offset
    return comb.notes.index(m if m in comb.notes else snap_note(m, comb))


def compare_fit(events: List[Tuple[float, int]], offset: int, partition: List[List[bool]],
                duration: float, rev_seconds: float, comb: Comb = DEFAULT_COMB) -> Dict:
    """Score how closely the disc reproduces the MIDI slice: every MIDI note is
    matched to the nearest pin of its (snapped) pitch within 2 beats; the score
    blends notes found, timing error and pitch exactness, minus a small tempo
    penalty so the original speed wins ties."""
    n = len(events)
    if n == 0:
        return {"score": 0.0, "matched": 0, "timing_ms": 0.0, "exact": 0, "tempo": duration / rev_seconds}
    beat_sec = duration / MAX_BEAT
    pins: Dict[int, List[float]] = {}
    for tone, row in enumerate(partition):
        pins[tone] = [b * beat_sec for b, on in enumerate(row) if on]
    matched = 0
    err = 0.0
    exact = 0
    for t, note in sorted(events):
        if note + offset in comb.notes:
            exact += 1
        tone = _event_tone(note, offset, comb)
        cands = pins[tone]
        if not cands:
            continue
        k = min(range(len(cands)), key=lambda i: abs(cands[i] - t))
        dt = abs(cands[k] - t)
        if dt <= 2 * beat_sec:
            matched += 1
            err += dt
            cands.pop(k)
    mean_err_beats = (err / matched / beat_sec) if matched else 1.0
    tempo = duration / rev_seconds
    score = 100 * (0.5 * matched / n + 0.3 * (1 - min(1.0, mean_err_beats)) + 0.2 * exact / n) - TEMPO_PENALTY * abs(tempo - 1)
    return {
        "score": round(max(0.0, score), 1),
        "matched": matched,
        "timing_ms": round((err / matched) * 1000, 1) if matched else 0.0,
        "exact": exact,
        "tempo": round(tempo, 3),
    }


def auto_fit(midi_bytes: bytes, start: float, rev_seconds: float = 25.0,
             comb: Comb = DEFAULT_COMB, roll: str = "before", auto_transpose: bool = True,
             manual_offset: int = 0, max_tries: int = 12000, tempo_range: float = 0.35,
             nudge: float = 0.5, tracks: Optional[List[int]] = None, skyline: bool = False,
             melody_fill: bool = False, chords: bool = False, voices: int = 16) -> Dict:
    """Re-map the MIDI slice onto the 86-beat disc up to `max_tries` ways —
    varying how many MIDI seconds fill one revolution (tempo within
    ±tempo_range) and a fine shift of the window start (±nudge s) — comparing
    each disc against the MIDI and keeping the closest match."""
    import numpy as np
    d_lo, d_hi = rev_seconds * (1 - tempo_range), rev_seconds * (1 + tempo_range)
    base = max(0.0, start - nudge)
    all_events = parse_midi_events(midi_bytes, d_hi + 2 * nudge, base, tracks, skyline, melody_fill)
    if not all_events:
        rec = events_to_record([], rev_seconds, auto_transpose, manual_offset, comb, roll=roll)
        rec["events"] = []
        rec["fit"] = {"score": 0.0, "tries": 0, "duration": rev_seconds, "start": start, "tempo": 1.0, "matched": 0, "timing_ms": 0.0}
        return rec
    notes = [n for _, n in all_events]
    offsets = transposition_candidates(notes, comb) if auto_transpose else [manual_offset]
    offset = offsets[0]
    T = np.array([t for t, _ in all_events])
    tones = np.array([_event_tone(n, offset, comb) for n in notes])
    single = np.array([len(comb.tines[t]) == 1 for t in range(comb.tones)])

    def quick(delta: float, dur: float) -> float:
        tt = T - delta
        m = (tt >= 0) & (tt < dur)
        tt, tn = tt[m], tones[m]
        n = len(tt)
        if n == 0:
            return -1.0
        bs = dur / MAX_BEAT
        beats = np.clip(np.rint(tt / bs).astype(int), 0, MAX_BEAT - 1)
        err = np.abs(beats * bs - tt) / bs
        keys = np.unique(tn * MAX_BEAT + beats)
        merged = n - len(keys)
        _, bc = np.unique(keys % MAX_BEAT, return_counts=True)
        chords = int((bc - 1).sum())
        kt, kb = keys // MAX_BEAT, keys % MAX_BEAT
        rep = int(((kt[1:] == kt[:-1]) & (kb[1:] - kb[:-1] == 1) & single[kt[1:]]).sum())
        return 100 * (1 - 0.5 * (merged + chords + rep) / n - 0.3 * float(err.mean())) - TEMPO_PENALTY * abs(dur / rev_seconds - 1)

    deltas = np.arange(0, 2 * nudge + 1e-9, 0.05)
    refine = min(300, max(10, max_tries // 10))
    n_dur = max(1, (max_tries - 2 * refine - 4) // len(deltas))
    durs = np.linspace(d_lo, d_hi, n_dur)
    coarse = sorted(((quick(d, u), d, u) for d in deltas for u in durs), reverse=True)
    tries = len(coarse)

    def full(delta: float, dur: float, off: int = None):
        delta, dur = float(delta), float(dur)
        off = offset if off is None else off
        ev = [(t - delta, n) for t, n in all_events if 0 <= t - delta < dur]
        rec = events_to_record(ev, dur, False, off, comb, stagger=not chords, roll=roll, voices=voices)
        fit = compare_fit(ev, off, rec["partition"], dur, rev_seconds, comb)
        return fit["score"], delta, dur, rec, fit, ev

    best = None
    for _, d, u in coarse[:refine]:
        if tries >= max_tries:
            break
        cand = full(d, u)
        tries += 1
        if best is None or cand[0] > best[0]:
            best = cand
        if best[0] >= 99.5:
            break
    if best[0] < 99.5:
        _, d0, u0, *_ = best
        fine = [(d0 + dd, u0 + du) for dd in np.arange(-0.05, 0.051, 0.01) for du in np.arange(-0.1, 0.101, 0.02)]
        for d, u in fine:
            if 0 <= d <= 2 * nudge and d_lo <= u <= d_hi and tries < max_tries:
                cand = full(float(d), float(u))
                tries += 1
                if cand[0] > best[0]:
                    best = cand
    # tines up or down: re-test the best mapping with the runner-up transpositions
    for off in offsets[1:]:
        if tries >= max_tries:
            break
        cand = full(best[1], best[2], off)
        tries += 1
        if cand[0] > best[0]:
            best = cand
    score, delta, dur, rec, fit, ev = best
    rec["events"] = [[round(t, 3), n] for t, n in sorted(ev)]
    rec["fit"] = {**fit, "tries": tries, "duration": round(float(dur), 2), "start": round(base + float(delta), 2),
                  "nudge": round(base + float(delta) - start, 2), "offset": rec["offset"]}
    return rec


# ---------------------------------------------------------------------------
# 16 tones -> 22 physical tracks (doubled tracks let fast repeats reset)
# ---------------------------------------------------------------------------
MIN_PIN_ARC_MM = 2.0  # pins in one groove must be at least this far apart along the groove


def _gap_beats(tone: int, comb: Comb, beats: int) -> int:
    """Minimum beat spacing between two pins of one pitch: >= MIN_PIN_ARC_MM
    along the track, and a rest beat for single tines (they can't re-strike)."""
    radius = min(TRACK_RADIUS[t] for t in comb.tines[tone])
    gap = max(1, math.ceil(MIN_PIN_ARC_MM / (2 * math.pi * radius / beats)))
    return max(gap, 2) if len(comb.tines[tone]) == 1 else gap


def _can_place(partition: List[List[bool]], tone: int, b: int, comb: Comb, mono: bool = True) -> bool:
    """One pin per beat on the whole disc (unless chords are allowed) + per-pitch spacing (disc wraps)."""
    beats = len(partition[0])
    if mono and any(row[b] for row in partition):
        return False
    if not mono and partition[tone][b]:
        return False
    row = partition[tone]
    for d in range(1, _gap_beats(tone, comb, beats)):
        if row[(b - d) % beats] or row[(b + d) % beats]:
            return False
    return True


LEAN_BEATS = 4  # how far a rolled note follows the chosen direction before the other side is tried


def _nearest_free(partition: List[List[bool]], tone: int, b: int, comb: Comb, mono: bool = True,
                  reach: int = 8) -> Optional[int]:
    """Closest beat (later first) within `reach` where another pin of this pitch fits."""
    beats = len(partition[0])
    for d in range(1, reach + 1):
        for nb in (b + d, b - d):
            if 0 <= nb < beats and _can_place(partition, tone, nb, comb, mono):
                return nb
    return None


def _slide(partition: List[List[bool]], tone: int, b: int, comb: Comb, prefer: int, mono: bool = True) -> bool:
    """Move the pin at (tone, b) to the nearest free beat, leaning `prefer`
    direction for the first LEAN_BEATS. Returns False only on a full disc."""
    beats = len(partition[0])
    partition[tone][b] = False
    cands = [b + prefer * d for d in range(1, LEAN_BEATS)]
    cands += [x for d in range(LEAN_BEATS, beats) for x in (b + prefer * d, b - prefer * d)]
    cands += [b - prefer * d for d in range(1, LEAN_BEATS)]
    for nb in cands:
        if 0 <= nb < beats and _can_place(partition, tone, nb, comb, mono):
            partition[tone][nb] = True
            return True
    return False


def limit_voices(partition: List[List[bool]], voices: int, comb: Comb = DEFAULT_COMB,
                 roll: str = "before", reach: int = 4) -> Tuple[int, int]:
    """Simple chords: keep at most `voices` tines per beat — the top (melody)
    note first, then the bottom, then the middle. Extra notes roll to a beat
    within `reach` that still has room; if none has, they are dropped.
    Returns (moved, dropped)."""
    beats = len(partition[0])
    prefer = 1 if roll == "after" else -1
    load = [sum(row[b] for row in partition) for b in range(beats)]
    moved = dropped = 0
    for b in range(beats):
        hits = [t for t in range(len(partition)) if partition[t][b]]
        if len(hits) <= voices:
            continue
        keep = [hits[-1]] + ([hits[0]] if voices >= 2 else [])
        mids = sorted(hits[1:-1], key=lambda t: abs(t - (hits[0] + hits[-1]) / 2))
        keep = set(keep + mids[: max(0, voices - 2)])
        for t in hits:
            if t in keep:
                continue
            partition[t][b] = False
            load[b] -= 1
            placed = False
            for d in range(1, reach + 1):
                for nb in (b + prefer * d, b - prefer * d):
                    if 0 <= nb < beats and load[nb] < voices and _can_place(partition, t, nb, comb, mono=False):
                        partition[t][nb] = True
                        load[nb] += 1
                        placed = True
                        break
                if placed:
                    break
            if placed:
                moved += 1
            else:
                dropped += 1
    return moved, dropped


def stagger_partition(partition: List[List[bool]], comb: Comb = DEFAULT_COMB,
                      roll: str = "before") -> int:
    """The player plucks one tine at a time: notes sharing a beat are rolled
    like the factory records — the top (melody) note keeps the beat, the lower
    notes slide to the nearest free beats, leaning `before` or `after` it."""
    beats = len(partition[0])
    prefer = 1 if roll == "after" else -1
    moved = 0
    for b in range(beats):
        hits = [t for t in range(len(partition)) if partition[t][b]]
        for t in hits[:-1]:
            _slide(partition, t, b, comb, prefer=prefer)
            moved += 1
    return moved


def make_playable(partition: List[List[bool]], comb: Comb = DEFAULT_COMB) -> Tuple[int, int]:
    """Enforce per-pitch spacing in place: a single tine cannot strike on two
    consecutive beats (it is still deflected), and pins on one track must sit
    >= MIN_PIN_ARC_MM apart. The later strike slides to the nearest free beat
    (preferring later). Returns (slid, dropped) — dropped only on a full disc."""
    slid = dropped = 0
    beats = len(partition[0])
    for tone in range(len(partition)):
        row = partition[tone]
        gap = _gap_beats(tone, comb, beats)
        if gap < 2:
            continue
        b = 0
        while b < beats:
            if row[b] and any(row[(b - d) % beats] for d in range(1, gap)):
                if _slide(partition, tone, b, comb, prefer=1):
                    slid += 1
                else:
                    dropped += 1
            b += 1
    return slid, dropped


def to_physical(partition: List[List[bool]], comb: Comb = DEFAULT_COMB,
                overrides: Dict[str, int] = None) -> List[List[bool]]:
    """Pitch rows -> 22 physical tracks. Twin-tine pitches alternate between
    their two tines; `overrides` {"tone-beat": slot} pins a note to tine slot 0/1."""
    overrides = overrides or {}
    beats = len(partition[0])
    part22 = [[False] * beats for _ in range(TRACKS_COUNT)]
    for tone, tracks in enumerate(comb.tines):
        row = partition[tone]
        if len(tracks) == 1:
            part22[tracks[0]] = list(row)
            continue
        on_second = False
        for i, on in enumerate(row):
            if not on:
                continue
            slot = overrides.get(f"{tone}-{i}")
            if slot is None:
                slot = 1 if on_second else 0
            slot = int(slot) % len(tracks)
            part22[tracks[slot]][i] = True
            on_second = slot == 0
    return part22


def get_pins(part22: List[List[bool]]) -> List[Dict]:
    """Semicircular bumps on the groove walls (like the factory records).
    Even tracks ride the inner wall of a groove, odd tracks the outer wall;
    the bump is centred on the wall so it never bridges the 2 mm groove."""
    pins = []
    beats = len(part22[0])
    note_angle = 2 * math.pi / beats
    for track in range(TRACKS_COUNT):
        radius = TRACK_RADIUS[track]
        wall = radius - 0.5 if track % 2 == 0 else radius + 0.5
        direction = 1 if track % 2 == 0 else -1   # +1: bump points outward from the inner wall
        for beat in range(beats):
            if part22[track][beat]:
                angle = note_angle * beat - HEAD_OFFSET / radius
                pins.append({"wall": wall, "angle": angle, "dir": direction})
    return pins


# ---------------------------------------------------------------------------
# Mesh construction
# ---------------------------------------------------------------------------
def _cyl(radius, height, z_center, sections=160):
    c = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    c.apply_translation([0, 0, z_center])
    return c


def _annulus(inner, outer, height, z_center, sections=200):
    return trimesh.boolean.difference(
        [_cyl(outer, height, z_center, sections),
         _cyl(inner, height, z_center, sections)],
        engine="manifold",
    )


# Label text: raised letters curved around the spindle, inside the recess,
# in the ring between the centre hole (r 3.22) and the drive holes (r >= 20.25)
LABEL_R = 16.3          # baseline-centre radius of the text arc
LABEL_MAX_H = 4.6       # letter height (radial)
LABEL_MAX_ARC = 300.0   # degrees of arc the title may span
ARC_CENTRE = math.pi    # title arc centred on the left (9 o'clock), like the originals
MARK_R = 8.5            # radius of the side numeral / dash marks
MARK_H = 4.0            # numeral height
DASH_W, DASH_T = 3.0, 0.8
H_TEXT = 0.6
_FONT = dict(family="DejaVu Sans", weight="bold")
# Dedication line: a second, smaller arc inside the title (r 10.8-13.2), clear of the
# side numeral (top r 10.5) and the title (bottom r 14.0)
DEDICATION = "Dedicated To My Fiancée Barbara"
DED_R = 12.0
DED_H = 2.4
DED_ARC = 240.0
DED_CENTRE = 0.0        # centred on the right (3 o'clock), opposite the side numeral


def _flip(H):
    """Transform mapping a top-side feature onto the underside (side B)."""
    m = trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0])
    m[2, 3] += H
    return m


def _text_path(title: str):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    return TextPath((0, 0), title, size=10, prop=FontProperties(**_FONT))


def _text_scale(title: str, r: float = LABEL_R, h: float = LABEL_MAX_H, arc: float = LABEL_MAX_ARC) -> float:
    """Scale factor mapping font units -> mm so letters fit height and arc."""
    ext = _text_path(title).get_extents()
    max_len = math.radians(arc) * r
    return min(h / max(ext.height, 1e-6), max_len / max(ext.width, 1e-6))


def _text_shape(title: str, r: float = LABEL_R, h: float = LABEL_MAX_H, arc: float = LABEL_MAX_ARC):
    """Flat text outline, scaled, centred on x=0, baseline band centred on y=0."""
    from shapely.geometry import Polygon
    from shapely import affinity
    tp = _text_path(title)
    shape = None
    for ring in tp.to_polygons():
        if len(ring) < 3:
            continue
        p = Polygon(ring)
        if not p.is_valid:
            p = p.buffer(0)
        shape = p if shape is None else shape.symmetric_difference(p)
    if shape is None or shape.is_empty:
        return None
    minx, miny, maxx, maxy = shape.bounds
    s = _text_scale(title, r, h, arc)
    shape = affinity.scale(shape, s, s, origin=(0, 0))
    return affinity.translate(shape, -(minx + maxx) / 2 * s, -(miny + maxy) / 2 * s)


def _bend(shape, r: float = LABEL_R, centre: float = ARC_CENTRE):
    """Wrap a flat shape around the label arc: x -> angle, y -> radius.
    Centred on ARC_CENTRE (left side, like the factory records), reading
    clockwise with letter tops facing outward."""
    import shapely

    def warp(coords):
        x, y = coords[:, 0], coords[:, 1]
        theta = centre - x / r
        return np.column_stack([(r + y) * np.cos(theta), (r + y) * np.sin(theta)])

    dense = shapely.segmentize(shape, 0.25)
    return shapely.transform(dense, warp)


def _place(shape, angle_deg: float, radius: float):
    """Put a flat, centred shape at a polar position, tops facing outward."""
    from shapely import affinity
    shape = affinity.translate(shape, 0, radius)
    return affinity.rotate(shape, angle_deg - 90, origin=(0, 0))


def _side_marks(side_no: int):
    """Factory-style marks: record number left of the spindle, dash to the right."""
    from shapely import affinity
    from shapely.geometry import box
    marks = []
    if side_no:
        num = _text_shape(str(side_no))
        if num is not None:
            minx, miny, maxx, maxy = num.bounds
            k = MARK_H / max(maxy - miny, 1e-6)
            marks.append(_place(affinity.scale(num, k, k, origin=(0, 0)), 180, MARK_R))
    marks.append(_place(box(-DASH_W / 2, -DASH_T / 2, DASH_W / 2, DASH_T / 2), 0, MARK_R))
    return marks


def _extrude_label(shapes, H: float) -> List:
    meshes = []
    for shape in shapes:
        geoms = list(shape.geoms) if hasattr(shape, "geoms") else [shape]
        for g in geoms:
            if not g.is_valid:
                g = g.buffer(0)
            if g.is_empty or g.area < 0.05:
                continue
            for part in (g.geoms if hasattr(g, "geoms") else [g]):
                m = trimesh.creation.extrude_polygon(part, H_TEXT + OVERLAP)
                m.apply_translation([0, 0, H - H_INSET - OVERLAP])
                meshes.append(m)
    return meshes


def _text_meshes(title: str, H: float, number: int = 0, dedication: str = DEDICATION, ded_height: float = DED_H) -> List:
    title = (title or "").strip()
    shapes = []
    if title:
        shape = _text_shape(title)
        if shape is not None:
            shapes.append(_bend(shape))
    if dedication:
        ded = _text_shape(dedication, DED_R, ded_height, DED_ARC)
        if ded is not None:
            shapes.append(_bend(ded, DED_R, DED_CENTRE))
    if number:
        shapes.extend(_side_marks(number))
    return _extrude_label(shapes, H)


def label_glyphs(title: str, r: float = LABEL_R, h: float = LABEL_MAX_H, arc: float = LABEL_MAX_ARC,
                 centre: float = ARC_CENTRE) -> List[Tuple[str, float, float]]:
    """Per-character (char, angle_deg, size_mm) placements for OpenSCAD."""
    title = (title or "").strip()
    if not title:
        return []
    s = _text_scale(title, r, h, arc)
    full = _text_path(title).get_extents()
    x_centre = (full.x0 + full.x1) / 2
    out = []
    prev_x1 = 0.0
    for i, ch in enumerate(title):
        if ch.isspace():
            continue
        ext = _text_path(title[: i + 1]).get_extents()
        x_mid = (prev_x1 + ext.x1) / 2 if i else (ext.x0 + ext.x1) / 2
        prev_x1 = ext.x1
        angle = math.degrees(centre) - math.degrees((x_mid - x_centre) * s / r)
        out.append((ch, round(angle, 2), round(float(10 * s), 3)))
    return out


def _groove_cutters(H: float) -> List:
    gz = H - H_GROOVE / 2 + 0.2
    return [_annulus(inner, inner + 2, H_GROOVE + 0.4, gz) for inner in GROOVE_INNERS]


def _cam_polygon(direction: int, depth: float):
    """Plan-view pin: isosceles triangle whose base (PIN_BASE long) is buried
    PIN_SINK into the groove wall, apex `depth` into the groove at the beat."""
    from shapely.geometry import Polygon
    d = direction
    half = PIN_BASE / 2
    return Polygon([(-d * PIN_SINK, -half), (-d * PIN_SINK, half), (0.0, half),
                    (d * depth, 0.0), (0.0, -half)])


def _pin_meshes(partition: List[List[bool]], H: float, comb: Comb = DEFAULT_COMB,
                overrides: Dict[str, int] = None, pin_radius: float = R_PIN) -> List:
    pins = get_pins(to_physical(partition, comb, overrides))
    out = []
    z0 = H - H_GROOVE - OVERLAP
    cams = {d: trimesh.creation.extrude_polygon(_cam_polygon(d, pin_radius), H_GROOVE + OVERLAP)
            for d in (1, -1)}
    for p in pins:
        cam = cams[p["dir"]].copy()
        cam.apply_translation([p["wall"], 0, z0])
        cam.apply_transform(trimesh.transformations.rotation_matrix(p["angle"], [0, 0, 1]))
        out.append(cam)
    return out


def build_mesh(partition: List[List[bool]], thickness: float = 3.0,
               title: str = "", partition_b: List[List[bool]] = None,
               title_b: str = "", marks: bool = True, record_no: int = 6,
               comb: Comb = DEFAULT_COMB, overrides: Dict = None, overrides_b: Dict = None,
               pin_radius: float = R_PIN, flat_back: bool = False,
               ded_height: float = DED_H, ded_b: bool = True):
    H = float(thickness)
    base = _cyl(R_STOCK, H, H / 2)
    two_sided = partition_b is not None
    flip = _flip(H)

    cutters = []
    # centre + drive holes (through)
    cutters.append(_cyl(R_CENTER, H + 1, H / 2))
    for dx, dy in [(0, O_DRIVE), (0, -O_DRIVE), (O_DRIVE, 0), (-O_DRIVE, 0)]:
        c = _cyl(R_DRIVE, H + 1, H / 2)
        c.apply_translation([dx, dy, 0])
        cutters.append(c)
    # recessed label area top & bottom
    cutters.append(_cyl(R_INSET, H_INSET + 0.4, H - H_INSET / 2 + 0.2))
    if not flat_back:
        cutters.append(_cyl(R_INSET, H_INSET + 0.4, H_INSET / 2 - 0.2))
    # note grooves (annular channels cut into the top, and bottom for side B)
    cutters.extend(_groove_cutters(H))
    if two_sided:
        for g in _groove_cutters(H):
            g.apply_transform(flip)
            cutters.append(g)

    all_cuts = trimesh.boolean.union(cutters, engine="manifold")
    disc = trimesh.boolean.difference([base, all_cuts], engine="manifold")

    # pins (bumps) refill groove segments up to the surface
    adds = _pin_meshes(partition, H, comb, overrides, pin_radius)
    pin_count = len(adds)
    adds.extend(_text_meshes(title, H, record_no if marks else 0, DEDICATION, ded_height))
    if two_sided:
        side_b = _pin_meshes(partition_b, H, comb, overrides_b, pin_radius)
        pin_count += len(side_b)
        side_b.extend(_text_meshes(title_b, H, record_no if marks else 0, DEDICATION if ded_b else "", ded_height))
        for m in side_b:
            m.apply_transform(flip)
        adds.extend(side_b)

    if adds:
        adds_union = trimesh.boolean.union(adds, engine="manifold")
        disc = trimesh.boolean.union([disc, adds_union], engine="manifold")

    return disc, pin_count


# ---------------------------------------------------------------------------
# .fpr (tracker) and .scad (OpenSCAD) exporters
# ---------------------------------------------------------------------------
def to_fpr(partition: List[List[bool]], title: str) -> str:
    """Music-box tune-tracker text format: one row of + / - per pitch, then title."""
    beats = len(partition[0])
    lines = ["".join("+" if row[b] else "-" for b in range(beats)) for row in partition]
    return "\n".join(lines) + "\n" + (title or "Untitled") + "\n"


_SCAD_TEMPLATE = '''/* Generated by Fisher-Price Record Maker on {DATE_TIME}
 * Printable disc for the vintage Fisher-Price Music Box Record Player.
 * Based on "Fred's Fisher Price record creator" template.
 * Side A: {TITLE_A}
 * Side B: {TITLE_B}
 */

$fn = 100;
hStock = {THICKNESS};
rStock = 60.58;
oDrive = 21.8;
rDrive = 1.55;
hInset = 1;
rInset = 25.6;
hGroove = 1.2;
overlap = 0.2;
twoSided = {TWO_SIDED};
labelA = "{TITLE_A}";
labelB = "{TITLE_B}";
labelR = 16.3;
dedR = {DED_R};       // "{DEDICATION}" — small arc inside the title
markR = 8.5;
hText = 0.6;
pinDepth = {PIN_R};
pinBase = {PIN_BASE};
pinSink = {PIN_SINK};

module createDisc() {{
        union() {{
                createBlank();
                // Curved label text (dynamically generated)
{LABELS}
                // Notes (dynamically generated)
{NOTES}
        }}
}}

module createBlank() {{
        difference() {{
                cylinder(h=hStock, r=rStock);
                translate(v=[0,0,hStock-hInset+overlap]) {{ cylinder(h=hInset+overlap, r=rInset); }}
                translate(v=[0,0,-overlap]) {{ cylinder(h=hInset+overlap, r=rInset); }}
                cylinder(h=hStock, r=3.22);
                translate(v=[0,oDrive,0]) {{ cylinder(h=hStock, r=rDrive); }}
                translate(v=[0,-oDrive,0]) {{ cylinder(h=hStock, r=rDrive); }}
                translate(v=[oDrive,0,0]) {{ cylinder(h=hStock, r=rDrive); }}
                translate(v=[-oDrive,0,0]) {{ cylinder(h=hStock, r=rDrive); }}
                tracks(false);
                if (twoSided) tracks(true);
        }}
}}

// Maps a top-surface feature onto the underside (flip the disc over)
module onSide(onSecondSide) {{
        if (onSecondSide) {{ translate(v=[0,0,hStock]) rotate(a=[180,0,0]) children(); }}
        else {{ children(); }}
}}

module tracks(onSecondSide) {{
        onSide(onSecondSide) {{
                track(28.15); track(30.89); track(33.71); track(36.425); track(39.225);
                track(42); track(44.825); track(47.555); track(50.315); track(53.11); track(55.9);
        }}
}}

module track(inner) {{
        translate(v=[0,0,hStock-hGroove]) {{
                difference() {{
                        cylinder(h=hGroove+overlap, r=inner+2);
                        cylinder(h=hGroove+overlap, r=inner);
                }}
        }}
}}

// One letter of the title, standing on the arc of radius labelR at the given angle
module glyph(ch, angle, size, onSecondSide) {{
        mark(ch, angle, labelR, size, onSecondSide);
}}

// Raised character at a polar position, letter top facing outward
module mark(ch, angle, r, size, onSecondSide) {{
        onSide(onSecondSide) rotate(a=angle-90) translate(v=[0, r, hStock-hInset-overlap]) {{
                linear_extrude(height=hText+overlap) {{
                        text(ch, size=size, halign="center", valign="center", font="DejaVu Sans:style=Bold");
                }}
        }}
}}

// Factory-style dash mark to the right of the spindle
module dash(onSecondSide) {{
        onSide(onSecondSide) translate(v=[markR, 0, hStock-hInset-overlap]) {{
                linear_extrude(height=hText+overlap) {{ square(size=[3, 0.8], center=true); }}
        }}
}}

// Note pin: isosceles triangle on a groove wall, base pinBase long and buried pinSink
// into the wall, apex pinDepth into the groove at the beat
// dir = 1 -> on the inner wall pointing outward, -1 -> on the outer wall pointing inward
module pin(wall, angle, dir, onSecondSide) {{
        half = pinBase / 2;
        onSide(onSecondSide) rotate(a=angle) translate(v=[wall, 0, hStock-hGroove-overlap]) {{
                linear_extrude(height=hGroove+overlap) {{
                        polygon(points=[[-dir*pinSink, -half], [-dir*pinSink, half], [0, half], [dir*pinDepth, 0], [0, -half]]);
                }}
        }}
}}

createDisc();
'''


def _scad_pins(partition, side_flag, comb=DEFAULT_COMB, overrides=None):
    lines = []
    for p in get_pins(to_physical(partition, comb, overrides)):
        deg = math.degrees(p["angle"])
        lines.append(f"\t\tpin({round(p['wall'], 3)},{round(deg, 3)},{p['dir']},{side_flag});")
    return lines


def _scad_str(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def to_scad(partition: List[List[bool]], thickness: float, title: str,
            partition_b: List[List[bool]] = None, title_b: str = "",
            label_a: str = None, label_b: str = None, marks: bool = True,
            record_no: int = 6, comb: Comb = DEFAULT_COMB,
            overrides: Dict = None, overrides_b: Dict = None,
            pin_radius: float = R_PIN, ded_height: float = DED_H, ded_b: bool = True) -> str:
    label_a = title if label_a is None else label_a
    label_b = title_b if label_b is None else label_b
    lines = _scad_pins(partition, "false", comb, overrides)
    if partition_b is not None:
        lines.append("\t\t// Side B")
        lines.extend(_scad_pins(partition_b, "true", comb, overrides_b))
    labels = [f'\t\tglyph("{_scad_str(ch)}",{ang},{size},false);'
              for ch, ang, size in label_glyphs(label_a)]
    ded = lambda side: [f'\t\tmark("{_scad_str(ch)}",{ang},dedR,{size},{side});'
                        for ch, ang, size in label_glyphs(DEDICATION, DED_R, ded_height, DED_ARC, DED_CENTRE)]
    labels += ded("false")
    if marks:
        labels += [f'\t\tmark("{record_no}",180,markR,3.2,false);', '\t\tdash(false);']
    if partition_b is not None:
        labels += [f'\t\tglyph("{_scad_str(ch)}",{ang},{size},true);'
                   for ch, ang, size in label_glyphs(label_b)]
        if ded_b:
            labels += ded("true")
        if marks:
            labels += [f'\t\tmark("{record_no}",180,markR,3.2,true);', '\t\tdash(true);']
    from datetime import datetime
    return _SCAD_TEMPLATE.format(
        DATE_TIME=datetime.now().strftime("%d %b %Y %H:%M"),
        THICKNESS=thickness,
        PIN_R=pin_radius,
        PIN_BASE=PIN_BASE,
        PIN_SINK=PIN_SINK,
        DED_R=DED_R,
        DEDICATION=_scad_str(DEDICATION),
        TWO_SIDED="true" if partition_b is not None else "false",
        TITLE_A=_scad_str(title),
        TITLE_B=_scad_str(title_b) if partition_b is not None else "",
        LABELS="\n".join(labels),
        NOTES="\n".join(lines),
    )


def analyze(midi_bytes: bytes, duration: float = 25.0, start: float = 0.0,
            auto_transpose: bool = True, manual_offset: int = 0,
            comb: Comb = DEFAULT_COMB, roll: str = "before", rev_seconds: float = 25.0,
            tracks: Optional[List[int]] = None, skyline: bool = False, melody_fill: bool = False,
            chords: bool = False, voices: int = 16) -> Dict:
    """MIDI window -> editable pitch x 86 partition plus mapping stats."""
    events = parse_midi_events(midi_bytes, duration, start, tracks, skyline, melody_fill)
    rec = events_to_record(events, duration, auto_transpose, manual_offset, comb, stagger=not chords, roll=roll, voices=voices)
    rec["events"] = [[round(t, 3), n] for t, n in sorted(events)]
    rec["fit"] = compare_fit(events, rec["offset"], rec["partition"], duration, rev_seconds, comb) if events else None
    return _finish_analysis(rec, duration, start)


REAL_PITCH_OFFSET = -4   # the toy's comb sounds 4 semitones below Fred's notation (A-flat major)
RENDER_RATE = 8000       # review audio: 8 kHz mono, like the toy's own tinny voice


def plan_song(midi_bytes: bytes, comb: Comb, tracks: Optional[List[int]], skyline: bool,
              duration: float, rev_seconds: float, roll: str, auto_transpose: bool,
              manual_offset: int, melody_fill: bool = False, chords: bool = False, voices: int = 16) -> Dict:
    """Slice the whole song (selected tracks) into consecutive 86-beat sides
    with one transposition and one tempo. duration <= 0 auto-fits the tempo."""
    allev = parse_midi_events(midi_bytes, 36000.0, 0.0, tracks, skyline, melody_fill)
    if not allev:
        raise ValueError("No playable notes in the selected tracks")
    first, last = allev[0][0], allev[-1][0]
    start, fit = max(0.0, first - 0.2), None
    if duration <= 0:
        rec = auto_fit(midi_bytes, start, rev_seconds, comb, roll, auto_transpose, manual_offset,
                       12000, 0.35, 0.5, tracks, skyline, melody_fill, chords, voices)
        fit, duration, start = rec["fit"], rec["fit"]["duration"], rec["fit"]["start"]
    offset = (fit["offset"] if fit else choose_transposition([n for _, n in allev], comb)) if auto_transpose else manual_offset
    n_sides = max(1, math.ceil((last - start + 0.01) / duration))
    sides = [analyze(midi_bytes, duration, start + k * duration, False, offset, comb, roll, rev_seconds,
                     tracks, skyline, melody_fill, chords, voices) for k in range(n_sides)]
    return {"sides": sides, "duration": duration, "start": start, "offset": offset, "fit": fit,
            "note_count": sum(s["note_count"] for s in sides)}


def render_song(sides: List[Dict], rev_seconds: float, comb: Comb = DEFAULT_COMB,
                rate: int = RENDER_RATE, side_gap: float = 0.6) -> bytes:
    """Mono 16-bit WAV of the whole song as the toy will play it: every pin is
    a plucked tine (decaying partials below Nyquist) at toy pitch and toy speed."""
    import struct
    beat_sec = rev_seconds / MAX_BEAT
    onsets = []
    cursor = 0.0
    for part in sides:
        p = part["partition"]
        for tone, row in enumerate(p):
            for b, on in enumerate(row):
                if on:
                    onsets.append((cursor + b * beat_sec, comb.notes[tone] + REAL_PITCH_OFFSET))
        cursor += rev_seconds + side_gap
    total = int((cursor + 1.5) * rate)
    audio = np.zeros(total, dtype=np.float32)
    dur = 1.2
    n = int(dur * rate)
    t = np.arange(n) / rate
    env = np.exp(-t * 4.5) * (1 - np.exp(-t * 400))
    for when, midi in onsets:
        f0 = 440.0 * 2 ** ((midi - 69) / 12)
        tone = np.zeros(n, dtype=np.float32)
        for k, amp, decay in ((1, 1.0, 1.0), (2.76, 0.35, 2.2), (5.4, 0.12, 3.5)):
            if f0 * k < rate / 2:
                tone += amp * np.sin(2 * np.pi * f0 * k * t) * np.exp(-t * decay * 2)
        i0 = int(when * rate)
        seg = min(n, total - i0)
        if seg > 0:
            audio[i0:i0 + seg] += (tone * env)[:seg]
    peak = float(np.abs(audio).max()) or 1.0
    pcm = (audio / peak * 0.85 * 32767).astype("<i2").tobytes()
    header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(pcm), b"WAVE", b"fmt ", 16, 1, 1,
                         rate, rate * 2, 2, 16, b"data", len(pcm))
    return header + pcm


def chord_test_partition(comb: Comb = DEFAULT_COMB) -> List[List[bool]]:
    """One phrase three ways on one disc: single notes, two-note chords, triads.
    Beats 2-14 ONE · 30-42 TWO · 58-70 THREE (rests between so you can tell them apart)."""
    p = [[False] * MAX_BEAT for _ in range(comb.tones)]
    melody = [3, 4, 5, 3, 2, 1]                 # E5 G5 A5 E5 D5 C5 in Fred's notation (tones)
    harmony2 = [[1], [2], [3], [1], [0], [0]]  # a third / fifth below
    harmony3 = [[1, 0], [2, 0], [3, 1], [1, 0], [0, 1], [0, 3]]
    for section, extra in ((2, None), (30, harmony2), (58, harmony3)):
        for i, tone in enumerate(melody):
            b = section + i * 2
            p[tone][b] = True
            if extra:
                for t in extra[i]:
                    p[t][b] = True
    return p


def _finish_analysis(rec: Dict, duration: float, start: float) -> Dict:
    rec["notes_used"] = [{"midi": m, "name": note_name(m)} for m in rec["notes_used"]]
    rec["duration"] = duration
    rec["start"] = start
    rec["beats"] = MAX_BEAT
    return rec


def heal_mesh(mesh: trimesh.Trimesh) -> Tuple[trimesh.Trimesh, Dict]:
    """Printer pre-flight: merge seams, drop duplicate/degenerate triangles,
    fix mismatched (inverted) windings, fill holes, then verify watertight."""
    faces_before = int(len(mesh.faces))
    open_edges_before = int((trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)).shape[0])
    winding_ok_before = bool(mesh.is_winding_consistent)
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    after_dupes = int(len(mesh.faces))
    mesh.update_faces(mesh.nondegenerate_faces())
    after_degen = int(len(mesh.faces))
    flipped = 0
    if not mesh.is_winding_consistent:
        before = mesh.faces.copy()
        trimesh.repair.fix_winding(mesh)
        flipped = int((before != mesh.faces).any(axis=1).sum())
    holes_filled = 0
    if open_edges_before or not mesh.is_watertight:
        n0 = len(mesh.faces)
        trimesh.repair.fill_holes(mesh)
        holes_filled = int(len(mesh.faces) - n0)
    if mesh.is_watertight and mesh.volume < 0:
        mesh.invert()
        flipped += int(len(mesh.faces))
    trimesh.repair.fix_normals(mesh)
    open_edges_after = int((trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)).shape[0])
    report = {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "winding_was_consistent": winding_ok_before,
        "open_edges_before": open_edges_before,
        "open_edges_after": open_edges_after,
        "holes_filled": holes_filled,
        "duplicate_faces_removed": faces_before - after_dupes,
        "degenerate_faces_removed": after_dupes - after_degen,
        "flipped_faces_fixed": flipped,
        "faces": int(len(mesh.faces)),
        "volume_mm3": round(float(abs(mesh.volume)), 1) if mesh.is_watertight else None,
        "bodies": int(len(mesh.split(only_watertight=False))) if mesh.is_watertight else None,
    }
    report["ok"] = report["watertight"] and report["winding_consistent"] and open_edges_after == 0
    return mesh, report


def _stl(mesh) -> bytes:
    b = mesh.export(file_type="stl")
    return b.encode() if isinstance(b, str) else bytes(b)


def press(partition: List[List[bool]], title: str, thickness: float = 3.0,
          partition_b: List[List[bool]] = None, title_b: str = "",
          engrave: bool = True, record_no: int = 6, comb: Comb = DEFAULT_COMB,
          overrides: Dict = None, overrides_b: Dict = None,
          pin_radius: float = R_PIN, roll: str = "before", chords: bool = False, voices: int = 16,
          ded_height: float = DED_H, ded_b: bool = True) -> Dict:
    """Partition(s) -> STL / SCAD / FPR files. Two-sided discs also get two
    flat-backed halves to print pins-up and glue back to back (no supports)."""
    label_a = title if engrave else ""
    label_b = title_b if engrave else ""
    toy_fixes = (sum(limit_voices(partition, voices, comb, roll)) if chords else stagger_partition(partition, comb, roll)) + sum(make_playable(partition, comb))
    if partition_b is not None:
        toy_fixes += (sum(limit_voices(partition_b, voices, comb, roll)) if chords else stagger_partition(partition_b, comb, roll)) + sum(make_playable(partition_b, comb))
    ded_height = max(2.0, min(3.5, float(ded_height)))
    common = dict(marks=engrave, record_no=record_no, comb=comb, pin_radius=pin_radius, ded_height=ded_height, ded_b=ded_b)
    mesh, pin_count = build_mesh(partition, thickness, label_a, partition_b, label_b,
                                 overrides=overrides, overrides_b=overrides_b, **common)
    mesh, mesh_check = heal_mesh(mesh)
    stl_bytes = _stl(mesh)
    halves = {}
    if partition_b is not None:
        half = thickness / 2
        ha, _ = build_mesh(partition, half, label_a, overrides=overrides, flat_back=True, **common)
        hb, _ = build_mesh(partition_b, half, label_b, overrides=overrides_b, flat_back=True, **common)
        ha, rep_a = heal_mesh(ha)
        hb, rep_b = heal_mesh(hb)
        mesh_check["halves_ok"] = bool(rep_a["ok"] and rep_b["ok"])
        halves = {"stl_half_a": _stl(ha), "stl_half_b": _stl(hb)}
    used = sorted({comb.notes[t] for part in (partition, partition_b or [])
                   for t, row in enumerate(part) if any(row)})
    return {
        "stl": stl_bytes,
        **halves,
        "fpr": to_fpr(partition, title),
        "fpr_b": to_fpr(partition_b, title_b) if partition_b is not None else None,
        "scad": "// Fisher-Price Record Maker - Dedicated To My Fiancee Barbara - Copyright 2026 Russ Campbell. All rights reserved.\n" + to_scad(partition, thickness, title, partition_b, title_b, label_a, label_b,
                        marks=engrave, record_no=record_no, comb=comb,
                        overrides=overrides, overrides_b=overrides_b, pin_radius=pin_radius,
                        ded_height=ded_height, ded_b=ded_b),
        "stats": {
            "pin_count": pin_count,
            "pin_radius": pin_radius,
            "ded_height": ded_height,
            "ded_b": ded_b,
            "toy_fixes": toy_fixes,
            "mesh_check": mesh_check,
            "roll": roll,
            "thickness": thickness,
            "beats": MAX_BEAT,
            "triangles": int(len(mesh.faces)),
            "notes_used": [{"midi": m, "name": note_name(m)} for m in used],
            "two_sided": partition_b is not None,
        },
    }


def generate_stl(midi_bytes: bytes, duration: float = 25.0,
                 thickness: float = 3.0, auto_transpose: bool = True,
                 manual_offset: int = 0, title: str = "Record",
                 record_no: int = 6) -> Dict:
    rec = analyze(midi_bytes, duration, 0.0, auto_transpose, manual_offset)
    out = press(rec["partition"], title, thickness, record_no=record_no)
    out["stats"]["staggered"] = rec["staggered"]
    out["stats"].update({
        "note_count": rec["note_count"],
        "exact": rec["exact"],
        "adjusted": rec["adjusted"],
        "merged": rec["merged"],
        "offset": rec["offset"],
        "duration": duration,
    })
    out["partition"] = rec["partition"]
    return out


# ---------------------------------------------------------------------------
# Factory tune library (the 10 nursery rhymes shipped with the 1971/1977 player),
# transcribed by ear as NOTE[:beats] in quarter-note units.
# ---------------------------------------------------------------------------
LIBRARY = [
    ("Twinkle Twinkle Little Star", "C5 C5 G5 G5 A5 A5 G5:2 F5 F5 E5 E5 D5 D5 C5:2 "
     "G5 G5 F5 F5 E5 E5 D5:2 G5 G5 F5 F5 E5 E5 D5:2 C5 C5 G5 G5 A5 A5 G5:2 F5 F5 E5 E5 D5 D5 C5:2"),
    ("Au Clair de la Lune", "C5 C5 C5 D5 E5:2 D5:2 C5 E5 D5 D5 C5:4 "
     "C5 C5 C5 D5 E5:2 D5:2 C5 E5 D5 D5 C5:4 D5 D5 D5 D5 A4:2 A4:2 D5 C5 B4 A4 G4:4"),
    ("Humpty Dumpty", "E5 G5 G5 E5 C5 D5 E5:2 F5 A5 A5 F5 D5 E5 F5:2 "
     "G5 G5 G5 E5 C5 D5 E5:2 F5 F5 F5 D5 B4 C5 D5:2 E5 F5 G5 A5 G5 F5 E5:2 D5 E5 F5 G5 F5 E5 D5:2 "
     "E5 F5 G5 A5 G5 F5 E5 D5 C5:3"),
    ("Jack and Jill", "G5 G5 A5 A5 B5 B5 C6:2 B5 B5 A5 A5 G5:3 "
     "G5 G5 A5 A5 B5 B5 C6:2 B5 B5 A5 A5 G5:3 D5 D5 E5 F5 G5 G5 A5:2 B5 B5 A5 G5 A5:3 G5 G5 A5 B5 C6 C6 B5 A5 G5:3"),
    ("Oh Where Has My Little Dog Gone", "G5:2 E5 C5:2 E5 G5:3 G5:2 E5 C5:2 E5 G5:3 "
     "A5 A5 A5 G5:2 F5 E5 E5 E5 D5:3 G5:2 E5 C5:2 E5 G5:3 A5:2 B5 C6:2 B5 A5 G5 F5 E5 D5 C5:3"),
    ("London Bridge", "G5 A5 G5 F5 E5 F5 G5:2 D5 E5 F5:2 E5 F5 G5:2 "
     "G5 A5 G5 F5 E5 F5 G5:2 D5:2 G5:2 E5 C5:3"),
    ("Edelweiss", "E5 G5 D6:3 C6 G5 F5:3 E5 E5 E5 F5 G5 A5:3 G5:3 "
     "E5 G5 D6:3 C6 G5 F5:3 E5 G5 G5 A5 B5 C6:3 C6:3 D6 G5 G5 B5 A5 G5 E5 G5 C6:3 A5 D6 C6 D6:3 B5 D6:3 "
     "E5 G5 D6:3 C6 G5 F5:3 E5 G5 G5 A5 B5 C6:3 C6:3"),
    ("Children's Prayer", "E5 D5 C5 D5 E5 E5 E5:2 D5 D5 D5:2 E5 G5 G5:2 "
     "E5 D5 C5 D5 E5 E5 E5 E5 D5 D5 E5 D5 C5:3 G5 G5 F5 D5 E5 E5 E5:2 G5 G5 F5 D5 E5 E5 E5:2 "
     "E5 D5 C5 D5 E5 E5 E5 E5 D5 D5 E5 D5 C5:3"),
    ("Camptown Races", "G5 G5 E5 G5 A5 G5 E5:2 E5 D5:3 E5 D5:3 "
     "G5 G5 E5 G5 A5 G5 E5:2 D5 E5 D5 C5:3 C5 E5 G5:3 A5 C6 A5 G5:3 "
     "G5 G5 E5 G5 A5 G5 E5:2 D5 E5 D5 C5:3"),
    ("Hickory Dickory Dock", "E5 D5 C5 E5 D5 C5:2 G5 A5 G5 F5 E5 D5:2 "
     "E5 F5 G5 A5 B5 C6:2 B5 A5 G5 F5 E5 D5 C5:3 E5 D5 C5 E5 D5 C5:2 G5 A5 G5 F5 E5 D5 C5:3"),
]
_NAME_TO_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def parse_note_name(name: str) -> int:
    """'G#5' / 'Bb4' / 'C5' -> MIDI number."""
    s = name.strip().upper().replace("♯", "#").replace("♭", "B")
    m = re.fullmatch(r"([A-G])([#B]?)(-?\d)", s)
    if not m:
        raise ValueError(f"bad note name: {name}")
    semi = _NAME_TO_SEMI[m.group(1)] + (1 if m.group(2) == "#" else -1 if m.group(2) == "B" else 0)
    return (int(m.group(3)) + 1) * 12 + semi


def melody_events(melody: str, duration: float) -> List[Tuple[float, int]]:
    """Fit a NOTE[:beats] melody into `duration` seconds (small tail gap)."""
    steps = []
    for tok in melody.split():
        name, _, length = tok.partition(":")
        steps.append((parse_note_name(name), float(length or 1)))
    total = sum(l for _, l in steps)
    scale = duration * 0.96 / total
    events, t = [], 0.0
    for midi, length in steps:
        events.append((t * scale, midi))
        t += length
    return events


def library(duration: float = 25.0, comb: Comb = DEFAULT_COMB) -> List[Dict]:
    out = []
    for title, melody in LIBRARY:
        rec = events_to_record(melody_events(melody, duration), duration, True, 0, comb)
        out.append({"title": title, "analysis": _finish_analysis(rec, duration, 0.0)})
    return out
