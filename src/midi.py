import os
import math
import mido
from record import Record

class Midi:
    program = 10
    port = None

    def open_port(self, portname):
        try:
           Midi.port = mido.open_output(portname)
        except:
           Midi.port = mido.open_output()

    def close_port(self):
        Midi.port.close()

    def set_program(self, program):
        Midi.program = program
        self.port.send(mido.Message("program_change", program=program))

    def play_note(self, note):
        self.port.send(mido.Message("note_on", note=note))

    def _detect_bpm(self, mid_file):
        """
        Detects BPM from a MIDI file using the logic from bpm_detector.py.
        It finds the first 'set_tempo' message and returns the BPM.
        Defaults to 120 if no tempo is found.
        """
        for msg in mid_file:
            if msg.type == 'set_tempo':
                bpm = mido.tempo2bpm(msg.tempo)
                return int(round(bpm))
        return 120

    def export_to_mid(self, record):
        ticks = 480
        mid = mido.MidiFile(type=0, ticks_per_beat=ticks)
        track = mido.MidiTrack()
        mid.tracks.append(track)

        track.append(mido.Message("program_change", program=Midi.program, time=0))

        for beat_index in range(record.beats_count):
            for track_index in range(Record.TONES_COUNT):
                if record.has_note(beat_index, track_index):
                    track.append(
                        mido.Message("note_on", note=record.NOTES[track_index], time=0)
                    )
            track.append(mido.Message("note_off", time=ticks))

        mid.save(record.title + ".mid")

    def import_from_mid(self, record, filename, bpm_override, offset):
        FPR_SEC_BETWEEN_BEATS = 0.25
        mid = mido.MidiFile(filename)
        ticks_per_beat = mid.ticks_per_beat
        
        # Use the new BPM detection logic
        if bpm_override:
            bpm = bpm_override
        else:
            bpm = self._detect_bpm(mid)
        
        tempo = mido.bpm2tempo(bpm)

        total_time_ticks = 0
        
        # Simplified single loop for note processing
        for msg in mid:
            total_time_ticks += msg.time

            # Skip messages that are not musical notes.
            if msg.is_meta or msg.type != "note_on" or msg.velocity == 0:
                continue

            # Process the valid musical note using the pre-determined tempo.
            time_in_seconds = mido.tick2second(total_time_ticks, ticks_per_beat, tempo)
            beat_index = round(time_in_seconds / FPR_SEC_BETWEEN_BEATS)

            note = msg.note + offset
            
            # Find the closest available note on the music box.
            if note not in record.NOTES:
                nabv = note
                nbel = note
                found = False
                while not found:
                    nabv += 1
                    nbel -= 1
                    if nabv in record.NOTES:
                        note = nabv
                        found = True
                    elif nbel in record.NOTES:
                        note = nbel
                        found = True

            if beat_index >= record.beats_count:
                record.resize_beats(beat_index + 1)
            
            track_index = record.NOTES.index(note)
            record.set_note(beat_index, track_index, True)

        record.filename = os.path.splitext(filename)[0] + ".fpr"
        basename = os.path.basename(filename)
        record.title = os.path.splitext(basename)[0]
        record.comment = f"""Imported from {os.path.basename(filename)}\nBPM: {bpm}"""