"""
Fisher-Price Music Box Record generator.

Ports the geometry/algorithm from the "Fisher Price Music Box Record Creator"
(Fred's Fisher Price record creator template) to pure Python, producing a
printable STL for the vintage 1977 Fisher-Price Music Box Record Player.

The physical record is a flat disc with raised bumps ("pins") arranged in
concentric tracks. As the disc rotates, the pins pluck the music box tines.
"""
import math
import io
from typing import List, Dict, Tuple

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

# Groove inner radii (11 grooves, each holds two note tracks)
GROOVE_INNERS = [28.15, 30.89, 33.71, 36.425, 39.225, 42,
                 44.825, 47.555, 50.315, 53.11, 55.9]

# The 16 physical tine pitches (MIDI note numbers), low -> high
NOTES = [67, 72, 74, 76, 79, 81, 83, 84, 86, 88, 89, 91, 93, 95, 96, 98]
TONES_COUNT = 16
TRACKS_COUNT = 22
MAX_BEAT = 86         # beats (angular steps) per full revolution

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
def parse_midi_events(midi_bytes: bytes, duration: float) -> List[Tuple[float, int]]:
    """Return [(time_seconds, midi_note)] for note-on events in the first
    `duration` seconds."""
    import mido
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    events: List[Tuple[float, int]] = []
    t = 0.0
    for msg in mid:
        t += msg.time
        if t > duration:
            break
        if msg.type == "note_on" and msg.velocity > 0:
            events.append((t, msg.note))
    return events


def choose_transposition(notes: List[int]) -> int:
    """Find the semitone offset that lands the most notes exactly on the
    playable tine set (tie-break: smallest total snap distance)."""
    allowed = set(NOTES)
    lo, hi = min(NOTES), max(NOTES)
    best_offset, best_score = 0, None
    for offset in range(-48, 49):
        exact = 0
        dist = 0
        for n in notes:
            m = n + offset
            if m in allowed:
                exact += 1
            dist += min(abs(m - a) for a in NOTES)
        # center of mass must be roughly in range to avoid absurd shifts
        avg = (sum(notes) / len(notes)) + offset
        if not (lo - 6 <= avg <= hi + 6):
            continue
        score = (exact, -dist)
        if best_score is None or score > best_score:
            best_score = score
            best_offset = offset
    return best_offset


def snap_note(midi: int) -> int:
    return min(NOTES, key=lambda a: abs(a - midi))


def events_to_record(events: List[Tuple[float, int]], duration: float,
                     auto_transpose: bool = True,
                     manual_offset: int = 0) -> Dict:
    """Quantize note events onto a 16-tone x MAX_BEAT grid."""
    partition = [[False] * MAX_BEAT for _ in range(TONES_COUNT)]
    raw_notes = [n for _, n in events]

    offset = 0
    if raw_notes:
        offset = choose_transposition(raw_notes) if auto_transpose else manual_offset

    exact = adjusted = 0
    used = set()
    for t, n in events:
        m = n + offset
        snapped = m if m in NOTES else snap_note(m)
        if m in NOTES:
            exact += 1
        else:
            adjusted += 1
        tone = NOTES.index(snapped)
        beat = int(round(t / duration * MAX_BEAT)) if duration > 0 else 0
        beat = max(0, min(MAX_BEAT - 1, beat))
        partition[tone][beat] = True
        used.add(snapped)

    return {
        "partition": partition,
        "offset": offset,
        "exact": exact,
        "adjusted": adjusted,
        "notes_used": sorted(used),
        "note_count": len(events),
    }


# ---------------------------------------------------------------------------
# 16 tones -> 22 physical tracks (doubled tracks let fast repeats reset)
# ---------------------------------------------------------------------------
def _split(part22, first, second, beats):
    on_second = False
    for i, on in enumerate(beats):
        if on:
            part22[second if on_second else first][i] = True
            on_second = not on_second


def to_physical(partition: List[List[bool]]) -> List[List[bool]]:
    beats = len(partition[0])
    part22 = [[False] * beats for _ in range(TRACKS_COUNT)]
    for tone in range(TONES_COUNT):
        track = partition[tone]
        if tone < 7:
            part22[tone] = list(track)
        elif tone == 7:
            _split(part22, 7, 8, track)
        elif tone == 8:
            _split(part22, 9, 10, track)
        elif tone == 9:
            _split(part22, 11, 12, track)
        elif tone == 10:
            _split(part22, 13, 14, track)
        elif tone == 11:
            _split(part22, 15, 16, track)
        elif tone == 12:
            _split(part22, 17, 18, track)
        else:  # 13, 14, 15
            part22[tone + 6] = list(track)
    return part22


def get_pins(part22: List[List[bool]]) -> List[Dict]:
    pins = []
    beats = len(part22[0])
    note_angle = 2 * math.pi / beats
    for track in range(TRACKS_COUNT):
        inner = TRACK_RADIUS[track] - 0.5 - (OVERLAP if track % 2 == 0 else 0)
        outer = inner + 1 + OVERLAP
        radius = TRACK_RADIUS[track]
        for beat in range(beats):
            if part22[track][beat]:
                angle = note_angle * beat - HEAD_OFFSET / radius
                pins.append({"inner": inner, "outer": outer, "angle": angle})
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


