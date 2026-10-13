#!/usr/bin/env python3

import sys
import argparse
import curses

try:
    import mido
except ImportError:
    mido = None

try:
    import rtmidi
except ImportError:
    rtmidi = None

try:
    from playsound import playsound
except ImportError:
    playsound = None

try:
    from midi import Midi
except ImportError:
    Midi = None

from record import Record
from ui_curses.display import CursesDisplay
from ui_curses.control import run_curses
# 1. ADDED THIS IMPORT to get the default beat count.
from ui_curses.const import BEAT_COUNT

if __name__ == "__main__":
    # 2. CORRECTED: Initializes a new record with the default beat count.
    record = Record(BEAT_COUNT)
    parser = argparse.ArgumentParser()

    # General arguments
    parser.add_argument("--fpr", help=".fpr file to open")
    parser.add_argument("--title", help="set the title of a new tune")
    parser.add_argument("--low", help="display low pitch notes first", action="store_true")
    parser.add_argument("--audio", choices=["wav", "midi"], help="use wav or midi as audio backend")
    parser.set_defaults(audio="wav")
    parser.add_argument("--check-packages", help="Check if optional packages are installed and quit", action="store_true")

    # MIDI related arguments
    if mido:
        # Generic MIDI import argument
        parser.add_argument("--mid", help="import from a generic .mid file for the music box")
        parser.add_argument("--bpm", help="override bpm for midi import")

        if rtmidi:
            parser.add_argument("--port", help="name of the midi port to use")
            parser.add_argument("--program", help="midi instrument code")

    args = parser.parse_args()

    if args.check_packages:
        print(f"playsound (wav audio backend): {playsound is not None}")
        print(f"mido (midi import/export): {mido is not None}")
        print(f"rtmidi (mido audio backend): {rtmidi is not None}")
        sys.exit()

    if args.fpr:
        record.filename = args.fpr
    if args.title:
        record.title = args.title

    if args.audio == "wav" and not playsound:
        sys.exit("Wav audio backend selected but playsound package not found.")
    if args.audio == "midi" and (not mido or not rtmidi):
        sys.exit("Midi audio backend selected but mido and rtmidi packages not found.")

    midi = Midi() if mido else None

    if args.audio == "midi" and rtmidi and midi:
        program = int(args.program) if args.program else 10
        portname = args.port if args.port else ""
        midi.open_port(portname)
        midi.set_program(program)

    if args.fpr:
        record.load()
    else:
        # This check ensures new records are correctly sized.
        if record.beats_count == 0:
             record.resize_beats(BEAT_COUNT)
        record.filename = record.title + ".fpr"

    if mido:
        bpm_override = int(args.bpm) if args.bpm else None

        if args.mid:
            midi.import_from_mid(record, args.mid, bpm_override, 0)

    display = CursesDisplay(record)
    if args.low:
        display.tone_descending = False

    try:
        curses.wrapper(run_curses, display, midi, args.audio)
        if args.audio == "midi" and rtmidi:
            midi.close_port()
    except curses.error:
        sys.exit("Error when drawing to terminal (terminal too small?)")