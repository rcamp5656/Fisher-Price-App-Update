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
import re
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
R_PIN = 0.35          # radius of the semicircular note bumps on the groove walls

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


def midi_length(midi_bytes: bytes) -> float:
    import mido
    return mido.MidiFile(file=io.BytesIO(midi_bytes)).length


def choose_transposition(notes: List[int], comb: Comb = DEFAULT_COMB) -> int:
    """Find the semitone offset that lands the most notes exactly on the
    playable pitch set (tie-break: smallest total snap distance)."""
    allowed = set(comb.notes)
    lo, hi = min(comb.notes), max(comb.notes)
    best_offset, best_score = 0, None
    for offset in range(-48, 49):
        exact = 0
        dist = 0
        for n in notes:
            m = n + offset
            if m in allowed:
                exact += 1
            dist += min(abs(m - a) for a in comb.notes)
        avg = (sum(notes) / len(notes)) + offset
        if not (lo - 6 <= avg <= hi + 6):
            continue
        score = (exact, -dist)
        if best_score is None or score > best_score:
            best_score = score
            best_offset = offset
    return best_offset


def snap_note(midi: int, comb: Comb = DEFAULT_COMB) -> int:
    return min(comb.notes, key=lambda a: abs(a - midi))


def events_to_record(events: List[Tuple[float, int]], duration: float,
                     auto_transpose: bool = True,
                     manual_offset: int = 0,
                     comb: Comb = DEFAULT_COMB,
                     stagger: bool = True) -> Dict:
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
        if stagger and col_used[beat] and not partition[tone][beat]:
            for d in (1, -1, 2, -2, 3, -3):
                nb = beat + d
                if 0 <= nb < MAX_BEAT and not col_used[nb]:
                    beat = nb
                    staggered += 1
                    break
        if partition[tone][beat]:
            merged += 1
        partition[tone][beat] = True
        col_used[beat] = True
        used.add(snapped)

    return {
        "partition": partition,
        "offset": offset,
        "exact": exact,
        "adjusted": adjusted,
        "merged": merged,
        "staggered": staggered,
        "notes_used": sorted(used),
        "note_count": len(events),
    }


# ---------------------------------------------------------------------------
# 16 tones -> 22 physical tracks (doubled tracks let fast repeats reset)
# ---------------------------------------------------------------------------
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
        for beat in range(beats):
            if part22[track][beat]:
                angle = note_angle * beat - HEAD_OFFSET / radius
                pins.append({"wall": wall, "angle": angle})
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
    """Wrap a flat shape around the label arc: x -> angle, y -> radius.
    Centred on ARC_CENTRE (left side, like the factory records), reading
    clockwise with letter tops facing outward."""
    import shapely

    def warp(coords):
        x, y = coords[:, 0], coords[:, 1]
        theta = ARC_CENTRE - x / LABEL_R
        r = LABEL_R + y
        return np.column_stack([r * np.cos(theta), r * np.sin(theta)])

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


def _text_meshes(title: str, H: float, number: int = 0) -> List:
    title = (title or "").strip()
    shapes = []
    if title:
        shape = _text_shape(title)
        if shape is not None:
            shapes.append(_bend(shape))
    if number:
        shapes.extend(_side_marks(number))
    return _extrude_label(shapes, H)


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
        angle = math.degrees(ARC_CENTRE) - math.degrees((x_mid - centre) * s / LABEL_R)
        out.append((ch, round(angle, 2), round(float(10 * s), 3)))
    return out


def _groove_cutters(H: float) -> List:
    gz = H - H_GROOVE / 2 + 0.2
    return [_annulus(inner, inner + 2, H_GROOVE + 0.4, gz) for inner in GROOVE_INNERS]


def _pin_meshes(partition: List[List[bool]], H: float, comb: Comb = DEFAULT_COMB,
                overrides: Dict[str, int] = None) -> List:
    pins = get_pins(to_physical(partition, comb, overrides))
    out = []
    pz = H - (H_GROOVE + OVERLAP) / 2
    for p in pins:
        cyl = trimesh.creation.cylinder(radius=R_PIN, height=H_GROOVE + OVERLAP, sections=24)
        cyl.apply_translation([p["wall"], 0, pz])
        cyl.apply_transform(trimesh.transformations.rotation_matrix(p["angle"], [0, 0, 1]))
        out.append(cyl)
    return out


