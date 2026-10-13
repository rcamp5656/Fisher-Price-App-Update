# Fisher-Price Record Maker — PRD

## Original Problem Statement
Update the GitHub app (rcamp5656/Fisher-Price-App-Update) so it works. Primary
function: convert a MIDI file into a 3D-printable STL for the vintage 1977
Fisher-Price Music Box Record Player. User later specified: sample the first
**25 seconds**, provide a **3D browser preview**, and also output the **.fpr**
(tracker) and **.scad** (OpenSCAD) files alongside the **.stl**.

## Architecture
- **Frontend**: React 19 + Tailwind + react-three-fiber/drei (3D STL preview).
- **Backend**: FastAPI. Pure-Python MIDI→geometry engine (`fisher_price.py`)
  using `mido` (MIDI parse), `trimesh` + `manifold3d` (watertight mesh / STL).
- **DB**: MongoDB (`conversions` collection). STL stored base64; FPR/SCAD as text.
- Geometry ported faithfully from the user's own "Fisher-Price-Music-Box-Record-Creator"
  repo (Fred's record creator template): Ø121mm disc, 11 grooves / 22 tracks,
  16 playable tines, 86 beats per revolution, 4 drive holes + centre spindle.

## User Persona
Maker / vintage-toy enthusiast who wants to 3D-print custom song discs that play
on an original Fisher-Price music box record player.

## Core Requirements (static)
- Upload MIDI, sample first N seconds (default 25) → one disc revolution.
- Map/transpose notes onto the 16 physical tines; snap off-scale notes to nearest.
- Generate printable STL + OpenSCAD (.scad) + tracker (.fpr).
- Interactive 3D preview; download all three formats.

## Implemented (2026-06 / built 2026-10-13)
- MIDI parsing with first-`duration`-seconds truncation.
- Auto-transposition (maximize on-pitch hits) + manual semitone offset.
- Faithful disc mesh (grooves, drive holes, label inset, note pins/bumps).
- STL/SCAD/FPR exporters + download endpoints.
- Chunky retro-maker UI: upload, settings (auto-transpose, 25s window, thickness),
  3D viewer, spec sheet, playable-tines panel, recent-pressings history.
- Full E2E tested (backend 100%, frontend 100%).

## Backlog / Remaining
- P2: Store STL in GridFS/filesystem instead of base64 (16MB doc limit for very long songs).
- P2: Upload size limit / rate guard on /api/convert.
- P2: Migrate deprecated FastAPI `on_event` to lifespan.
- P2: Optional disc title engraving in the label area.
- P2: Two-sided discs (verso) support (template already supports it).
