#!/usr/bin/env python3

import sys
import threading
import curses
import curses.textpad

try:
    import mido
    import rtmidi
    from midi import Midi
except ImportError:
    pass

from sound import play_note, play
import ui_curses.const
from record import Record

# A simple class to hold the application's state
class AppState:
    """Encapsulates the application's runtime state."""
    def __init__(self, stdscr, display, midi, audio):
        self.stdscr = stdscr
        self.display = display
        self.midi = midi
        self.audio = audio
        self.record = display.record
        self.cursor_y = display.start_y + display.offset_x
        self.cursor_x = display.start_x + display.offset_y
        self.thread_player = None
        self.is_running = True

# --- Handler Functions for Key Presses ---

def handle_quit(state):
    """Signals the application to exit."""
    state.is_running = False

def handle_move(state, dy=0, dx=0):
    """Handles cursor movement, including horizontal scrolling."""
    next_y, next_x = state.cursor_y + dy, state.cursor_x + dx

    if dx != 0: # Horizontal movement
        if state.display.can_move(state.cursor_y, next_x):
            state.cursor_x = next_x
            state.display.draw_beat_index(state.cursor_x)
        elif dx > 0: # Scroll right
            state.display.display_from += 1
            state.stdscr.erase()
            state.display.draw(state.cursor_x, state.cursor_y)
        elif dx < 0 and state.display.display_from > 0: # Scroll left
            state.display.display_from -= 1
            state.stdscr.erase()
            state.display.draw(state.cursor_x, state.cursor_y)
    elif dy != 0: # Vertical movement
        if state.display.can_move(next_y, state.cursor_x):
            state.cursor_y = next_y
            state.display.draw(state.cursor_x, state.cursor_y)

def handle_export_midi(state):
    """Exports the current record to a MIDI file."""
    if "mido" in sys.modules:
        state.midi.export_to_mid(state.record)

def handle_set_player_start(state):
    """Sets the player start position to the current cursor position."""
    state.display.player_start_at_value(state.display.display_from + state.cursor_x - 1)
    state.display.draw(state.cursor_x, state.cursor_y)

def handle_adjust_player_start(state, delta):
    """Increments or decrements the player start position."""
    if delta > 0:
        state.display.player_start_at_inc()
    else:
        state.display.player_start_at_dec()
    state.display.draw(state.cursor_x, state.cursor_y)

def handle_shift_beat(state, direction):
    """Shifts notes in the current beat left or right."""
    if direction > 0:
        state.record.right_shift(state.cursor_x - 1)
    else:
        state.record.left_shift(state.cursor_x - 1)
    state.display.draw_partition()

def handle_edit_title(state):
    """Opens a textbox to edit the record's title."""
    h, w = state.stdscr.getmaxyx()
    # Position the edit window dynamically near the bottom
    edit_y = max(20, h - 5)
    edit_w = min(79, w - 2)
    
    editwin = curses.newwin(1, edit_w, edit_y, 1)
    editwin.addstr(0, 0, state.record.title)
    box = curses.textpad.Textbox(editwin, insert_mode=True)
    
    box.edit()
    title = box.gather()
    state.display.record.title = title.strip()
    state.display.draw(state.cursor_x, state.cursor_y)

def handle_toggle_note(state):
    """Toggles a note on or off at the current cursor position."""
    x = state.display.display_from + state.cursor_x - 1
    y = state.cursor_y - 1

    if x >= state.record.beats_count:
        state.record.resize_beats(x + 1)

    if state.display.tone_descending:
        y = Record.TONES_COUNT - 1 - y

    if 0 <= y < Record.TONES_COUNT:
        state.record.reverse_note(x, y)
    state.display.draw_partition()

def handle_play_current_note(state):
    """Plays the single note corresponding to the cursor's row."""
    tone_index = state.cursor_y - (state.display.start_y + state.display.offset_y)
    if state.display.tone_descending:
        tone_index = Record.TONES_COUNT - 1 - tone_index
    if 0 <= tone_index < len(state.record.NOTES):
        play_note(state.record.NOTES[tone_index], state.audio, state.midi)

def handle_play_current_beat(state):
    """Plays all notes in the current beat (column)."""
    beats = state.record.get_beats(state.cursor_x - 1)
    for tone_index, has_note in enumerate(beats):
        if has_note and tone_index < len(state.record.NOTES):
            play_note(state.record.NOTES[tone_index], state.audio, state.midi)

def handle_toggle_playback(state):
    """Starts or stops the background playback thread."""
    if state.thread_player and state.thread_player.is_alive():
        state.thread_player.do_run = False
        state.thread_player.join()
        state.display.draw(state.cursor_x, state.cursor_y) # Redraw to clear progress bar
    else:
        state.thread_player = threading.Thread(
            target=play,
            args=(
                state.audio,
                state.midi,
                state.record,
                state.display.player_start_at,
                state.display.update_progress_bar,
            ),
        )
        state.thread_player.start()

def handle_save(state):
    """Saves the record."""
    state.record.save()

def handle_load(state):
    """Loads a record and redraws the screen."""
    state.record.load()
    state.display.draw(state.cursor_x, state.cursor_y)

def handle_resize(state):
    """Handles terminal resize events."""
    state.display.set_size()
    state.stdscr.erase()
    state.display.draw(state.cursor_x, state.cursor_y)

# --- Main Application Runner ---

def run_curses(stdscr, display, midi, audio):
    # Set up curses color pairs
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(ui_curses.const.PAIR_NOTE, curses.COLOR_RED, curses.COLOR_YELLOW)
    curses.init_pair(ui_curses.const.PAIR_INPUT_A, -1, curses.COLOR_CYAN)
    curses.init_pair(ui_curses.const.PAIR_INPUT_B, -1, curses.COLOR_BLACK)
    curses.init_pair(ui_curses.const.PAIR_HIGHLIGHT, curses.COLOR_RED, -1)

    # Initialize application state
    state = AppState(stdscr, display, midi, audio)
    display.window = stdscr
    display.set_size()
    display.draw(state.cursor_x, state.cursor_y)

    key_handlers = {
        curses.KEY_UP: lambda s: handle_move(s, dy=-1),
        curses.KEY_DOWN: lambda s: handle_move(s, dy=1),
        curses.KEY_LEFT: lambda s: handle_move(s, dx=-1),
        curses.KEY_RIGHT: lambda s: handle_move(s, dx=1),
        ord('q'): handle_quit,
        ord('x'): handle_export_midi,
        ord('o'): handle_set_player_start,
        ord('i'): lambda s: handle_adjust_player_start(s, 1),
        ord('u'): lambda s: handle_adjust_player_start(s, -1),
        ord('+'): lambda s: handle_shift_beat(s, 1),
        ord('-'): lambda s: handle_shift_beat(s, -1),
        ord('e'): handle_edit_title,
        ord(' '): handle_toggle_note,
        ord('t'): handle_play_current_note,
        ord('r'): handle_play_current_beat,
        ord('p'): handle_toggle_playback,
        ord('s'): handle_save,
        ord('l'): handle_load,
        curses.KEY_RESIZE: handle_resize,
    }

    while state.is_running:
        stdscr.move(state.cursor_y, state.cursor_x)
        ch = stdscr.getch()

        handler = key_handlers.get(ch)
        if handler:
            handler(state)

    # Clean up the playback thread before exiting
    if state.thread_player and state.thread_player.is_alive():
        state.thread_player.do_run = False
        state.thread_player.join()