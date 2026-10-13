import curses
from record import Record
from ui_curses import const

class CursesDisplay:
    def __init__(self, record):
        self.record = record
        self.window = None
        self.width = 0
        self.height = 0
        self.start_y = 1
        self.start_x = 1
        self.offset_y = 1
        self.offset_x = 1
        self.display_from = 0
        self.player_start_at = 0
        self.tone_descending = True

    def set_size(self):
        self.height, self.width = self.window.getmaxyx()

    def can_move(self, y, x):
        beat_index = self.display_from + x - self.offset_x
        tone_index = y - self.offset_y
        if self.tone_descending:
            tone_index = Record.TONES_COUNT - 1 - tone_index
        return (
            0 <= tone_index < Record.TONES_COUNT
            and 0 <= beat_index < self.record.beats_count
        )

    def draw(self, cursor_x, cursor_y):
        self.window.erase()
        self.draw_beat_index(cursor_x)
        self.draw_labels()
        self.draw_partition()
        self.draw_progress_bar()
        self.window.refresh()

    def draw_partition(self):
        # The labels are drawn from the draw_labels method now
        for tone_index in range(Record.TONES_COUNT):
            row = tone_index if not self.tone_descending else Record.TONES_COUNT - 1 - tone_index
            for beat_index in range(self.display_from, self.display_from + self.width - self.offset_x):
                if beat_index >= self.record.beats_count:
                    continue
                y = row + self.offset_y
                x = beat_index - self.display_from + self.offset_x
                has_note = self.record.has_note(beat_index, tone_index)

                if has_note:
                    self.window.addch(y, x + 4, '+', curses.color_pair(const.PAIR_NOTE))
                else:
                    self.window.addch(y, x + 4, '-')

    def draw_beat_index(self, cursor_x):
        for x in range(self.display_from, self.display_from + self.width - self.offset_x):
            if x >= self.record.beats_count:
                break
            idx = x
            value = str((idx + 1) % 10)
            self.window.addch(self.offset_y - 1, idx - self.display_from + self.offset_x + 4, value)

    def draw_progress_bar(self):
        bar_line = self.offset_y + Record.TONES_COUNT + 1
        self.window.addstr(bar_line, 1, f"Start at: {self.player_start_at}")
        self.window.refresh()

    def update_progress_bar(self, value):
        bar_line = self.offset_y + Record.TONES_COUNT + 1
        self.window.addstr(bar_line, 20, f"Playing: {value}     ")
        self.window.refresh()

    def player_start_at_value(self, value):
        if 0 <= value < self.record.beats_count:
            self.player_start_at = value

    def player_start_at_dec(self):
        if self.player_start_at > 0:
            self.player_start_at -= 1

    def player_start_at_inc(self):
        if self.player_start_at < self.record.beats_count - 1:
            self.player_start_at += 1

    def draw_labels(self):
        # CORRECTED LABELS to match the chromatic scale from C4 to A5
        asc_labels = [
            'C-4', 'C#4', 'D-4', 'D#4', 'E-4', 'F-4', 'F#4', 'G-4',
            'G#4', 'A-4', 'A#4', 'B-4', 'C-5', 'C#5', 'D-5', 'D#5',
            'E-5', 'F-5', 'F#5', 'G-5', 'G#5', 'A-5'
        ]
        
        labels = list(reversed(asc_labels)) if self.tone_descending else asc_labels
        
        for i, label in enumerate(labels):
            self.window.addstr(i + self.offset_y, 0, label.ljust(4))