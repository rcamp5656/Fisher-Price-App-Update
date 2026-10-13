import mido
import sys
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# The valid 22-note range for the Fisher-Price player (G3 to E5)
VALID_NOTE_MIN = 55
VALID_NOTE_MAX = 76

def transpose_note_to_valid_range(note: int) -> int:
    """
    Transposes a MIDI note number into the valid Fisher-Price range by octaves.
    If the note is already valid, it is returned unchanged.
    """
    if VALID_NOTE_MIN <= note <= VALID_NOTE_MAX:
        return note

    transposed_note = note
    # If the note is too low, shift it up by octaves (12 semitones)
    if transposed_note < VALID_NOTE_MIN:
        while transposed_note < VALID_NOTE_MIN:
            transposed_note += 12
        return transposed_note
    
    # If the note is too high, shift it down by octaves
    else: # note > VALID_NOTE_MAX
        while transposed_note > VALID_NOTE_MAX:
            transposed_note -= 12
        return transposed_note

def process_midi_file(input_path: str, output_path: str):
    """
    Reads a MIDI file, transposes all notes into the valid range, and saves the result.
    """
    notes_transposed = 0
    try:
        mid = mido.MidiFile(input_path)
        new_mid = mido.MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)

        for track in mid.tracks:
            new_track = mido.MidiTrack()
            for msg in track:
                if msg.type in ('note_on', 'note_off'):
                    original_note = msg.note
                    transposed_note = transpose_note_to_valid_range(original_note)
                    
                    if original_note != transposed_note:
                        notes_transposed += 1

                    # Create a new message with the (potentially) transposed note
                    new_track.append(msg.copy(note=transposed_note))
                else:
                    # Copy all other messages (meta, control change, etc.) as is
                    new_track.append(msg.copy())
            new_mid.tracks.append(new_track)
        
        new_mid.save(output_path)
        logging.info(f"Transposed {notes_transposed} notes. Saved file to {output_path}")

    except Exception as e:
        logging.error(f"Error processing MIDI file '{input_path}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transpose MIDI notes to a valid range for the Fisher-Price player.")
    parser.add_argument('--input', required=True, help='Path to the input MIDI file.')
    parser.add_argument('--output', required=True, help='Path to save the processed output MIDI file.')
    args = parser.parse_args()

    process_midi_file(args.input, args.output)