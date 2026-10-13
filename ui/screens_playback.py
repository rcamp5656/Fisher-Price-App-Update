"""
ui/screens_playback.py
Contains the Kivy screens related to playing MIDI files and browsing
converted or enhanced content.
"""
# --- Standard Library Imports ---
import os
import threading
import logging
import time
import shutil
import textwrap
import re

# --- Third-Party Imports ---
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.properties import NumericProperty
from kivy.clock import Clock
from kivy.graphics import Rectangle, PushMatrix, PopMatrix, Rotate
import mido

# --- Local Module Imports ---
from constants import (
    FILES_PER_PAGE, ENHANCED_FOLDER, CONVERTED_FOLDER,
    RECORDS_FOLDER, INSTRUMENT_DATABASE
)
from ui.widgets import get_contrasting_colors, make_nav, split_filename

logger = logging.getLogger(__name__)

# =======================================================================
# === Screen Classes Begin
# =======================================================================

class EnhancedBandSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0
        self._colors = get_contrasting_colors()
        root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text="Select Artist (Enhanced)", font_size=24, size_hint_y=0.1))
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.8)
        root.add_widget(self.grid)
        nav = [('Back to Main Browser', lambda *_: setattr(self.manager, 'current', 'files')), ('Prev Page', self.prev_page), ('Next Page', self.next_page)]
        root.add_widget(make_nav(nav))
        self.add_widget(root)

    def on_enter(self, *args):
        self.page = 0
        try:
            self.bands = sorted([d for d in os.listdir(ENHANCED_FOLDER) if os.path.isdir(os.path.join(ENHANCED_FOLDER, d))])
        except Exception as e:
            logger.error(f"Could not read Enhanced_MIDI folder: {e}"); self.bands = []
        self.populate_grid()

    def populate_grid(self, *args):
        self.grid.clear_widgets()
        start = self.page * FILES_PER_PAGE
        page_items = self.bands[start:start + FILES_PER_PAGE]
        for idx, band_name in enumerate(page_items):
            btn = Button(text=split_filename(band_name), background_normal='', background_color=self._colors[idx % len(self._colors)], font_size=12)
            btn.band_path = os.path.join(ENHANCED_FOLDER, band_name)
            btn.bind(on_press=self.select_band)
            self.grid.add_widget(btn)
        for _ in range(len(page_items), FILES_PER_PAGE):
            self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))

    def select_band(self, instance):
        self.manager.get_screen('enhanced_songs').setup_songs(instance.band_path)
        self.manager.current = 'enhanced_songs'

    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.bands): self.page += 1; self.populate_grid()

    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()

# -----------------------------------------------------------------------

class EnhancedSongSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0; self.band_path = ''
        self._colors = get_contrasting_colors()
        root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text="Select Song (Enhanced)", font_size=24, size_hint_y=0.1))
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.8); root.add_widget(self.grid)
        nav = [('Back to Artists', lambda *_: setattr(self.manager, 'current', 'enhanced_bands')), ('Prev Page', self.prev_page), ('Next Page', self.next_page)]
        root.add_widget(make_nav(nav)); self.add_widget(root)

    def setup_songs(self, band_path):
        self.page = 0; self.band_path = band_path
        self.songs = sorted([d for d in os.listdir(band_path) if os.path.isdir(os.path.join(band_path, d))])
        self.populate_grid()
    
    def populate_grid(self):
        self.grid.clear_widgets()
        start = self.page * FILES_PER_PAGE
        page_items = self.songs[start:start + FILES_PER_PAGE]
        for idx, song_name in enumerate(page_items):
            btn = Button(text=split_filename(song_name), background_normal='', background_color=self._colors[idx], font_size=12)
            btn.song_path = os.path.join(self.band_path, song_name)
            btn.bind(on_release=self.select_song)
            self.grid.add_widget(btn)
        for _ in range(len(page_items), FILES_PER_PAGE):
            self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))
    
    def select_song(self, instance):
        self.manager.get_screen('enhanced_versions').setup_versions(instance.song_path)
        self.manager.current = 'enhanced_versions'

    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.songs): self.page += 1; self.populate_grid()
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()

