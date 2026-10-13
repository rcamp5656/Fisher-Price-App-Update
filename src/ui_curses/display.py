
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
        labels = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5', 'D5', 'E5', 'F5', 'G5',
                  'A5', 'B5', 'C6', 'D6', 'E6', 'F6', 'G6', 'A6', 'B6', 'C7']
        for tone_index, label in zip(range(Record.TONES_COUNT), labels):
            row = tone_index if not self.tone_descending else Record.TONES_COUNT - 1 - tone_index
            for beat_index in range(self.display_from, self.display_from + self.width - self.offset_x):
                if beat_index >= self.record.beats_count:
                    continue
                y = row + self.offset_y
                x = beat_index - self.display_from + self.offset_x
                has_note = self.record.has_note(beat_index, tone_index)
                self.window.addstr(y, 0, label.ljust(4))
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
            self.window.addch(self.offset_y - 1, idx - self.display_from + self.offset_x, value)

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
        labels = ['C7', 'B6', 'A6', 'G6', 'F6', 'E6', 'D6', 'C6', 'B5', 'A5', 'G5', 'F5', 'E5',
                  'D5', 'C5', 'B4', 'A4', 'G4', 'F4', 'E4', 'D4', 'C4'] if self.tone_descending else                  ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5', 'D5', 'E5', 'F5', 'G5', 'A5',
                  'B5', 'C6', 'D6', 'E6', 'F6', 'G6', 'A6', 'B6', 'C7']
        for i, label in enumerate(labels):
            self.window.addstr(i + self.offset_y, 0, label.ljust(4))
