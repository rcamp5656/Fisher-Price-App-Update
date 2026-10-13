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

### 2026-10-13 (session 2, batch 3 — factory label match)
- User supplied photos of an original two-sided record (Humpty Dumpty / Jack and Jill).
  Label now mirrors it: title arc centred on the LEFT (9 o'clock) reading clockwise with
  letter tops outward; raised side numeral ("1"/"2") left of the spindle at r 8.5 mm; raised
  dash mark right of the spindle; all inside the recess. SCAD has `mark()`/`dash()` modules.
- 3D preview recoloured to Fisher-Price lavender (#B9A9E3). Backend 23/23 tests pass.

### 2026-10-13 (session 2, batch 4 — pins & numbering)
- **Note pins** are now semicircular bumps (R_PIN 0.7 mm half-cylinders centred on the groove
  wall, full groove depth) instead of 1 mm blocks — opposite-wall bumps never bridge the groove,
  matching the user's photos of the originals. SCAD `pin(wall, angle, side)` uses a cylinder.
- **Record numbering**: label numeral = record number. Starts at **#6** (factory set is 1–5),
  increments per new pressing; re-pressing the same title (case-insensitive) reuses its number.
  Stored as `record_no`; shown in spec sheet, history and share page. Both sides carry the number.

### 2026-10-13 (session 2, batch 5 — one-note-at-a-time + 5 features)
- **Stagger fix**: the player plucks one tine per beat; `events_to_record` moves simultaneous
  notes to the nearest free beat (`staggered` stat); editor flags leftover same-beat notes as
  "Chords" (amber) with a warning. Pins halved to Ø0.7 mm (R_PIN 0.35).
- **Record number override** (`record_no` in /press; `GET /api/next-record-no?title=` for the auto preview).
- **Twin tine control**: 22 TINES view pins on twin tracks are clickable → `overrides` {"tone-beat": slot}
  sent to /press and stored; `to_physical(partition, comb, overrides)` on both ends.
- **Comb re-map**: `Comb` class (22 tracks → unique pitch rows); `GET/PUT/DELETE /api/comb` stored in
  `settings` collection; frontend live-binding `applyComb()`; CombEditor with 22 note-name inputs.
- **Factory library**: 10 nursery rhymes transcribed as NOTE[:beats] strings (`fp.LIBRARY`),
  `GET /api/library` → ready-to-edit analyses; LibraryPicker in the Load card.
- **Song overview**: `POST /api/scan` (all note-ons + length); SongOverview strip with draggable
  capture window → `start` for /analyze (per side).
- User confirmed by magnifier: 12 walls, inner/outer walls one-sided, 10 ridges two-sided = 22 tines.
- Tested: iteration_4.json (backend 37/37 after fixing blank-title 500 on next-record-no; all UI flows pass).

### 2026-10-13 (session 2, batch 6)
- **Window fine-tune**: ◀ ▶ 0.5 s nudges + start-time box on the song overview (clamped to total − window).
- **Record Shelf**: tiles for every number (1–5 factory lavender, pressed red, dashed gaps); gap click
  pre-fills the record-number override; pressed click opens the record.
- **Library preview**: play/stop control per factory tune before loading it.
- **Print Pack**: `GET /api/conversions/{id}/pack` zip → STL, SCAD, FPR (A + B), 100×60 mm label-card SVG, README.
- Tested: iteration_5.json (backend 40/40, all UI flows pass).

### 2026-10-13 (session 3 — this fork)
- **Stagger rule (user ruling)**: one note at a time on the whole disc — no two pins share a beat
  anywhere; pins of one pitch ≥2 mm apart along the track and single tines get a rest beat
  (disc wraps). Chords are *rolled* like the factory records (top note keeps the beat, lower
  notes slide, preferring earlier); repeats slide later. Notes slide as far as needed to the
  nearest free beat — **nothing is dropped** unless the disc is full. `make_playable` returns
  (slid, dropped); `staggered` = rolled + slid; `toy_fixes` counts all fixes. Mirrored in
  `fp.js` (canPlace/slide/staggerPartition/thinRepeats). iter8 test updated (dropped==0).
- **Editor layout**: all 86 beats shown by default (fit toggle kept, default off); measured
  cell sizing (ResizeObserver, no horizontal scroll), ruler with beat numbers + song seconds
  every 10 beats, bar lines every 5/10, caption "window X → Y s of song". Page widened to
  1800 px (workspace 9/12, sidebar 3/12).
- **Mesh pre-flight (`heal_mesh`)**: before STL export: merge vertices, drop duplicate +
  degenerate triangles, fix mismatched windings, fill holes, verify watertight/winding/open
  edges, volume, bodies. Report stored as `mesh_check` on the record; SpecSheet shows
  "MESH CHECK — PRINT READY / NEEDS ATTENTION" with the repairs performed. Halves checked too
  (`halves_ok`). Added scipy + networkx (trimesh graph engines).
- Tested: iteration_10.json (backend 67/67, all UI flows pass).

### 2026-10-13 (session 3, part 2)
- **Jump to playhead**: clicking a beat on the editor ruler (`ruler-beat-{b}`) plays the preview
  from that beat; red cue marker; `useMusicBox.play({side, beat})`.
- **Chord roll direction**: Settings `roll-before`/`roll-after` (default before). `_slide` leans
  the preferred way for LEAN_BEATS=4 before trying the other side. `roll` accepted by
  /api/analyze (form) and /api/press (json), stored on the record. Mirrored in `fp.js`.
- **mesh-check.txt** in the Print Pack ZIP (`_mesh_report`), README updated.
- **MIDI vs DISC compare panel** (`compare-toggle`): side-by-side mini grids with moved/placed
  highlights, HEAR MIDI (real MIDI slice at true timing, toy key) vs HEAR DISC (toy speed),
  match score; editor shows dashed ghost cells where the MIDI had a note before it moved.
- **Auto-Fit** (user: automatic on load/window move, tempo ±35 %, start nudge ±0.5 s):
  `fisher_price.auto_fit` + `compare_fit` + `POST /api/autofit` — up to 12,000 candidate
  mappings (seconds-per-rev × start phase; numpy quick score, then full stagger+compare on the
  best ~300, then fine pass), ~0.5–0.8 s. Score = 50 % notes matched + 30 % timing +
  20 % pitch exact − TEMPO_PENALTY·|tempo−1|. Analysis now returns `events` and `fit`.
  Frontend: `autofit-toggle` (default ON) applies fitted duration + nudged start without
  marking stale; dragging the duration slider / match-toy turns auto-fit off.
- Tested: iteration_11.json (backend 76/76 after max_tries fix, frontend 100 %).

### 2026-10-13 (session 3, part 3 — multi-track MIDI, album, review audio, chords)
- **Track picker** (`TrackPicker.js`, `scan_tracks`): /api/scan returns per-track summaries
  (name, GM instrument, notes, range, strip, melody_score), suggested melody track, song title.
  Drums (ch 10) never used; bass lines demoted (name/program/mean<55 → ×0.4), name hints
  (melody/lead/vocal…) +20. Auto-picks the single best melody track; buttons "melody only" /
  "mono mix" (all tracks + skyline); `skyline` option; `melody_fill` option (default on) borrows
  the skyline of other non-bass instruments where the melody rests > 1.5 s.
- **Swap-file bug fixed**: uploading a new MIDI drops the old analysis, disables LOAD NOTES until
  the scan finishes, resets tracks/start, discards obsolete analysis responses; Disc title auto-
  fills from the MIDI first-track name or prettified file name.
- **Album** (`POST /api/album`, background task, `GET /api/album/{id}`, `/zip`): whole song →
  consecutive 86-beat sides, one key + one tempo (auto-fit), pressed as numbered records
  (two-sided pairs or single), ZIP with STLs/halves/scad/fpr/mesh-check/README. `AlbumPanel.js`.
- **Review audio** (`POST /api/render`, `SongReview.js`): whole song as the toy plays it →
  8 kHz 16-bit MONO WAV (pluck synth, partials < Nyquist), headers X-Sides/X-Notes/…
- **Pins**: 1.6 mm-base triangle ramps buried 0.5 mm into the wall (PIN_BASE/PIN_SINK, SCAD too).
  Viewer zooms to 12 units. Two-sided downloads now lead with HALF A / HALF B (full disc = link,
  needs supports).
- **Auto-fit** also tries the runner-up transpositions ("tines up or down"); budget respected.
- **Stagger instead of merge**: a second same-pitch note on a used beat moves to the nearest free
  beat (±8); only a full disc counts as "No room" (stat-lost). Capacity: 86 notes/side mono.
- **Voices / simple chords**: `voices` 1 (factory, rolled) · 2 · 3 (keep top, bottom, middle;
  extras roll within ±4 or drop) · 16 (full chords); on analyze/autofit/render/album/press and
  stored on records. Editor flags beats exceeding `voices`.
- Tested: iteration_12 … iteration_18.json (backend 129/129, all UI flows pass).

### 2026-10-13 (session 3, part 4)
- **Chord test disc** (`POST /api/testdisc`, button `test-disc-button`): one phrase as single notes
  (beats 2-12), two-note chords (30-40), triads (58-68) → "CHORD TEST 1-2-3", voices=3.
- **Album shelf**: RecordShelf groups album discs (blue, i/n tags), play-order chips, NEXT ▶ marker
  for the disc after the open one, PLAYING on the open one.
- **Melody confidence**: TrackPicker "rank by ear" top-3 chips (tap = audition, tap again = use)
  and a "why:" line (mono / notes-per-sec / range / span / score) on the top-3 rows.
- **Review timeline**: SongReview shows "side k of N · beat b" while the WAV plays; "OPEN THIS SPOT
  IN THE EDITOR" sets auto-fit off, duration, window start and cues the beat in the editor.
- **Splash + credits + source ZIP** (owner: Russ Campbell): `Splash.js` (2.5 s, click to skip) —
  "Fisher-Price Record Maker · Dedicated To My Fiancée Barbara · Russ Campbell · Copyright 2026
  Russ Campbell. All rights reserved."; footer credits; `GET /api/source.zip` = full project
  (backend, frontend src + production build, standalone/splash.html HTML5/CSS3/JS, tests, README,
  LICENSE; no .env/node_modules/.git). Credits also head every SCAD file and mesh-check.txt.
- Tested: iteration_19.json, iteration_20.json (backend 137/137, UI green).

### 2026-10-13 (session 4)
- **No-sound fix**: one shared AudioContext for the whole app (`audioEngine()` in useMusicBox.js; every player
  gets a `Channel` gain node — `newCtx()` keeps its old call shape). Chrome/Edge on Windows went silent when
  contexts were opened/closed per play. Unlocked on first pointer/key; `SoundCheck` (TEST chime, state
  "SOUND ON/BLOCKED/MUTED", volume slider stored in localStorage) in the Load card + editor transport.
- **Barbara label art**: dedication "Dedicated To My Fiancée Barbara" as a raised curved arc (r 12, 2.4 mm,
  centred 3 o'clock, clear of numeral/title) on every disc side (mesh + SCAD `mark(..., dedR, ...)`), curved
  `<textPath>` + footer line on the sleeve-card SVG. `GET /api/conversions/{id}/label.svg` + SLEEVE CARD button.
- **Test-disc notes**: `GET/PUT /api/defaults` {voices, note, tested_at}; `TestDiscNotes` card under the test
  disc button (ONE/TWO/THREE + note → default "notes at once", applied on load).
- **Album sleeve sheet**: `GET /api/album/{id}/sleeves` (HTML, A4 pages of 8 numbered 100×60 cards with i/n
  badge, play order) + `sleeves/` folder in the album ZIP; PRINT SLEEVE SHEET button in AlbumPanel.
- **Offline build**: `/app/launchers/` → ZIP root gets start-windows.bat, start-mac.command, start-linux.sh
  (0755), BUILD-GUIDE.txt; `backend/requirements-local.txt` (public PyPI only). README updated.
- **Label preview**: RecordViewer FULL DISC / READ LABEL toggle (straight-down close-up, grazing light,
  hint box); viewer is now sticky + viewport-height instead of stretching to the sidebar height.
- **Sleeve colour bands**: album cards get a coloured spine (10-colour palette by disc index), DISC n text,
  a dot row with the current disc highlighted, matching badge colour; long titles squeezed via textLength,
  RECORD / #no split into two lines, header shrunk so nothing runs under the disc art.
- Defaults load no longer flags "settings changed" on an opened record.
- **Dedication dial + side-B toggle**: `ded_height` (2.0–3.5 mm, default 2.4) and `ded_b` on press/album/testdisc,
  stored on records, SCAD honours both; Settings slider "Dedication letters" with nozzle hints, toggle shown for
  two-sided discs. **Shelf colours**: RecordShelf album tiles/chips/tags use the sleeve-card palette (`ALBUM_COLOURS`).
- **Offline without MongoDB**: `backend/filedb.py` (folder-backed Motor stand-in: one JSON per doc in
  `data/records/<collection>/`), selected when `FP_STORAGE=files` or MONGO_URL is unset; start scripts write
  that .env when mongod is absent. Verified against press/list/get/stl/defaults/numbering/testdisc.
- **Dedication font**: `ded_font` bold|rounded|script (DejaVu Sans Bold / Comfortaa / Pacifico, TTFs in
  backend/fonts, thin fonts emboldened 0.12/0.08 mm); Settings picker; SCAD `mark(..., font)` + `dedFont`.
- **Shelf album filter**: tap an album name → spotlight its discs (others dim 20 %), tap again to clear.
- **Backup all records**: `POST /api/backup` starts a background job (one record at a time, zip work in a
  thread, compresslevel 1, spooled to a temp file), `GET /api/backup` progress, `GET /api/backup.zip` download.
  Per record: STL(s), SCAD, FPR, sleeve label, JSON meta; albums/*.json; settings.json; README index.
  `BackupButton` on the Record Shelf (PACKING n/N → DOWNLOAD BACKUP). Preview DB has ~1500 records → slow here.
- **Font preview**: `GET /api/label-preview.svg?font=&height=&title=&record_no=` flat label drawing; the three
  font buttons in Settings show it live. **Shelf search**: title or #number box, hits lit, others dim, first
  hit scrolls into view, Enter opens it, Esc clears.
- User print feedback: first disc "looks pretty good", needs clean-up before playback; sizing feedback pending.
- Direct ZIP link given to user: {API}/api/source.zip.
- Verified: curl on all new endpoints, pytest (analyze/press/api/pack green), browser smoke (shared ctx, save default).

## Backlog / Remaining
- P1: User validation of physical prints (pin height/width on the real toy).
- P1: User to verify twin tines 8/9 sound the same pitch on their player (confirms comb mapping).
- P2: Store STL in GridFS/filesystem instead of base64 (16MB doc limit).
- P2: Editable 22-tine view (hand-assign which twin tine takes a note).
- P2: Migrate deprecated FastAPI `on_event` to lifespan.