# -----------------------------------------------------------------------

class EnhancedVersionSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0; self.song_path = ''
        self._colors = get_contrasting_colors()
        root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text="Select Version to Play (Enhanced)", font_size=24, size_hint_y=0.1))
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.8); root.add_widget(self.grid)
        nav = [('Back to Songs', lambda *_: setattr(self.manager, 'current', 'enhanced_songs')), ('Prev Page', self.prev_page), ('Next Page', self.next_page)]
        root.add_widget(make_nav(nav)); self.add_widget(root)
        
    def setup_versions(self, song_path):
        self.page = 0; self.song_path = song_path
        self.versions = sorted([f for f in os.listdir(song_path) if f.lower().endswith('.mid')])
        self.populate_grid()

    def populate_grid(self):
        self.grid.clear_widgets()
        start = self.page * FILES_PER_PAGE
        page_items = self.versions[start:start + FILES_PER_PAGE]
        for idx, fname in enumerate(page_items):
            btn = Button(text=split_filename(fname.replace('.mid','')), background_normal='', background_color=self._colors[idx], font_size=12)
            btn.fullpath = os.path.join(self.song_path, fname)
            btn.bind(on_press=self.play_enhanced_file)
            self.grid.add_widget(btn)
        for _ in range(len(page_items), FILES_PER_PAGE):
            self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))

    def play_enhanced_file(self, instance):
        player_screen = self.manager.get_screen('player')
        player_screen.play_midi(
            instance.fullpath,
            album_name=os.path.basename(os.path.dirname(self.song_path)),
            song_name=os.path.basename(self.song_path),
            return_screen_name=self.name
        )
        self.manager.current = 'player'

    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.versions): self.page += 1; self.populate_grid()
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()       

# -----------------------------------------------------------------------

class ConvertedArtistSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0; self._colors = get_contrasting_colors(); root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text="Select Artist", font_size=24, size_hint_y=0.1))
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.8); root.add_widget(self.grid)
        nav = [('Back to Main Browser', lambda *_: setattr(self.manager, 'current', 'files')), ('Prev Page', self.prev_page), ('Next Page', self.next_page)]
        root.add_widget(make_nav(nav)); self.add_widget(root)
    
    def on_enter(self, *args):
        self.page = 0
        try:
            self.artists = sorted([d for d in os.listdir(CONVERTED_FOLDER) if os.path.isdir(os.path.join(CONVERTED_FOLDER, d))])
        except FileNotFoundError:
            self.artists = []
        self.populate_grid()

    def populate_grid(self):
        self.grid.clear_widgets(); start = self.page * FILES_PER_PAGE; page_items = self.artists[start:start + FILES_PER_PAGE]
        for idx, artist_name in enumerate(page_items):
            btn = Button(text=split_filename(artist_name), background_normal='', background_color=self._colors[idx], font_size=12)
            btn.artist_path = os.path.join(CONVERTED_FOLDER, artist_name); btn.bind(on_release=self.select_artist); self.grid.add_widget(btn)
        for _ in range(len(page_items), FILES_PER_PAGE): self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))
    
    def select_artist(self, instance):
        self.manager.get_screen('converted_songs').setup_songs(instance.artist_path)
        self.manager.current = 'converted_songs'
    
    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.artists): self.page += 1; self.populate_grid()
    
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()

# -----------------------------------------------------------------------

class ConvertedSongSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0; self._colors = get_contrasting_colors(); root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text="Select Song", font_size=24, size_hint_y=0.1))
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.8); root.add_widget(self.grid)
        nav = [('Back to Artists', lambda *_: setattr(self.manager, 'current', 'converted_artists')), ('Prev Page', self.prev_page), ('Next Page', self.next_page)]
        root.add_widget(make_nav(nav)); self.add_widget(root)

    def setup_songs(self, artist_path):
        self.page = 0; self.artist_path = artist_path
        self.songs = sorted([d for d in os.listdir(artist_path) if os.path.isdir(os.path.join(artist_path, d))])
        self.populate_grid()

    def populate_grid(self):
        self.grid.clear_widgets(); start = self.page * FILES_PER_PAGE; page_items = self.songs[start:start + FILES_PER_PAGE]
        for idx, song_name in enumerate(page_items):
            btn = Button(text=split_filename(song_name), background_normal='', background_color=self._colors[idx], font_size=12)
            btn.song_path = os.path.join(self.artist_path, song_name); btn.bind(on_release=self.select_song); self.grid.add_widget(btn)
        for _ in range(len(page_items), FILES_PER_PAGE): self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))

    def select_song(self, instance):
        self.manager.get_screen('chunks').setup_chunks(instance.song_path)
        self.manager.current = 'chunks'
    
    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.songs): self.page += 1; self.populate_grid()
    
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()
        
