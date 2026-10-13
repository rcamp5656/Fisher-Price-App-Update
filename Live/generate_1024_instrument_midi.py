
from music21 import converter, stream, instrument, note, chord, tempo
from pathlib import Path

def generate_1024_instrument_midi(input_midi_path, output_midi_path, logger=None):
    if logger: logger.info(f"Parsing MIDI: {input_midi_path}")
    original = converter.parse(input_midi_path)
    enhanced = stream.Score()

    for i, part in enumerate(original.parts[:16]):
        new_part = stream.Part()
        new_part.id = f"track{i}"
        instrument_offset = i * 8

        if logger: logger.info(f"Processing track {i}, instrument offset {instrument_offset}")

        instr_index = 0
        for idx, elem in enumerate(part.recurse().notesAndRests):
            if idx % 50 == 0 and logger:
                logger.info(f"  Track {i} note {idx}")

            program = (instrument_offset + instr_index) % 128
            instr_obj = instrument.fromMidiProgram(program)
            new_part.append(instr_obj)

            if isinstance(elem, note.Note):
                new_note = note.Note(elem.pitch, quarterLength=elem.quarterLength)
                new_note.volume.velocity = elem.volume.velocity if elem.volume else 64
                new_part.append(new_note)
            elif isinstance(elem, chord.Chord):
                new_chord = chord.Chord(elem.pitches, quarterLength=elem.quarterLength)
                new_chord.volume.velocity = elem.volume.velocity if elem.volume else 64
                new_part.append(new_chord)
            elif isinstance(elem, note.Rest):
                new_rest = note.Rest(quarterLength=elem.quarterLength)
                new_part.append(new_rest)

            instr_index += 1

        enhanced.append(new_part)

    tempos = original.flat.getElementsByClass(tempo.MetronomeMark)
    if tempos:
        enhanced.insert(0, tempos[0])

    mid_path = Path(output_midi_path)
    mid_path.parent.mkdir(parents=True, exist_ok=True)
    enhanced.write('midi', fp=str(mid_path))

    if logger: logger.info(f"MIDI written successfully: {mid_path}")
    return str(mid_path)
