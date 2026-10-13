# Fisher-Price Record Maker — PRD

## Original Problem Statement
Update the GitHub app (rcamp5656/Fisher-Price-App-Update) so it works. Primary
function: convert a MIDI file into a 3D-printable STL for the vintage 1977
Fisher-Price Music Box Record Player. User later specified: sample the first
**25 seconds**, provide a **3D browser preview**, and also output the **.fpr**
(tracker) and **.scad** (OpenSCAD) files alongside the **.stl**.

## Architecture
- **Frontend**: React 19 + Tailwind + react-three-fiber/drei (3D STL preview),
  Web Audio API music-box synth (no external API).
- **Backend**: FastAPI. Pure-Python MIDI→geometry engine (`fisher_price.py`)
  using `mido` (MIDI parse), `trimesh` + `manifold3d` (watertight mesh / STL),
  `matplotlib` TextPath + `shapely` (curved label lettering).
- **DB**: MongoDB (`conversions` collection). STL stored base64; FPR/SCAD as text;
  editable partitions (16×86) stored with each record.
- Geometry ported faithfully from the user's own "Fisher-Price-Music-Box-Record-Creator"
  repo (Fred's record creator template): Ø121mm disc, 11 grooves / 22 tracks,
  **22 tines = 16 distinct pitches** (C6–A6 doubled on twin tines), 86 beats per
  revolution, 4 drive holes + centre spindle.

## Physics note (answer to "how many seconds?")
The toy's spring motor fixes play time: one revolution ≈ 25 s freshly wound
(slows to ~35–40 s). The capture window only decides how much MIDI is squeezed
into the 86 beats: 32 s window ⇒ tune plays at 128 % tempo. "Match toy" button
sets window = revolution time so the tune plays at original tempo.

## User Persona
Maker / vintage-toy enthusiast who wants to 3D-print custom song discs that play
on an original Fisher-Price music box record player.

## Core Requirements (static)
- Upload MIDI, sample first N seconds (default 25) → one disc revolution.
- Map/transpose notes onto the 16 pitches; snap off-scale notes to nearest.
- Generate printable STL + OpenSCAD (.scad) + tracker (.fpr).
- Interactive 3D preview; download all three formats.

## Implemented
### 2026-10-13 (session 1)
- MIDI parsing with first-`duration`-seconds truncation; auto-transposition + manual offset.
- Faithful disc mesh (grooves, drive holes, label inset, note pins/bumps).
- STL/SCAD/FPR exporters + download endpoints; retro-maker UI; 3D viewer; history.

### 2026-10-13 (session 2 — this fork)
- **Flow redesign**: upload → `POST /api/analyze` → Note Editor → `POST /api/press` → 3D + downloads.
- **Capture window** up to 45 s, live "% tempo" readout, merged-note count/warning, "match toy" button.
- **Curved disc labels**: title raised 0.6 mm inside the label recess, bent around
  the spindle (r 14–18.5 mm, clears drive holes). Side B title on underside.
  SCAD gets per-letter `glyph()` placement. Engrave toggle.
- **Two-sided discs**: Side B from a 2nd MIDI file or by continuing the same song
  (window 2). Bottom grooves + mirrored pins via flip transform. `.fpr?side=b`.
- **Note editor**: 16×86 grid, click add/remove, drag to nudge, reset, twin-tine (×2)
  markers, side A/B tabs, stale-settings badge.
- **Song preview**: Web Audio music-box pluck synth at real toy speed (25–40 s/rev slider), playhead.
- UI labels corrected: "22 tines (16 pitches)".
- Full E2E tested: backend 13/13, frontend all flows (iteration_2.json).

### 2026-10-13 (session 2, batch 2)
- **Comb research** (Fred Murphy Instructable comments, twagoo's tuner readings): 22 tines =
  16 unique pitches, twins on tines 8+9, 10+11, 12+13, 14+15, 16+17, 18+19. Real sounding
  pitch is a major third below Fred's notation (A♭ major) → preview synth uses `REAL_PITCH_OFFSET=-4`.
  Fred: double-sided discs must be 5 mm → two-sided toggle auto-sets 5 mm, backend clamps ≥4.5.
  Some players turn at ~50 s/rev → toy-speed slider 20–60 s.
- **Repeat warning**: single-tine notes on back-to-back beats highlighted amber + "Repeats" stat + banner.
- **Loop playback** + sequential A→B playback (0.8 s flip gap), side tab auto-follows playhead.
- **22 TINES view**: read-only track view showing pins on all 22 physical tracks (11 grooves × 2 walls).
- **Print Guide** collapsible card (layer height, orientation, material, slicer, finishing); auto-opens after press.
- **Share links**: `COPY SHARE LINK` → `/r/:id` page (3D view, downloads, print guide, "Remix" → `/?open=id`).
- Tested: iteration_3.json (backend 15/15, all frontend flows; PrintGuide auto-open fix verified).

## Backlog / Remaining
- P1: User validation of physical prints (pin height/width on the real toy).
- P1: User to verify twin tines 8/9 sound the same pitch on their player (confirms comb mapping).
- P2: Store STL in GridFS/filesystem instead of base64 (16MB doc limit).
- P2: Editable 22-tine view (hand-assign which twin tine takes a note).
- P2: Migrate deprecated FastAPI `on_event` to lifespan.
