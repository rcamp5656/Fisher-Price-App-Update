# record.py

class Record:
    # Set the Fisher-Price standard of 86 beats as a constant.
    MAX_BEAT = 86
    TONES_COUNT = 22
    TRACKS_COUNT = TONES_COUNT
    NOTES = [
        60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73,
        74, 75, 76, 77, 78, 79, 80, 81,
    ]

    def __init__(self, beats_count=MAX_BEAT):
        self.filename = ""
        self.title = ""
        self.comment = ""
        # The record is always initialized to the max beat count.
        self.beats_count = beats_count if beats_count > 0 else Record.MAX_BEAT
        self._partition = [[False] * self.beats_count for _ in range(Record.TONES_COUNT)]

    def get_track(self, track_index):
        return self._partition[track_index]

    def get_beats(self, beat_index):
        """Returns a list of boolean note values for all tracks at a given beat index."""
        if beat_index >= self.beats_count:
            # If the beat is out of bounds, return a silent beat.
            return [False] * self.TONES_COUNT
            
        # Use a list comprehension to build a list of all note states for the given beat.
        return [self._partition[track_idx][beat_index] for track_idx in range(self.TONES_COUNT)]

    def has_note(self, beat_index, track_index):
        if beat_index >= self.beats_count:
            return False
        return self._partition[track_index][beat_index]

    def set_note(self, beat_index, track_index, value):
        if beat_index < self.beats_count:
            self._partition[track_index][beat_index] = value
    
    def save(self):
        # A simple save method for the .fpr format
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(f"TITLE={self.title}\n")
            f.write(f"COMMENT={self.comment}\n")
            for beat_idx in range(self.beats_count):
                line = ""
                for track_idx in range(self.TONES_COUNT):
                    if self.has_note(beat_idx, track_idx):
                        line += "1"
                    else:
                        line += "0"
                f.write(line + "\n")

    def load(self):
        # A simple load method for the .fpr format
        with open(self.filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("TITLE="):
                    self.title = line.strip().split("=")[1]
                elif line.startswith("COMMENT="):
                    self.comment = line.strip().split("=")[1]
            
            note_lines = [l for l in lines if not l.startswith(("TITLE=", "COMMENT="))]
            self.resize_beats(len(note_lines))

            for beat_idx, line in enumerate(note_lines):
                for track_idx, char in enumerate(line.strip()):
                    if char == '1':
                        self.set_note(beat_idx, track_idx, True)

    def resize_beats(self, new_beats_count):
        if new_beats_count == self.beats_count:
            return
        
        old_beats_count = self.beats_count
        new_partition = [[False] * new_beats_count for _ in range(Record.TONES_COUNT)]

        beats_to_copy = min(old_beats_count, new_beats_count)
        for track_idx in range(Record.TONES_COUNT):
            for beat_idx in range(beats_to_copy):
                new_partition[track_idx][beat_idx] = self._partition[track_idx][beat_idx]

        self._partition = new_partition
        self.beats_count = new_beats_count
        
    def fill_gaps(self):
        """
        Finds any beat that has no notes and adds a default note to it.
        This prevents silent gaps in the final output.
        """
        # Iterate through each beat index (column) in the record.
        for beat_idx in range(self.beats_count):
            is_beat_silent = True
            # Check every track for a note at the current beat.
            for track_idx in range(self.TONES_COUNT):
                if self.has_note(beat_idx, track_idx):
                    is_beat_silent = False
                    # A note was found, so this beat isn't silent.
                    # We can stop checking this beat and move to the next one.
                    break
            
            # If after checking all tracks, the beat is still silent, fill it.
            if is_beat_silent:
                # Add a default note. Let's use the first track (index 0)
                # as the default note to fill the gap.
                print(f"--> Found silent beat at index {beat_idx}, filling it.")
                self.set_note(beat_idx, 0, True)