# -----------------------------------------------------------------------

class ChunkSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dir_path, self.page, self.files, self.selected_chunk_path = '', 0, [], None
        self._colors = get_contrasting_colors()
        root = BoxLayout(orientation='vertical')
        main_content = BoxLayout(size_hint_y=0.9)
        
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.7)
        left_panel.add_widget(Label(text="Select a Chunk", font_size=24, size_hint_y=0.1, color=(1,0.84,0,1)))
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.9)
        left_panel.add_widget(self.grid)
        
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.3, padding=10, spacing=10)
        right_panel.add_widget(Label(text="Chunk Info", font_size=24, size_hint_y=0.1, color=(1,0.84,0,1)))
        self.selected_file_label = Label(text="No chunk selected", size_hint_y=0.1, font_size=16)
        right_panel.add_widget(self.selected_file_label)
        
        scroll = ScrollView(size_hint_y=0.8)
        self.notes_label = Label(text="", font_size=16, size_hint_y=None, halign='left', valign='top', markup=True)
        self.notes_label.bind(width=lambda *x: self.notes_label.setter('text_size')(self.notes_label, (self.notes_label.width-20, None)))
        self.notes_label.bind(texture_size=lambda i,v: setattr(i, 'height', v[1]))
        scroll.add_widget(self.notes_label)
        right_panel.add_widget(scroll)
        
        main_content.add_widget(left_panel); main_content.add_widget(right_panel)
        root.add_widget(main_content)

        self.play_button = Button(text='Play Selected', disabled=True, on_release=self.play_selected_chunk, background_color=(0,0.8,0,1))
        nav_buttons = [('Back to Songs', lambda *_: setattr(self.manager, 'current', 'converted_songs')),
                       ('Prev Page', self.prev_page), ('Next Page', self.next_page)]
        nav_bar = make_nav(nav_buttons)
        nav_bar.add_widget(self.play_button)
        root.add_widget(nav_bar)
        self.add_widget(root)

    def setup_chunks(self, dir_path):
        self.dir_path, self.page = dir_path, 0
        try:
            self.files = sorted([f for f in os.listdir(dir_path) if f.lower().endswith('.mid')], 
                                key=lambda f: int(re.search(r'_(\d+)_', f).group(1)) if re.search(r'_(\d+)_', f) else 0)
        except (ValueError, AttributeError): self.files = sorted([f for f in os.listdir(dir_path) if f.lower().endswith('.mid')])
        self.populate_grid()
        self.selected_chunk_path, self.play_button.disabled = None, True
        self.notes_label.text, self.selected_file_label.text = "", "No chunk selected"

    def populate_grid(self, *args):
        self.grid.clear_widgets()
        chunks_per_page = 49
        start = self.page * chunks_per_page
        page_items = self.files[start:start+chunks_per_page]
        for idx, fname in enumerate(page_items):
            btn = Button(text=split_filename(fname.replace('.mid',''),12), background_normal='', background_color=self._colors[idx%len(self._colors)], font_size=12)
            btn.fullpath = os.path.join(self.dir_path, fname)
            btn.bind(on_press=self.select_chunk)
            self.grid.add_widget(btn)
        for _ in range(len(page_items), chunks_per_page): self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))

    def select_chunk(self, instance):
        self.selected_chunk_path = instance.fullpath
        self.selected_file_label.text = f"Selected: {os.path.basename(instance.fullpath)}"
        self.play_button.disabled = False
        self.display_chunk_notes()

    def display_chunk_notes(self):
        if not self.selected_chunk_path: return
        try:
            mid = mido.MidiFile(self.selected_chunk_path)
            notes, total, progs = set(), 0, set()
            for msg in mid:
                if msg.type == 'note_on' and msg.velocity > 0: notes.add(msg.note); total += 1
                elif msg.type == 'program_change': progs.add(msg.program)
            
            info = f"[b]Total Notes:[/b] {total}\n[b]Ticks/Beat:[/b] {mid.ticks_per_beat}\n\n"
            if notes: info += f"[b]Unique Notes ({len(notes)}):[/b]\n{textwrap.fill(' '.join(map(str, sorted(list(notes)))), 30)}\n\n"
            if progs:
                info += f"[b]Instruments:[/b]\n"
                for p in sorted(list(progs)): info += f"- {INSTRUMENT_DATABASE.get(p,{}).get('name',f'Unknown {p}')}\n"
            self.notes_label.text = info
        except Exception as e:
            self.notes_label.text = f"Error reading file:\n{e}"; logger.error(f"Error viewing chunk: {e}")

    def play_selected_chunk(self, instance):
        if not self.selected_chunk_path: return
        try:
            song, chunk = os.path.basename(self.dir_path), os.path.basename(self.selected_chunk_path)
            shutil.copy(self.selected_chunk_path, os.path.join(RECORDS_FOLDER, f"{song}_{chunk}"))
        except Exception as e: logger.error(f"Could not copy to Records: {e}")
        self.manager.get_screen('player').play_midi(self.selected_chunk_path, os.path.basename(os.path.dirname(self.dir_path)), os.path.basename(self.dir_path), self.name)
        self.manager.current = 'player'

    def next_page(self, instance):
        if (self.page + 1) * 49 < len(self.files): self.page += 1; self.populate_grid()
    def prev_page(self, instance):
        if self.page > 0: self.page -= 1; self.populate_grid()

