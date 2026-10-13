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
def parse_midi_events(midi_bytes: bytes, duration: float,
                      start: float = 0.0) -> List[Tuple[float, int]]:
    """Return [(time_seconds, midi_note)] for note-on events in the window
    [start, start + duration), times relative to `start`."""
    import mido
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    events: List[Tuple[float, int]] = []
    t = 0.0
    for msg in mid:
        t += msg.time
        if t >= start + duration:
            break
        if msg.type == "note_on" and msg.velocity > 0 and t >= start:
            events.append((t - start, msg.note))
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

    exact = adjusted = merged = 0
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
        if partition[tone][beat]:
            merged += 1
        partition[tone][beat] = True
        used.add(snapped)

    return {
        "partition": partition,
        "offset": offset,
        "exact": exact,
        "adjusted": adjusted,
        "merged": merged,
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


# Label text: raised letters curved around the spindle, inside the recess,
# in the ring between the centre hole (r 3.22) and the drive holes (r >= 20.25)
LABEL_R = 16.3          # baseline-centre radius of the text arc
LABEL_MAX_H = 4.6       # letter height (radial)
LABEL_MAX_ARC = 300.0   # degrees of arc the title may span
H_TEXT = 0.6
_FONT = dict(family="DejaVu Sans", weight="bold")


def _flip(H):
    """Transform mapping a top-side feature onto the underside (side B)."""
    m = trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0])
    m[2, 3] += H
    return m


def _text_path(title: str):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    return TextPath((0, 0), title, size=10, prop=FontProperties(**_FONT))


def _text_scale(title: str) -> float:
    """Scale factor mapping font units -> mm so letters fit height and arc."""
    ext = _text_path(title).get_extents()
    max_len = math.radians(LABEL_MAX_ARC) * LABEL_R
    return min(LABEL_MAX_H / max(ext.height, 1e-6), max_len / max(ext.width, 1e-6))


def _text_shape(title: str):
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
    s = _text_scale(title)
    shape = affinity.scale(shape, s, s, origin=(0, 0))
    return affinity.translate(shape, -(minx + maxx) / 2 * s, -(miny + maxy) / 2 * s)


def _bend(shape):
    """Wrap a flat shape around the label arc: x -> angle, y -> radius."""
    import shapely

    def warp(coords):
        x, y = coords[:, 0], coords[:, 1]
        theta = math.pi / 2 - x / LABEL_R
        r = LABEL_R + y
        return np.column_stack([r * np.cos(theta), r * np.sin(theta)])

    dense = shapely.segmentize(shape, 0.25)
    return shapely.transform(dense, warp)


def _text_meshes(title: str, H: float) -> List:
    title = (title or "").strip()
    if not title:
        return []
    shape = _text_shape(title)
    if shape is None:
        return []
    shape = _bend(shape)
    geoms = list(shape.geoms) if hasattr(shape, "geoms") else [shape]
    meshes = []
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


def label_glyphs(title: str) -> List[Tuple[str, float, float]]:
    """Per-character (char, angle_deg, size_mm) placements for OpenSCAD."""
    title = (title or "").strip()
    if not title:
        return []
    s = _text_scale(title)
    full = _text_path(title).get_extents()
    centre = (full.x0 + full.x1) / 2
    out = []
    prev_x1 = 0.0
    for i, ch in enumerate(title):
        if ch.isspace():
            continue
        ext = _text_path(title[: i + 1]).get_extents()
        x_mid = (prev_x1 + ext.x1) / 2 if i else (ext.x0 + ext.x1) / 2
        prev_x1 = ext.x1
        angle = 90 - math.degrees((x_mid - centre) * s / LABEL_R)
        out.append((ch, round(angle, 2), round(float(10 * s), 3)))
    return out


def _groove_cutters(H: float) -> List:
    gz = H - H_GROOVE / 2 + 0.2
    return [_annulus(inner, inner + 2, H_GROOVE + 0.4, gz) for inner in GROOVE_INNERS]


def _pin_meshes(partition: List[List[bool]], H: float) -> List:
    pins = get_pins(to_physical(partition))
    out = []
    pz = H - (H_GROOVE + OVERLAP) / 2
    for p in pins:
        box = trimesh.creation.box(extents=[p["outer"] - p["inner"], 1.0,
                                            H_GROOVE + OVERLAP])
        box.apply_translation([p["inner"] + (p["outer"] - p["inner"]) / 2, 0, pz])
        box.apply_transform(trimesh.transformations.rotation_matrix(
            p["angle"], [0, 0, 1]))
        out.append(box)
    return out