def build_mesh(partition: List[List[bool]], thickness: float = 3.0):
    H = float(thickness)
    base = _cyl(R_STOCK, H, H / 2)

    cutters = []
    # centre + drive holes (through)
    cutters.append(_cyl(R_CENTER, H + 1, H / 2))
    for dx, dy in [(0, O_DRIVE), (0, -O_DRIVE), (O_DRIVE, 0), (-O_DRIVE, 0)]:
        c = _cyl(R_DRIVE, H + 1, H / 2)
        c.apply_translation([dx, dy, 0])
        cutters.append(c)
    # recessed label area top & bottom
    cutters.append(_cyl(R_INSET, H_INSET + 0.4, H - H_INSET / 2 + 0.2))
    cutters.append(_cyl(R_INSET, H_INSET + 0.4, H_INSET / 2 - 0.2))
    # note grooves (annular channels cut into the top)
    gz = H - H_GROOVE / 2 + 0.2
    for inner in GROOVE_INNERS:
        cutters.append(_annulus(inner, inner + 2, H_GROOVE + 0.4, gz))

    all_cuts = trimesh.boolean.union(cutters, engine="manifold")
    disc = trimesh.boolean.difference([base, all_cuts], engine="manifold")

    # pins (bumps) refill groove segments up to the top surface
    pins = get_pins(to_physical(partition))
    pin_meshes = []
    pz = H - (H_GROOVE + OVERLAP) / 2
    for p in pins:
        box = trimesh.creation.box(extents=[p["outer"] - p["inner"], 1.0,
                                            H_GROOVE + OVERLAP])
        box.apply_translation([p["inner"] + (p["outer"] - p["inner"]) / 2, 0, pz])
        box.apply_transform(trimesh.transformations.rotation_matrix(
            p["angle"], [0, 0, 1]))
        pin_meshes.append(box)

    if pin_meshes:
        pins_union = trimesh.boolean.union(pin_meshes, engine="manifold")
        disc = trimesh.boolean.union([disc, pins_union], engine="manifold")

    return disc, len(pins)


# ---------------------------------------------------------------------------
# .fpr (tracker) and .scad (OpenSCAD) exporters
# ---------------------------------------------------------------------------
def to_fpr(partition: List[List[bool]], title: str) -> str:
    """Music-box tune-tracker text format: 16 tone rows of + / - then title."""
    beats = len(partition[0])
    lines = []
    for tone in range(TONES_COUNT):
        lines.append("".join("+" if partition[tone][b] else "-" for b in range(beats)))
    return "\n".join(lines) + "\n" + (title or "Untitled") + "\n"


_SCAD_TEMPLATE = '''/* Generated by Fisher-Price Record Maker on {DATE_TIME}
 * Printable disc for the vintage Fisher-Price Music Box Record Player.
 * Based on "Fred's Fisher Price record creator" template.
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

module createDisc() {{
	union() {{
		createBlank();
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

module pin(inner, outer, angle, onSecondSide) {{
	rotate(a=angle) {{
		translate(v=[inner, -0.5, hStock-hGroove-overlap]) {{
			cube(size=[outer-inner, 1, hGroove+overlap], center=false);
		}}
	}}
}}

createDisc();
'''


def to_scad(partition: List[List[bool]], thickness: float, title: str) -> str:
    pins = get_pins(to_physical(partition))
    lines = []
    for p in pins:
        deg = math.degrees(p["angle"])
        lines.append(f"\t\tpin({round(p['inner'], 3)},{round(p['outer'], 3)},"
                     f"{round(deg, 3)},0);")
    from datetime import datetime
    return _SCAD_TEMPLATE.format(
        DATE_TIME=datetime.now().strftime("%d %b %Y %H:%M"),
        THICKNESS=thickness,
        NOTES="\n".join(lines),
    )


def generate_stl(midi_bytes: bytes, duration: float = 25.0,
                 thickness: float = 3.0, auto_transpose: bool = True,
                 manual_offset: int = 0, title: str = "Record") -> Dict:
    events = parse_midi_events(midi_bytes, duration)
    rec = events_to_record(events, duration, auto_transpose, manual_offset)
    mesh, pin_count = build_mesh(rec["partition"], thickness)
    stl_bytes = mesh.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode()

    stats = {
        "note_count": rec["note_count"],
        "exact": rec["exact"],
        "adjusted": rec["adjusted"],
        "offset": rec["offset"],
        "pin_count": pin_count,
        "duration": duration,
        "thickness": thickness,
        "beats": MAX_BEAT,
        "notes_used": [{"midi": m, "name": note_name(m)} for m in rec["notes_used"]],
        "triangles": int(len(mesh.faces)),
    }
    return {
        "stl": bytes(stl_bytes),
        "fpr": to_fpr(rec["partition"], title),
        "scad": to_scad(rec["partition"], thickness, title),
        "stats": stats,
    }