# -----------------------------------------------------------------------

class FisherPriceDisplayScreen(Screen):
    angle = NumericProperty(0)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.play_thread, self.file_path, self._spin_event = None, None, None
        self.stop_event, self.pause_event = threading.Event(), threading.Event()
        self.pitch_offset, self.return_screen = 0, 'files'

        root = BoxLayout(orientation='vertical')
        float_layout = FloatLayout(size_hint=(1, 0.7))
        with float_layout.canvas.before:
            PushMatrix()
            self.rot = Rotate(angle=self.angle, origin=(0,0))
            self.background_rect = Rectangle(source='Record_idle.png', size=(0,0), pos=(0,0))
        with float_layout.canvas.after: PopMatrix()
        float_layout.bind(size=self._update_canvas, pos=self._update_canvas)
        root.add_widget(float_layout)

        label_box = BoxLayout(orientation='vertical', size_hint=(0.4,0.2), pos_hint={'center_x':0.5, 'y':0.65})
        self.album_label = Label(text='--', color=(0.1,0.1,0.1,1), bold=True, font_size=24, halign='center')
        self.song_label = Label(text='--', color=(0.1,0.1,0.1,1), bold=True, font_size=24, halign='center')
        self.soundfont_label = Label(text='SF: Default', color=(0.1,0.1,0.1,1), font_size=16, halign='center')
        label_box.add_widget(self.album_label); label_box.add_widget(self.song_label); label_box.add_widget(self.soundfont_label)
        float_layout.add_widget(label_box)
        
        controls = BoxLayout(orientation='vertical', size_hint_y=0.3, spacing=5, padding=10)
        slider_layout = BoxLayout(spacing=20, size_hint_y=0.6)
        slider_layout.add_widget(Label(text="Pitch", size_hint_x=0.2))
        self.pitch_slider = Slider(min=-12, max=12, value=0, step=1)
        self.pitch_slider.bind(value=self.update_pitch)
        slider_layout.add_widget(self.pitch_slider)
        controls.add_widget(slider_layout)

        buttons = BoxLayout(size_hint_y=0.4, spacing=4, padding=2)
        buttons.add_widget(Button(text='Back', on_release=self.go_back))
        buttons.add_widget(Button(text='Pause/Resume', on_release=self.toggle_pause))
        buttons.add_widget(Button(text='Stop', on_release=self.stop_playback))
        buttons.add_widget(Button(text='Reset Pitch', on_release=self.reset_controls))
        controls.add_widget(buttons)
        root.add_widget(controls)
        self.add_widget(root)

    def _update_canvas(self, i, v): self.rot.origin, self.background_rect.pos, self.background_rect.size = i.center, i.pos, i.size
    def _update_spin(self, dt): self.angle = (self.angle-20*dt)%360
    def start_spinning(self):
        if not self._spin_event: self._spin_event=Clock.schedule_interval(self._update_spin, 1/60.)
    def stop_spinning(self):
        if self._spin_event: self._spin_event.cancel(); self._spin_event=None
        self.angle=0
    def on_leave(self, *a): self.stop_playback()
    def on_enter(self, *a): self.pause_event.set(); self.reset_controls()
    def is_playing(self): return self.play_thread and self.play_thread.is_alive()
    
    def play_midi(self, file_path, album_name=None, song_name=None, return_screen_name='files'):
        app = App.get_running_app()
        if self.is_playing(): self.stop_playback()
        with app.fs_lock:
            for s in app.player.synths.values():
                if s: s.system_reset()
        self.return_screen, self.file_path = return_screen_name, file_path
        sf1 = app.sf_layer1['name'] if app.sf_layer1['name']!='None' else ''
        self.soundfont_label.text = f"L1: {sf1}\nL2: {app.sf_layer2['name']}"
        if not app.external_midi_enabled:
            with app.fs_lock:
                for s in app.player.synths.values():
                    if s: s.gain = app.current_gain
        self.stop_event.clear(); self.pause_event.set()
        self._update_labels(file_path, album_name, song_name)
        self.play_thread=threading.Thread(target=self._play_loop, args=(file_path,), daemon=True); self.play_thread.start()
        self.start_spinning()

    def _cleanup_playback_resources(self): self._all_notes_off(); self.play_thread=None; self.stop_event.clear(); self.stop_spinning()

    def stop_playback(self, instance=None):
        if self.is_playing(): self.stop_event.set(); self.pause_event.set(); self.play_thread.join(1.0)
        self._cleanup_playback_resources()
        if instance: self.manager.current = self.return_screen

    def _play_loop(self, file_path):
        app=App.get_running_app()
        try:
            for msg in mido.MidiFile(file_path).play():
                if self.stop_event.is_set(): break
                self.pause_event.wait()
                new_msg = msg.copy()
                if new_msg.type in('note_on','note_off') and new_msg.channel!=9:
                    new_msg.note = max(0, min(127, new_msg.note+self.pitch_offset))
                app.player.send_message(new_msg)
        except Exception as e: logger.error(f"Player Screen Error: {e}", exc_info=True)
        finally:
            Clock.schedule_once(lambda dt: self._cleanup_playback_resources())
            if not self.stop_event.is_set(): Clock.schedule_once(lambda dt: setattr(self.manager, 'current', self.return_screen), 0.2)

    def _all_notes_off(self):
        app = App.get_running_app()
        if app and app.player:
            for ch in range(16): app.player.send_message(mido.Message('control_change',channel=ch,control=123,value=0))
            time.sleep(0.05)
        
    def _update_labels(self, file_path, album_name=None, song_name=None):
        try:
            self.album_label.text = album_name.replace('_',' ') if album_name else "Unknown"
            self.song_label.text = song_name.replace('_',' ') if song_name else os.path.splitext(os.path.basename(file_path))[0].replace('_',' ')
        except Exception as e: logger.error(f"Failed to update labels: {e}")
        
    def toggle_pause(self, i):
        if self.is_playing():
            if self.pause_event.is_set(): self.pause_event.clear(); self.stop_spinning()
            else: self.pause_event.set(); self.start_spinning()
        
    def go_back(self, instance): self.stop_playback(instance=True)
    def update_pitch(self, i, value): self.pitch_offset = int(value)
    def reset_controls(self, i=None): self.pitch_slider.value = 0