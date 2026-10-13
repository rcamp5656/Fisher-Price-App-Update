#
# src/bpm_detector.py
#
import argparse
import mido
import sys

def detect_and_print_bpm(midi_file_path):
    """
    Opens a MIDI file, finds the BPM, and prints it to the console.
    Prints a default of 120 if no tempo is found or an error occurs.
    """
    bpm_to_print = 120 # Default BPM
    try:
        mid = mido.MidiFile(midi_file_path)
        for msg in mid: # Look for the first tempo message
            if msg.type == 'set_tempo':
                bpm = mido.tempo2bpm(msg.tempo)
                bpm_to_print = int(round(bpm))
                break # Exit after finding the first tempo
    except Exception:
        # Silently fail on error, the default will be used
        pass

    # Print the result to standard output
    print(bpm_to_print)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect BPM from a MIDI file and print it.")
    parser.add_argument("--input", required=True, help="Path to the input MIDI file.")
    args = parser.parse_args()
    
    try:
        detect_and_print_bpm(args.input)
    except FileNotFoundError:
        print("120") # Print default BPM if file is not found
        sys.exit(1)