def build_mesh(partition: List[List[bool]], thickness: float = 3.0,
               title: str = "", partition_b: List[List[bool]] = None,
               title_b: str = ""):
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
    adds = _pin_meshes(partition, H)
    pin_count = len(adds)
    adds.extend(_text_meshes(title, H))
    if two_sided:
        side_b = _pin_meshes(partition_b, H)
        pin_count += len(side_b)
        side_b.extend(_text_meshes(title_b, H))
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
    """Music-box tune-tracker text format: 16 tone rows of + / - then title."""
    beats = len(partition[0])
    lines = []
    for tone in range(TONES_COUNT):
        lines.append("".join("+" if partition[tone][b] else "-" for b in range(beats)))
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
hText = 0.6;

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
        onSide(onSecondSide) rotate(a=angle-90) translate(v=[0, labelR, hStock-hInset-overlap]) {{
                linear_extrude(height=hText+overlap) {{
                        text(ch, size=size, halign="center", valign="center", font="DejaVu Sans:style=Bold");
                }}
        }}
}}

module pin(inner, outer, angle, onSecondSide) {{
        onSide(onSecondSide) rotate(a=angle) {{
                translate(v=[inner, -0.5, hStock-hGroove-overlap]) {{
                        cube(size=[outer-inner, 1, hGroove+overlap], center=false);
                }}
        }}
}}

createDisc();
'''


def _scad_pins(partition, side_flag):
    lines = []
    for p in get_pins(to_physical(partition)):
        deg = math.degrees(p["angle"])
        lines.append(f"\t\tpin({round(p['inner'], 3)},{round(p['outer'], 3)},"
                     f"{round(deg, 3)},{side_flag});")
    return lines


def _scad_str(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def to_scad(partition: List[List[bool]], thickness: float, title: str,
            partition_b: List[List[bool]] = None, title_b: str = "",
            label_a: str = None, label_b: str = None) -> str:
    label_a = title if label_a is None else label_a
    label_b = title_b if label_b is None else label_b
    lines = _scad_pins(partition, "false")
    if partition_b is not None:
        lines.append("\t\t// Side B")
        lines.extend(_scad_pins(partition_b, "true"))
    labels = [f'\t\tglyph("{_scad_str(ch)}",{ang},{size},false);'
              for ch, ang, size in label_glyphs(label_a)]
    if partition_b is not None:
        labels += [f'\t\tglyph("{_scad_str(ch)}",{ang},{size},true);'
                   for ch, ang, size in label_glyphs(label_b)]
    from datetime import datetime
    return _SCAD_TEMPLATE.format(
        DATE_TIME=datetime.now().strftime("%d %b %Y %H:%M"),
        THICKNESS=thickness,
        TWO_SIDED="true" if partition_b is not None else "false",
        TITLE_A=_scad_str(title),
        TITLE_B=_scad_str(title_b) if partition_b is not None else "",
        LABELS="\n".join(labels),
        NOTES="\n".join(lines),
    )


def analyze(midi_bytes: bytes, duration: float = 25.0, start: float = 0.0,
            auto_transpose: bool = True, manual_offset: int = 0) -> Dict:
    """MIDI window -> editable 16 x 86 partition plus mapping stats."""
    events = parse_midi_events(midi_bytes, duration, start)
    rec = events_to_record(events, duration, auto_transpose, manual_offset)
    rec["notes_used"] = [{"midi": m, "name": note_name(m)} for m in rec["notes_used"]]
    rec["duration"] = duration
    rec["start"] = start
    rec["beats"] = MAX_BEAT
    return rec


def press(partition: List[List[bool]], title: str, thickness: float = 3.0,
          partition_b: List[List[bool]] = None, title_b: str = "",
          engrave: bool = True) -> Dict:
    """Partition(s) -> STL / SCAD / FPR files."""
    label_a = title if engrave else ""
    label_b = title_b if engrave else ""
    mesh, pin_count = build_mesh(partition, thickness, label_a, partition_b, label_b)
    stl_bytes = mesh.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode()
    used = sorted({NOTES[t] for part in (partition, partition_b or [])
                   for t, row in enumerate(part) if any(row)})
    return {
        "stl": bytes(stl_bytes),
        "fpr": to_fpr(partition, title),
        "fpr_b": to_fpr(partition_b, title_b) if partition_b is not None else None,
        "scad": to_scad(partition, thickness, title, partition_b, title_b, label_a, label_b),
        "stats": {
            "pin_count": pin_count,
            "thickness": thickness,
            "beats": MAX_BEAT,
            "triangles": int(len(mesh.faces)),
            "notes_used": [{"midi": m, "name": note_name(m)} for m in used],
            "two_sided": partition_b is not None,
        },
    }


def generate_stl(midi_bytes: bytes, duration: float = 25.0,
                 thickness: float = 3.0, auto_transpose: bool = True,
                 manual_offset: int = 0, title: str = "Record") -> Dict:
    rec = analyze(midi_bytes, duration, 0.0, auto_transpose, manual_offset)
    out = press(rec["partition"], title, thickness)
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
