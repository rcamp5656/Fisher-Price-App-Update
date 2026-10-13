import argparse
from record import Record
from midi import Midi
import os

def main():
    parser = argparse.ArgumentParser(description="Convert a MIDI file to a .fpr file.")
    parser.add_argument("--input", required=True, help="Path to the input MIDI file.")
    parser.add_argument("--output", required=True, help="Path for the output .fpr file.")
    # --- CHANGE 1: Added the required --bpm argument ---
    parser.add_argument("--bpm", required=True, type=int, help="BPM of the original song.")
    args = parser.parse_args()

    # Initialize the record and midi objects
    record = Record(beats_count=1) # Initial size, will be resized on import
    midi_converter = Midi()

    # --- CHANGE 2: Updated print statement for better feedback ---
    print(f"--> Importing notes from {os.path.basename(args.input)} at {args.bpm} BPM...")

    # --- CHANGE 3: Passed the bpm argument to the import function ---
    midi_converter.import_from_mid(record, args.input, args.bpm, 0)
    
    # This part of your code remains the same
    print("--> Filling in silent beats...")
    record.fill_gaps()

    note_count = 0
    for beat_index in range(record.beats_count):
        if any(record.get_beats(beat_index)):
            note_count += 1
            
    if note_count > 0:
        print(f"--> Success: Song now has notes in {note_count} beats.")
    else:
        print(f"--> WARNING: No notes were found in the MIDI file. The output will be silent.")

    record.filename = args.output
    record.title = os.path.splitext(os.path.basename(args.input))[0]
    
    print(f"--> Saving to {os.path.basename(args.output)}...")
    record.save()
    print("--> Conversion complete.")


if __name__ == "__main__":
    main()