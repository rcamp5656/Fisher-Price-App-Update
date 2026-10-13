# ui/diagnostic.py

import mido
import os
import sys

# The official 22-note Fisher-Price chromatic scale (G3 to E5)
FISHER_PRICE_NOTES = set(range(55, 77)) 

# A helper dictionary to convert MIDI note numbers to human-readable names
MIDI_NOTE_NAMES = {
    55: 'G3', 56: 'G#3', 57: 'A3', 58: 'A#3', 59: 'B3', 60: 'C4', 
    61: 'C#4', 62: 'D4', 63: 'D#4', 64: 'E4', 65: 'F4', 66: 'F#4', 
    67: 'G4', 68: 'G#4', 69: 'A4', 70: 'A#4', 71: 'B4', 72: 'C5', 
    73: 'C#5', 74: 'D5', 75: 'D#5', 76: 'E5'
}

def check_midi_notes(file_path):
    """
    Reads a MIDI file and checks if all notes are within the Fisher-Price range.

    Args:
        file_path (str): The full path to the MIDI file to check.

    Returns:
        tuple: A tuple containing:
               (bool): True if the file is valid, False otherwise.
               (list): A list of the out-of-range MIDI note numbers found.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return False, []

    invalid_notes = set()
    try:
        mid = mido.MidiFile(file_path)
        for msg in mid:
            if msg.type == 'note_on':
                if msg.note not in FISHER_PRICE_NOTES:
                    invalid_notes.add(msg.note)
    except Exception as e:
        print(f"Error reading MIDI file '{file_path}': {e}")
        return False, []

    if not invalid_notes:
        return True, []
    else:
        # Return a sorted list of the unique invalid notes
        return False, sorted(list(invalid_notes))

if __name__ == '__main__':
    # This part allows you to run the script directly from the command line for testing
    # Usage: python diagnostic.py "path/to/your/midi_file.mid"
    
    if len(sys.argv) != 2:
        print("Usage: python diagnostic.py <path_to_midi_file>")
        sys.exit(1)

    midi_file = sys.argv[1]
    
    is_valid, bad_notes = check_midi_notes(midi_file)
    
    print("-" * 30)
    print(f"Checking file: {os.path.basename(midi_file)}")
    print("-" * 30)

    if is_valid:
        print("✅ SUCCESS: All notes are within the Fisher-Price 22-note range.")
    else:
        print("❌ FAILED: The following notes are outside the allowed range:")
        for note in bad_notes:
            note_name = MIDI_NOTE_NAMES.get(note, 'Unknown Note')
            print(f"  - Note Number: {note} ({note_name})")
        print("\nValid range is MIDI notes 55 (G3) through 76 (E5).")