def build_mesh(partition: List[List[bool]], thickness: float = 3.0,
               title: str = "", partition_b: List[List[bool]] = None,
               title_b: str = "", marks: bool = True, record_no: int = 6,
               comb: Comb = DEFAULT_COMB, overrides: Dict = None, overrides_b: Dict = None):
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
    adds = _pin_meshes(partition, H, comb, overrides)
    pin_count = len(adds)
    adds.extend(_text_meshes(title, H, record_no if marks else 0))
    if two_sided:
        side_b = _pin_meshes(partition_b, H, comb, overrides_b)
        pin_count += len(side_b)
        side_b.extend(_text_meshes(title_b, H, record_no if marks else 0))
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
markR = 8.5;
hText = 0.6;
rPin = 0.35;

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

// Semicircular note bump centred on a groove wall (half sits in the wall, half plucks the tine)
module pin(wall, angle, onSecondSide) {{
        onSide(onSecondSide) rotate(a=angle) {{
                translate(v=[wall, 0, hStock-hGroove-overlap]) {{
                        cylinder(h=hGroove+overlap, r=rPin, $fn=24);
                }}
        }}
}}

createDisc();
'''


def _scad_pins(partition, side_flag, comb=DEFAULT_COMB, overrides=None):
    lines = []
    for p in get_pins(to_physical(partition, comb, overrides)):
        deg = math.degrees(p["angle"])
        lines.append(f"\t\tpin({round(p['wall'], 3)},{round(deg, 3)},{side_flag});")
    return lines


def _scad_str(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def to_scad(partition: List[List[bool]], thickness: float, title: str,
            partition_b: List[List[bool]] = None, title_b: str = "",
            label_a: str = None, label_b: str = None, marks: bool = True,
            record_no: int = 6, comb: Comb = DEFAULT_COMB,
            overrides: Dict = None, overrides_b: Dict = None) -> str:
    label_a = title if label_a is None else label_a
    label_b = title_b if label_b is None else label_b
    lines = _scad_pins(partition, "false", comb, overrides)
    if partition_b is not None:
        lines.append("\t\t// Side B")
        lines.extend(_scad_pins(partition_b, "true", comb, overrides_b))
    labels = [f'\t\tglyph("{_scad_str(ch)}",{ang},{size},false);'
              for ch, ang, size in label_glyphs(label_a)]
    if marks:
        labels += [f'\t\tmark("{record_no}",180,markR,3.2,false);', '\t\tdash(false);']
    if partition_b is not None:
        labels += [f'\t\tglyph("{_scad_str(ch)}",{ang},{size},true);'
                   for ch, ang, size in label_glyphs(label_b)]
        if marks:
            labels += [f'\t\tmark("{record_no}",180,markR,3.2,true);', '\t\tdash(true);']
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
            auto_transpose: bool = True, manual_offset: int = 0,
            comb: Comb = DEFAULT_COMB) -> Dict:
    """MIDI window -> editable pitch x 86 partition plus mapping stats."""
    events = parse_midi_events(midi_bytes, duration, start)
    return _finish_analysis(events_to_record(events, duration, auto_transpose, manual_offset, comb),
                            duration, start)


def _finish_analysis(rec: Dict, duration: float, start: float) -> Dict:
    rec["notes_used"] = [{"midi": m, "name": note_name(m)} for m in rec["notes_used"]]
    rec["duration"] = duration
    rec["start"] = start
    rec["beats"] = MAX_BEAT
    return rec


def press(partition: List[List[bool]], title: str, thickness: float = 3.0,
          partition_b: List[List[bool]] = None, title_b: str = "",
          engrave: bool = True, record_no: int = 6, comb: Comb = DEFAULT_COMB,
          overrides: Dict = None, overrides_b: Dict = None) -> Dict:
    """Partition(s) -> STL / SCAD / FPR files."""
    label_a = title if engrave else ""
    label_b = title_b if engrave else ""
    mesh, pin_count = build_mesh(partition, thickness, label_a, partition_b, label_b,
                                 marks=engrave, record_no=record_no, comb=comb,
                                 overrides=overrides, overrides_b=overrides_b)
    stl_bytes = mesh.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode()
    used = sorted({comb.notes[t] for part in (partition, partition_b or [])
                   for t, row in enumerate(part) if any(row)})
    return {
        "stl": bytes(stl_bytes),
        "fpr": to_fpr(partition, title),
        "fpr_b": to_fpr(partition_b, title_b) if partition_b is not None else None,
        "scad": to_scad(partition, thickness, title, partition_b, title_b, label_a, label_b,
                        marks=engrave, record_no=record_no, comb=comb,
                        overrides=overrides, overrides_b=overrides_b),
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
