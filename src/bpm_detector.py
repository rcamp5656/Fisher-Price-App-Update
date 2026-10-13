#
# src/bpm_detector_fixed.py
#
import argparse
import mido
import sys

def detect_and_print_bpm(midi_file_path):
    """
    Opens a MIDI file, finds the BPM from the first track, and prints it.
    If no tempo is found, it reports an error.
    """
    try:
        mid = mido.MidiFile(midi_file_path)
        # For Type 1 MIDI files, the first track is the "conductor" track
        # that contains tempo and other meta messages.
        if mid.tracks:
            # Check only the first track for a tempo message
            for msg in mid.tracks[0]:
                if msg.type == 'set_tempo':
                    bpm = mido.tempo2bpm(msg.tempo)
                    print(int(round(bpm)))
                    return # Exit function successfully

        # Fallback for Type 0 files or if no tempo in track 0
        for msg in mid:
            if msg.type == 'set_tempo':
                bpm = mido.tempo2bpm(msg.tempo)
                print(int(round(bpm)))
                return # Exit function successfully

        # If no tempo message was found anywhere
        print("Error: No tempo information found in the MIDI file.", file=sys.stderr)
        sys.exit(1)

    except FileNotFoundError:
        print(f"Error: File not found at '{midi_file_path}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch other errors (e.g., corrupted file, not a MIDI file)
        print(f"Error processing MIDI file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect BPM from a MIDI file and print it.")
    parser.add_argument("--input", required=True, help="Path to the input MIDI file.")
    args = parser.parse_args()
    
    detect_and_print_bpm(args.input)