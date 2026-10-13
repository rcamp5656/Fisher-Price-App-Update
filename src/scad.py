# src/convert.py

import argparse
from record import Record
from midi import Midi

def main():
    parser = argparse.ArgumentParser(description="Convert a MIDI file to a fixed-length FPR file.")
    parser.add_argument("--input", required=True, help="Path to the input MIDI file.")
    parser.add_argument("--output", required=True, help="Path for the output .fpr file.")
    parser.add_argument("--bpm", type=int, help="BPM override for the MIDI import.")
    args = parser.parse_args()

    # Create a new record, which defaults to 86 beats.
    record = Record()
    midi_handler = Midi()

    # Import notes from the MIDI file.
    midi_handler.import_from_mid(record, args.input, bpm_override=args.bpm, offset=0)
    
    # CRITICAL STEP: Ensure the record is exactly 86 beats long.
    # It will truncate longer songs or pad shorter ones.
    if record.beats_count != Record.MAX_BEAT:
        record.resize_beats(Record.MAX_BEAT)
    
    # Save the standardized 86-beat record to the specified .fpr file.
    record.filename = args.output
    record.save()
    print(f"Success: Song now has notes in {record.beats_count} beats.")
    print(f"Saving to {record.filename}...")

if __name__ == "__main__":
    main()