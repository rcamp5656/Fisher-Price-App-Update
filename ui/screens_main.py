"""
ui/screens_main.py
Contains the primary Kivy screens for browsing, setup, enhancement, and live input.
"""
# --- Standard Library Imports ---
import os
import threading
import logging
import textwrap
import json
import hashlib
import time
import re
import random
from datetime import datetime
from queue import Queue, Empty
import subprocess
import sys
import shutil

# --- pyfluidsynth Imports for MIDI Playback ---
import fluidsynth
import tempfile 
# -----------------------------------------------

# --- Third-Party Imports ---
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image
import pygame 
import mido

# --- Local Module Imports ---
from constants import (
    APP_ROOT, FILES_PER_PAGE, GM_SOUNDFONTS, ENHANCED_FOLDER,
    INSTRUMENT_DATABASE, MAPPINGS_FOLDER, MIDI_FOLDER,
    LIVE_FOLDER, CONVERTED_FOLDER, RECORDS_FOLDER
)
from ui.widgets import get_contrasting_colors, make_nav, split_filename, MySpinner
from midi_utils import convert_and_chunk_threaded

# --- Add These New Imports ---
from music21.midi import translate as midi_translate
from music21.midi.translate import TranslateWarning
import warnings

# Suppress music21 warnings
warnings.filterwarnings("ignore", category=TranslateWarning)
# -----------------------------

logger = logging.getLogger(__name__)

# =======================================================================
# === STANDALONE FLEXIBLE AUDIO PLAYBACK FUNCTION (REVISED FOR STATIC WAV) ===
# =======================================================================

def play_splash_midi_with_settings(rate=192000, channels=2):
    """
    Plays a pre-rendered static WAV file for the splash screen, configured for
    192000 Hz, 32-bit UNSIGNED, 2 channels, and 65536 byte buffer.
    """
    # *** IMPORTANT: Ensure your Mixcraft WAV file is named 'splash_music.wav' 
    # and is in the same directory as main.py and this file. ***
    static_wav_file = os.path.join(APP_ROOT, 'splash_music.wav')
    
    if not os.path.exists(static_wav_file):
        logger.error(f"Static splash music file not found at {static_wav_file}. Place your Mixcraft output here.")
        return False

    try:
        logger.info(f"Loading static WAV for playback at requested {rate}Hz, {channels} channels.")

        # --- 1. INITIALIZE PYGAME MIXER WITH CUSTOM SETTINGS (32-bit Unsigned) ---
        # We must fully quit the mixer before re-initializing it with custom settings.
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        
        # Initialize mixer: frequency=192000, size=32 (for 32-bit UNSIGNED), channels=2, buffer=65536
        pygame.mixer.init(frequency=192000, size=32, channels=2, buffer=65536) 
        
        # --- 2. LOAD AND PLAY (NON-BLOCKING) ---
        pygame.mixer.music.load(static_wav_file)
        pygame.mixer.music.play()
        logger.info(f"Static playback started: 192000Hz, 2 Channels, 32-bit Unsigned, Buffer 65536.")
        
        # Return the path of the *static* file 
        return static_wav_file
        
    except Exception as e:
        logger.error(f"Static WAV playback failed. Check WAV encoding (must be uncompressed PCM 32-bit unsigned): {e}", exc_info=True)
        return False

# =======================================================================
# === THREADED SOUNDFONT LOADER FUNCTION (remains unchanged) ===
# =======================================================================
def load_soundfont_threaded(sf_path, layer, result_queue):
    app = App.get_running_app()
    if not (app and app.player and app.player.synths):
        result_queue.put(('error', "Player or synths not ready."))
        return

    target_synth_keys = ['melody', 'harmony', 'bass'] if layer == 1 else ['rhythm']
    
    loaded_ids = {}
    try:
        with app.fs_lock:
            for key in target_synth_keys:
                synth = app.player.synths.get(key)
                if synth:
                    sfid = synth.sfload(sf_path)
                    if sfid != -1:
                        loaded_ids[key] = sfid
                    else:
                        logger.warning(f"Failed to load SoundFont into '{key}' synth (sfload returned -1).")
        
        if not loaded_ids:
            raise Exception("SoundFont failed to load into any target synth.")

        sf_name = os.path.basename(sf_path)
        result_data = {'layer': layer, 'sf_name': sf_name, 'new_ids': loaded_ids}
        result_queue.put(('success', result_data))

    except Exception as e:
        logger.error(f"Failed to load SoundFont '{sf_path}' in thread: {e}", exc_info=True)
        result_queue.put(('error', str(e)))


# =======================================================================
# === Screen Classes Begin
# =======================================================================

class SplashScreen(Screen):
    
    # Property to store the path of the dynamically created temporary WAV file
    _current_temp_wav = None 
    # Property to hold the 700-second timer event
    _ten_second_timer = None
    
    def on_enter(self, *args):
        """
        Called when the screen is displayed.
        The simplified audio function is called via a thread.
        """
        self.clear_widgets()
        
        # Use a BoxLayout for clean vertical arrangement of labels and image
        layout = BoxLayout(orientation='vertical', spacing=15, padding=20)
        
        gold = (1, 0.84, 0, 1)
        black = (0, 0, 0, 1)
        
        # --- Add your splash screen content ---
        
        # Main title
        layout.add_widget(Label(text='Fisher-Price MIDI Converter', font_size=78, color=gold,
                                outline_color=black, outline_width=3,
                                size_hint_y=None, height=100))

        # --- Add the Image ---
        image_path = os.path.join(APP_ROOT, 'splash_image.png')
        if os.path.exists(image_path):
            splash_image = Image(source=image_path, size_hint_y=None, height=605,
                                 allow_stretch=True, keep_ratio=True)
            layout.add_widget(splash_image)
        else:
            logger.warning(f"Splash image not found at {image_path}. Skipping image display.")

        # Remaining labels
        layout.add_widget(Label(text='Now With Surround Sound 7.1 , 5.1 and Stereo Support Plus 44100 , 48000 and 192000 Hertz Sample Rates.', font_size=32, color=gold,
                                outline_color=black, outline_width=2,
                                size_hint_y=None, height=60))
       
        layout.add_widget(Label(text='Created Especially For My Fiance Barbara The Most Beautiful Girl In The World.', font_size=54, color=gold,
                                outline_color=black, outline_width=2,
                                size_hint_y=None, height=80))
        layout.add_widget(Label(text='The Wedding Date Has Been Set For Tues July 7 2026 - Rain Dates Tues July 14 2026 and Tues July 21 2026.', font_size=38, color=gold,
                                outline_color=black, outline_width=2,
                                size_hint_y=None, height=75))
        layout.add_widget(Label(text='Written by Russ Campbell, Copyright 2025 - All Rights Reserved.', font_size=50, color=gold,
                                outline_color=black, outline_width=2,
                                size_hint_y=None, height=65))
                                
        self.add_widget(layout)
        
        # --- SCHEDULED TIMER: Ensure a minimum 700-second display time ---
        self._ten_second_timer = Clock.schedule_once(self.change_screen, 10)
        
        # --- START MUSIC IN A SEPARATE THREAD (FIX) ---
        # Parameters fixed to 192000 Hz, 2 channels (32-bit unsigned set inside the function)
        threading.Thread(target=lambda: self.start_custom_playback(rate=192000, channels=2), daemon=True).start()
        
    def start_custom_playback(self, rate=192000, channels=2):
        """
        Wrapper to call the external playback function. Runs in a worker thread.
        """
        # Call the external function which loads and starts playback
        static_wav_file = play_splash_midi_with_settings(rate, channels)
        
        # Safely schedule the music check back on the Kivy main thread
        if static_wav_file:
            self._current_temp_wav = static_wav_file
            # Schedule the check_music_finished to run on the main thread (0 delay)
            Clock.schedule_once(lambda dt: self._start_music_check(), 0)
        else:
            # Playback failed; the 700-second timer handles screen exit
            pass

    def _start_music_check(self):
        """Called safely on the main thread to start the music status check."""
        Clock.schedule_interval(self.check_music_finished, 1)


    def check_music_finished(self, dt):
        """Checks if the music is still playing. If not, change screen."""
        if pygame.mixer.get_init() and not pygame.mixer.music.get_busy():
            logger.info("Song finished.")
            
            # Cancel the safety timer if music finishes early
            if self._ten_second_timer:
                Clock.unschedule(self._ten_second_timer)
            
            self.change_screen()
            return False # Stop the scheduled check
        return True # Keep checking

    def change_screen(self, dt=None):
        """Switches to the 'bands' screen."""
        if self.manager:
            self.manager.current = 'bands'

    def on_leave(self, *args):
        """Stop music and cleanup when leaving the screen."""
        if pygame.mixer.get_init():
             pygame.mixer.music.stop()
             pygame.mixer.quit()
        
        # Cancel all scheduled events
        Clock.unschedule(self.check_music_finished)
        Clock.unschedule(self.change_screen)
        
        # Cancel the safety timer if it was running
        if self._ten_second_timer:
            Clock.unschedule(self._ten_second_timer)

        # The static WAV file is not deleted.
        pass 
# -----------------------------------------------------------------------

class SoundFontSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0
        self._colors = get_contrasting_colors()
        self.soundfont_queue = Queue()
        self.layout = BoxLayout(orientation='vertical', spacing=5, padding=10)
        title = Label(text='Select a SoundFont', font_size=40, size_hint_y=0.15, color=(1, 0.84, 0, 1), outline_color=(0,0,0,1), outline_width=2)
        subtitle = Label(text='For best results, choose a GREEN (General MIDI) SoundFont.', font_size=18, size_hint_y=0.05)
        self.layout.add_widget(title)
        self.layout.add_widget(subtitle)
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.7)
        self.layout.add_widget(self.grid)
        self.layout.add_widget(make_nav([('Prev Page', self.prev_page), ('Next Page', self.next_page), ('Exit', App.get_running_app().stop)]))
        self.add_widget(self.layout)

    def on_enter(self):
        self.page = 0
        soundfont_dir = os.path.join(APP_ROOT, 'soundfonts')
        all_sf2 = sorted([f for f in os.listdir(soundfont_dir) if f.lower().endswith('.sf2')]) if os.path.isdir(soundfont_dir) else []
        gm_soundfonts = [sf for sf in all_sf2 if 'gm' in sf.lower() or 'general' in sf.lower() or os.path.basename(sf).lower() in GM_SOUNDFONTS]
        other_soundfonts = [sf for sf in all_sf2 if sf not in gm_soundfonts]
        self.soundfonts = gm_soundfonts + other_soundfonts
        self.populate_grid()

    def start_soundfont_load(self, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f'Load "{instance.sf_name}" to which layer?'))
        button_box = BoxLayout(spacing=10, size_hint_y=None, height=44)
        
        btn1 = Button(text='Layer 1 (Melody/Custom)')
        btn2 = Button(text='Layer 2 (Rhythm/GM)')
        button_box.add_widget(btn1)
        button_box.add_widget(btn2)
        content.add_widget(button_box)

        popup = Popup(title='Select SoundFont Layer', content=content, size_hint=(0.5, 0.4))
        btn1.bind(on_release=lambda x: self.do_load(instance.sf_name, 1, popup))
        btn2.bind(on_release=lambda x: self.do_load(instance.sf_name, 2, popup))
        popup.open()

    def do_load(self, sf_name, layer, selection_popup):
        selection_popup.dismiss()
        app = App.get_running_app()
        sf_path = os.path.join(APP_ROOT, 'soundfonts', sf_name)
        
        loading_popup = Popup(title='Loading SoundFont...', content=Label(text=f'Loading {sf_name}...'), size_hint=(0.5, 0.4), auto_dismiss=False)
        loading_popup.open()

        # FIX: Ensure load_soundfont_threaded is correctly referenced from the global scope
        threading.Thread(target=load_soundfont_threaded, args=(sf_path, layer, self.soundfont_queue), daemon=True).start()
        
    def check_queue(dt):
            try:
                status, data = self.soundfont_queue.get(block=False)
                
                if status == 'success':
                    layer, sf_name, new_ids_map = data['layer'], data['sf_name'], data['new_ids']
                    logger.info(f"Main thread: Processing successful load of '{sf_name}' to layer {layer} with IDs: {new_ids_map}")
                    
                    target_layer = app.sf_layer1 if layer == 1 else app.sf_layer2
                    
                    with app.fs_lock:
                        # --- FIX: Unload *only* the old SFIDs for the synths that just got new ones. ---
                        for synth_key in new_ids_map.keys():
                            old_sfid = target_layer['ids'].get(synth_key)
                            synth = app.player.synths.get(synth_key)
                            if synth and old_sfid is not None:
                                logger.debug(f"Unloading old SFID {old_sfid} from synth '{synth_key}' for manual load.")
                                synth.sfunload(old_sfid)

                    # --- FIX: Update the layer's state intelligently ---
                    target_layer['name'] = sf_name # Manual load always replaces the name
                    
                    if layer == 1:
                        # Layer 1 is a "full" replacement for melodic parts
                        target_layer['ids'] = new_ids_map # Replaces the whole dict
                    else:
                        # Layer 2 is a "partial" update (e.g., just rhythm),
                        # so we preserve other fallback IDs.
                        target_layer['ids'].update(new_ids_map) # Update, not replace
                else:
                    logger.error(f"Main thread: Received error from loading thread: {data}")

                Clock.unschedule(check_queue)
                loading_popup.dismiss()
                
                if app.return_to_screen:
                    enhancer_screen = self.manager.get_screen(app.return_to_screen)
                    if hasattr(enhancer_screen, 'update_soundfont_labels'):
                        enhancer_screen.update_soundfont_labels()
                    self.manager.current = app.return_to_screen
                    app.return_to_screen = None
                else:
                    self.manager.current = 'bands'
            except Empty: pass
            except Exception as e:
                Clock.unschedule(check_queue)
                loading_popup.dismiss()
                logger.error(f"An error occurred during SoundFont loading: {e}", exc_info=True)
                Popup(title='Loading Error', content=Label(text=f"An error occurred:\n\n{e}"), size_hint=(0.7, 0.5)).open()
                
    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.soundfonts): self.page += 1; self.populate_grid()
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()
            
    def populate_grid(self):
        self.grid.clear_widgets()
        start = self.page * FILES_PER_PAGE
        fonts_on_page = self.soundfonts[start:start + FILES_PER_PAGE]
        for idx, sf_name in enumerate(fonts_on_page):
            is_gm = 'gm' in sf_name.lower() or 'general' in sf_name.lower() or os.path.basename(sf_name).lower() in GM_SOUNDFONTS
            btn_color = (0.2, 0.7, 0.3, 1) if is_gm else self._colors[idx % len(self._colors)]
            btn = Button(text=split_filename(sf_name.replace('.sf2','')), background_color=btn_color, background_normal='', font_size=12, color=(1,1,1,1))
            btn.sf_name = sf_name
            btn.bind(on_release=self.start_soundfont_load)
            self.grid.add_widget(btn)
        for _ in range(len(fonts_on_page), FILES_PER_PAGE):
            self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))

# -----------------------------------------------------------------------

class BandSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0
        self.bands = []
        self.layout = BoxLayout(orientation='vertical')
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint=(1, 0.9))
        self.layout.add_widget(self.grid)
        self.layout.add_widget(make_nav([('Prev Page', self.prev_page), ('Next Page', self.next_page), ('Change SoundFont', lambda *_: setattr(self.manager, 'current', 'soundfont_select')), ('Exit', App.get_running_app().stop)]))
        self.add_widget(self.layout)
    
    def on_enter(self):
        try:
            self.bands = sorted([d for d in os.listdir(MIDI_FOLDER) if os.path.isdir(os.path.join(MIDI_FOLDER, d))])
        except FileNotFoundError:
            self.bands = []
        self.populate_grid()
    
    def populate_grid(self):
        self.grid.clear_widgets()
        start = self.page * FILES_PER_PAGE
        bands_on_page = self.bands[start:start + FILES_PER_PAGE]
        colors = get_contrasting_colors()
        for idx, band_name in enumerate(bands_on_page):
            btn = Button(text=split_filename(band_name), background_color=colors[idx], background_normal='', font_size=12)
            btn.band_name = band_name
            btn.bind(on_release=self.select_band)
            self.grid.add_widget(btn)
        for _ in range(len(bands_on_page), FILES_PER_PAGE):
            self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))
    
    def select_band(self, instance):
        file_screen = self.manager.get_screen('files')
        file_screen.setup_files(os.path.join(MIDI_FOLDER, instance.band_name))
        self.manager.current = 'files'
    
    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.bands): self.page += 1; self.populate_grid()
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()

# -----------------------------------------------------------------------

class FileSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0
        self.band_dir = ''
        self.files = []
        self._colors = get_contrasting_colors()
        self.chunk_queue = Queue()
        self.popup = None
        self.last_selected_path = None
        self.last_detected_bpm = 120
        self.check_chunk_queue_event = None
        root = BoxLayout(orientation='vertical')
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint=(1, 0.9))
        root.add_widget(self.grid)
        nav = [('Back to Bands', lambda *_: setattr(self.manager, 'current', 'bands')),
               ('Prev Page', self.prev_page), 
               ('Next Page', self.next_page),
               ('Enhance a Song', self.go_to_enhancer_selection),
               ('Show Converted', lambda *_: setattr(self.manager, 'current', 'converted_artists')),
               ('Load Enhanced', lambda *_: setattr(self.manager, 'current', 'enhanced_bands')), 
               ('Live Input', lambda *_: setattr(self.manager, 'current', 'live')),
               ('Diagnostics', lambda *_: setattr(self.manager, 'current', 'diagnostic')),
               ('View Chunk Notes', lambda *_: setattr(self.manager, 'current', 'chunk_viewer')),
               ('Exit', App.get_running_app().stop)]
        root.add_widget(make_nav(nav))
        self.add_widget(root)

    def setup_files(self, band_dir):
        self.page = 0; self.band_dir = band_dir
        self.files = sorted([f for f in os.listdir(self.band_dir) if f.lower().endswith(('.mid', '.midi'))])
        self.populate_grid()

    def populate_grid(self):
        self.grid.clear_widgets()
        start = self.page * FILES_PER_PAGE
        page_files = self.files[start:start + FILES_PER_PAGE]
        for idx, fname in enumerate(page_files):
            btn = Button(background_normal='', background_color=self._colors[idx], font_size=12, text=f"{idx + 1}.\n{split_filename(fname.replace('.mid',''))}", halign='center')
            btn.file_path = os.path.join(self.band_dir, fname)
            btn.bind(on_release=self.select_file)
            self.grid.add_widget(btn)
        for _ in range(len(page_files), FILES_PER_PAGE):
            self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))

    def select_file(self, instance):
        original_path = instance.file_path
        try:
            band_name = os.path.basename(self.band_dir).replace(" ", "_")
            original_filename = os.path.basename(original_path).replace(" ", "_")

            transposed_folder = os.path.join(APP_ROOT, 'transposed_midi', band_name)
            os.makedirs(transposed_folder, exist_ok=True)
            transposed_path = os.path.join(transposed_folder, original_filename)
            
            logger.info("--> Running note transposition script...")
            subprocess.run(
                [sys.executable, 'transpose_notes.py', '--input', original_path, '--output', transposed_path],
                check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            input_for_next_step = transposed_path

            cleaned_band_folder = os.path.join(APP_ROOT, 'cleaned_midi', band_name)
            os.makedirs(cleaned_band_folder, exist_ok=True)
            cleaned_path = os.path.join(cleaned_band_folder, original_filename)
            
            logger.info("--> Running drum fixer...")
            subprocess.run(
                [sys.executable, 'check_and_fix_drums.py', '--input', input_for_next_step, '--output', cleaned_path],
                check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            
            logger.info("--> Detecting BPM...")
            result = subprocess.run(
                [sys.executable, 'bpm_detector.py', '--input', cleaned_path],
                capture_output=True, text=True, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            detected_bpm = int(result.stdout.strip())

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"A pre-processing script failed: {e}", exc_info=True)
            Popup(title='Processing Error', content=Label(text=f'A pre-processing script failed:\n{e}'), size_hint=(0.6, 0.4)).open()
            return
            
        self.last_selected_path = cleaned_path
        self.last_detected_bpm = detected_bpm
        # We no longer chunk automatically; we go straight to the enhancer
        enhancement_screen = self.manager.get_screen('enhancer')
        enhancement_screen.set_file(self.last_selected_path, self.last_detected_bpm)
        self.manager.current = 'enhancer'

    def go_to_enhancer_selection(self, instance):
        enhancer_file_select = self.manager.get_screen('enhancer_file_select')
        if self.band_dir:
            enhancer_file_select.setup_files(self.band_dir)
            self.manager.current = 'enhancer_file_select'
        else:
            self.manager.current = 'bands'

    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.files): self.page += 1; self.populate_grid()
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()

class EnhancementScreen(Screen):
    midi_path = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize all properties
        self.original_file_path, self.file_path, self.play_thread = None, None, None
        self.original_bpm, self.added_track_count = 120, 0
        self.stop_event, self.pause_event = threading.Event(), threading.Event()
        self.channel_buttons, self.output_device_map = [], {}
        self.enhancement_settings, self.channel_effect_sliders = {}, {}
        self.temp_midi_folder = os.path.join(APP_ROOT, 'temp_midi')
        os.makedirs(self.temp_midi_folder, exist_ok=True)
        self.soundfont_load_queue = Queue()
        self.chunk_queue = Queue()
        
        # --- Root Layout ---
        root = BoxLayout(orientation='vertical', padding=10, spacing=5)
        gold_color, new_font_size = (1, 0.84, 0, 1), 32

        # --- Top Bar ---
        top_bar = BoxLayout(size_hint_y=0.1, spacing=10)
        self.audio_status_label = Label(text='Audio: -', font_size=new_font_size, color=gold_color, size_hint_x=0.4)
        self.mode_status_label = Label(text='Mode: Internal', font_size=new_font_size, color=gold_color, halign='center', valign='top', size_hint_x=0.2)
        self.bpm_label = Label(text='BPM: -', font_size=new_font_size, color=gold_color, size_hint_x=0.15)
        self.force_xg_button = ToggleButton(text='Use External', size_hint_x=0.25, on_press=self.toggle_mode, font_size=24)
        top_bar.add_widget(self.audio_status_label); top_bar.add_widget(self.mode_status_label)
        top_bar.add_widget(self.bpm_label); top_bar.add_widget(self.force_xg_button)
        root.add_widget(top_bar)

        # --- Title ---
        self.title_label = Label(text='Enhancement Lab', font_size=40, size_hint_y=0.1, color=gold_color, outline_color=(0,0,0,1), outline_width=2, halign='center')
        root.add_widget(self.title_label)

        # --- Main Enhancement Box ---
        self.enhancement_box = BoxLayout(orientation='vertical', padding=5, spacing=10, size_hint_y=0.65) 
        
        # --- Top Controls Grid ---
        controls_grid = GridLayout(cols=4, spacing=15, size_hint_y=0.5)
        
        # Col 1: SoundFonts
        col1 = BoxLayout(orientation='vertical', spacing=10); controls_grid.add_widget(col1)
        col1.add_widget(Label(text='SoundFont Layers', font_size=18, underline=True, size_hint_y=None, height=30))
        self.sf1_label = Label(text="L1: None", font_size=14, size_hint_y=None, height=25, shorten=True, shorten_from='left')
        col1.add_widget(self.sf1_label)
        self.sf2_label = Label(text="L2: None", font_size=14, size_hint_y=None, height=25, shorten=True, shorten_from='left')
        col1.add_widget(self.sf2_label)
        col1.add_widget(Button(text="Find Best", on_release=self.find_best_soundfonts, size_hint_y=None, height=40, font_size=14))
        col1.add_widget(Button(text="Change", on_release=self.change_soundfont_manually, size_hint_y=None, height=40, font_size=14))
        
        # Col 2: Channel Effects (2-Column Layout)
        col2 = BoxLayout(orientation='vertical', spacing=5); controls_grid.add_widget(col2)
        col2.add_widget(Label(text='Channel Effects', font_size=18, underline=True, size_hint_y=None, height=30)) 
        self.channel_effects_spinner = MySpinner(text='1', values=[str(i) for i in range(1, 17)], font_size=16, size_hint_y=None, height=30)
        col2.add_widget(self.channel_effects_spinner)
        effects_grid = GridLayout(cols=2, spacing=8)
        def create_slider(name, cc_num):
            box = BoxLayout(orientation='vertical', height=45, size_hint_y=None)
            box.add_widget(Label(text=name, font_size=12, height=15, size_hint_y=None))
            slider = Slider(min=0, max=127, value=64, step=1); slider.cc_number = cc_num; slider.bind(value=self.send_enhancement_cc)
            box.add_widget(slider); self.channel_effect_sliders[name] = slider
            effects_grid.add_widget(box)
        create_slider('Volume', 7); create_slider('Reverb', 91); create_slider('Chorus', 93)
        create_slider('Cutoff', 74); create_slider('Resonance', 71); create_slider('Release', 72)
        col2.add_widget(effects_grid)

        # Col 3: Humanization & MIDI
        col3 = BoxLayout(orientation='vertical', spacing=10); controls_grid.add_widget(col3)
        col3.add_widget(Label(text='Humanization', font_size=18, underline=True, size_hint_y=None, height=30))
        col3.add_widget(Label(text='Velocity Variation (+/-)', size_hint_y=None, height=20, font_size=14))
        self.velocity_slider = Slider(min=0, max=20, value=0, step=1); col3.add_widget(self.velocity_slider)
        col3.add_widget(Label(text='Main Volume', size_hint_y=None, height=20, font_size=14))
        self.main_volume_slider = Slider(min=0, max=100, value=100, step=1); self.main_volume_slider.bind(value=self.update_main_volume); col3.add_widget(self.main_volume_slider)

        # Col 4: MIDI Output
        col4 = BoxLayout(orientation='vertical', spacing=10); controls_grid.add_widget(col4)
        col4.add_widget(Label(text='MIDI Output', font_size=18, underline=True, size_hint_y=None, height=30))
        self.midi_output_spinner = MySpinner(text='-Not Selected-', values=(), size_hint_y=None, height=44); self.midi_output_spinner.bind(text=self.select_midi_output); col4.add_widget(self.midi_output_spinner)
        col4.add_widget(Button(text="Refresh MIDI Devices", on_release=self.populate_midi_devices, size_hint_y=None, height=44))

        self.enhancement_box.add_widget(controls_grid)
      # --- Channel Mute Grid (Split into two columns) ---
        channel_header = BoxLayout(size_hint_y=None, height=30)
        channel_header.add_widget(Label(text='Channel Instruments (Click to Mute/Add)', font_size=18, underline=True))
        reset_mutes_button = Button(text="Reset Mutes", on_release=self.reset_mutes, font_size=12, size_hint_x=0.2)
        channel_header.add_widget(reset_mutes_button)
        self.enhancement_box.add_widget(channel_header)
        
        master_channel_box = BoxLayout(orientation='horizontal', spacing=20, size_hint_y=0.5, padding=(20, 0))
        
        # --- CHANGED (Change 1): btn_width and grid_width lines removed ---
        
        
        # --- CHANGED (Change 2): 'size_hint_x=None' and 'width=grid_width' removed from both lines below ---
        grid_left = GridLayout(cols=8, rows=1, spacing=5)
        grid_right = GridLayout(cols=8, rows=1, spacing=5)
        
        channel_colors = get_contrasting_colors(16)
        
        for i in range(16):
            
            # --- CHANGED (Change 3): 'size_hint_x=None' and 'width=btn_width' removed from the line below ---
            btn = ToggleButton(text=str(i+1), state='down', font_size=12, halign='center')
            
            btn.channel_index, btn.background_normal, btn.background_color, btn.original_color = i, '', channel_colors[i], channel_colors[i]
            btn.bind(on_press=self.on_channel_button_press)
            self.channel_buttons.append(btn)
            if i < 8: grid_left.add_widget(btn)
            else: grid_right.add_widget(btn)

        master_channel_box.add_widget(grid_left)
        master_channel_box.add_widget(grid_right)
        self.enhancement_box.add_widget(master_channel_box)
        # --- Action Buttons ---
        actions = BoxLayout(size_hint_y=0.1, spacing=10, padding=(0, 5))
        self.play_button = Button(text='Play', on_release=lambda x: self.show_chunking_popup('enhanced'), font_size=20, background_color=(0,0.8,0,1)); actions.add_widget(self.play_button)
        actions.add_widget(Button(text='Save', on_release=self.save_enhanced_midi, font_size=20, background_color=(0.2,0.5,0.8,1)))
        actions.add_widget(Button(text='Pause', on_release=self.toggle_pause))
        actions.add_widget(Button(text='Defaults', on_release=self.apply_intelligent_defaults, background_color=(0.9,0.6,0.1,1)))
        actions.add_widget(Button(text='Original', on_release=lambda x: self.show_chunking_popup('original'), background_color=(0.7,0.7,0.7,1)))
        root.add_widget(actions)

        # Spacer to push content up
        root.add_widget(BoxLayout(size_hint_y=0.05)) 

        # --- Bottom Nav Bar ---
        root.add_widget(make_nav([('Back', self.go_back), ('Instruments', self.view_instruments)]))
        self.add_widget(root)
        self.channel_effects_spinner.bind(text=self.on_enhancement_channel_change)

    # --- CHUNKING AND PLAYBACK LOGIC ---

    def show_chunking_popup(self, playback_type):
        if self.is_playing():
            self.stop_playback()
            return

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Select Playback Mode', font_size=20))
        button_box = BoxLayout(spacing=10, size_hint_y=None, height=50)

        no_chunk_btn = Button(text='No Chunking')
        orig_chunk_btn = Button(text='Original Chunking')
        enh_chunk_btn = Button(text='Enhanced Chunking')

        button_box.add_widget(no_chunk_btn)
        button_box.add_widget(orig_chunk_btn)
        button_box.add_widget(enh_chunk_btn)
        content.add_widget(button_box)

        popup = Popup(title='Playback Options', content=content, size_hint=(0.7, 0.4), auto_dismiss=False)

        no_chunk_btn.bind(on_release=lambda x: self.start_playback('no_chunking', playback_type, popup))
        orig_chunk_btn.bind(on_release=lambda x: self.start_playback('original_chunking', playback_type, popup))
        enh_chunk_btn.bind(on_release=lambda x: self.start_playback('enhanced_chunking', playback_type, popup))

        popup.open()

    def start_playback(self, chunk_mode, playback_type, popup):
        popup.dismiss()
        
        source_file = self.original_file_path if playback_type == 'original' else self.file_path
        if not source_file:
            Popup(title='Error', content=Label(text='No file loaded for playback.')).open()
            return

        # If playback is 'original' or chunk_mode is 'original_chunking', unload custom SFs
        if playback_type == 'original' or chunk_mode == 'original_chunking':
            self._unload_all_soundfonts()

        if chunk_mode == 'no_chunking':
            self._start_unchunked_playback(source_file)
        else:
            self._prepare_and_play_chunks(source_file)

    def _prepare_and_play_chunks(self, source_file_path):
        self.chunk_queue = Queue()
        
        progress_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        progress_label = Label(text='Preparing Chunks...')
        progress_bar = ProgressBar(max=100)
        progress_layout.add_widget(progress_label)
        progress_layout.add_widget(progress_bar)
        chunk_popup = Popup(title='Processing...', content=progress_layout, size_hint=(0.6, 0.4), auto_dismiss=False)
        chunk_popup.open()

        threading.Thread(target=lambda: convert_and_chunk_threaded(source_file_path, self.chunk_queue), daemon=True).start()

        def check_queue(dt):
            try:
                message_type, *data = self.chunk_queue.get(block=False)
                if message_type == 'progress':
                    progress_bar.value, progress_label.text = data[0], data[1]
                elif message_type == 'result':
                    Clock.unschedule(check_queue)
                    chunk_popup.dismiss()
                    chunk_dir = data[0]
                    self._start_chunked_playback(chunk_dir)
                elif message_type == 'error':
                    Clock.unschedule(check_queue)
                    chunk_popup.dismiss()
                    Popup(title='Chunking Error', content=Label(text=f'Failed to create chunks:\n{data[0]}'), size_hint=(0.6, 0.4)).open()
            except Empty:
                pass

        Clock.schedule_interval(check_queue, 0.1)
    
    def _start_unchunked_playback(self, file_path):
        self.stop_event.clear()
        self.pause_event.set()
        self.play_thread = threading.Thread(target=self._play_loop, args=(file_path,), daemon=True)
        self.play_thread.start()
        self.play_button.text, self.play_button.background_color = 'Stop', (1,0,0,1)

    def _start_chunked_playback(self, chunk_dir):
        self.stop_event.clear()
        self.pause_event.set()
        self.play_thread = threading.Thread(target=self._play_chunks_loop, args=(chunk_dir,), daemon=True)
        self.play_thread.start()
        self.play_button.text, self.play_button.background_color = 'Stop', (1,0,0,1)
        
    def _unload_all_soundfonts(self):
        app = App.get_running_app()
        logger.info("Unloading all custom soundfonts for original playback.")
        with app.fs_lock:
            for layer in [app.sf_layer1, app.sf_layer2]:
                for key, sfid in layer['ids'].items():
                    synth = app.player.synths.get(key)
                    if synth and sfid is not None:
                        synth.sfunload(sfid)
                layer['name'] = 'None'
                layer['ids'] = {}
        self.update_soundfont_labels()

    def _play_loop(self, file_path):
        app = App.get_running_app()
        try:
            mid = mido.MidiFile(file_path)
            for ch, settings in self.enhancement_settings.items():
                for k,v in settings.items():
                    cc = {'reverb':91,'chorus':93,'cutoff':74,'resonance':71,'release':72,'volume':7}.get(k)
                    if cc: app.player.send_message(mido.Message('control_change', channel=ch, control=cc, value=v))
            for msg in mid.play():
                if self.stop_event.is_set(): break
                self.pause_event.wait()
                if msg.type == 'control_change' and msg.control == 7: continue
                app.player.send_message(msg)
        except Exception as e: logger.error(f"Playback error: {e}")
        finally: Clock.schedule_once(lambda dt: self._cleanup_playback_resources())

    def _play_chunks_loop(self, chunk_dir):
        app = App.get_running_app()
        try:
            chunk_files = sorted([os.path.join(chunk_dir, f) for f in os.listdir(chunk_dir) if f.endswith('.mid')])
            for chunk_file in chunk_files:
                if self.stop_event.is_set(): break
                mid = mido.MidiFile(chunk_file)
                for msg in mid.play():
                    if self.stop_event.is_set(): break
                    self.pause_event.wait()
                    app.player.send_message(msg)
        except Exception as e:
            logger.error(f"Chunk playback error: {e}")
        finally:
            Clock.schedule_once(lambda dt: self._cleanup_playback_resources())
            shutil.rmtree(chunk_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary chunk directory: {chunk_dir}")
            
    # --- END CHUNKING AND PLAYBACK LOGIC ---

    def _update_audio_status_label(self):
        app = App.get_running_app()
        ch_text = {8: "7.1", 2: "Stereo"}.get(app.audio_channels, f"{app.audio_channels}-Ch")
        rate_text = f"{int(app.audio_rate/1000)}kHz" if app.audio_rate > 0 else "- Hz"
        self.audio_status_label.text = f"{ch_text} | {rate_text}"

    def classify_channels_for_routing(self):
        from main import channel_routing
        if not self.file_path: return
        try:
            mid = mido.MidiFile(self.file_path)
            note_counts, insts = {i:0 for i in range(16)}, {}
            for msg in mido.merge_tracks(mid.tracks):
                if msg.type == 'program_change': insts[msg.channel] = INSTRUMENT_DATABASE.get(msg.program,{})
                elif msg.type == 'note_on' and msg.velocity > 0: note_counts[msg.channel] += 1
            
            temp_route = {i:'rhythm' for i in range(16)}
            bass = {c for c,i in insts.items() if i.get('family') == 'Bass'}
            for c in bass: temp_route[c] = 'bass'
            
            melodic = sorted([(c,n) for c,n in note_counts.items() if c!=9 and c not in bass and n>0], key=lambda x:x[1], reverse=True)
            if melodic:
                temp_route[melodic[0][0]] = 'melody'
                for c,n in melodic[1:]: temp_route[c] = 'harmony'
            channel_routing.update(temp_route)
            logger.info(f"Channel routing map: {channel_routing}")
        except Exception as e: logger.error(f"Failed to classify channels: {e}")

    def find_best_soundfonts(self, instance=None):
        app = App.get_running_app()
        if not app.current_file_path: return
        all_f, drum_f = app.analyze_midi_for_families(), {'Percussive', 'Chromatic Percussion'}
        melodic_f = all_f - drum_f
        
        melodic_sf = app.find_best_font(['non_gm'], melodic_f)
        rhythm_sf = app.find_best_font(['gm'], drum_f) or app.find_best_font(['gm'], {'Percussive'})

        fonts, self.loads_pending = [], 0
        if melodic_sf: fonts.append({'path': os.path.join(APP_ROOT, 'soundfonts', melodic_sf), 'layer': 1})
        if rhythm_sf: fonts.append({'path': os.path.join(APP_ROOT, 'soundfonts', rhythm_sf), 'layer': 2})
        if not fonts: return
        
        popup = Popup(title='Loading', content=Label(text='Loading SoundFonts...'), auto_dismiss=False); popup.open()
        self.loads_pending = len(fonts)
        
        # --- FIX: Loop over a copy of fonts or just start threads directly ---
        for f in fonts: threading.Thread(target=load_soundfont_threaded, args=(f['path'],f['layer'],self.soundfont_load_queue),daemon=True).start()
    def check_loads(dt):
            try:
                status, data = self.soundfont_load_queue.get_nowait()
                self.loads_pending -= 1
                if status == 'success':
                    layer, name, new_ids_map = data['layer'], data['sf_name'], data['new_ids']
                    logger.info(f"Main thread: Processing success for '{name}' on layer {layer} with new IDs: {new_ids_map}")
                    
                    target_layer = app.sf_layer1 if layer == 1 else app.sf_layer2

                    with app.fs_lock:
                        # --- FIX: Unload *only* the old SFIDs for the synths that just got new ones. ---
                        for synth_key in new_ids_map.keys():
                            old_sfid = target_layer['ids'].get(synth_key)
                            synth = app.player.synths.get(synth_key)
                            if synth and old_sfid is not None:
                                logger.debug(f"Unloading old SFID {old_sfid} from synth '{synth_key}' for best-font load.")
                                synth.sfunload(old_sfid)
                    
                    # --- FIX: Update the layer's state intelligently ---
                    if layer == 1:
                        # Layer 1 is a "full" replacement for melodic parts
                        target_layer['name'] = name
                        target_layer['ids'] = new_ids_map # Replaces the whole dict
                    else:
                        # Layer 2 is a "partial" update (e.g., just rhythm),
                        # so we preserve other fallback IDs.
                        target_layer['name'] = name # Update the name to the new font
                        target_layer['ids'].update(new_ids_map) # Update, not replace
                
                if self.loads_pending <= 0:
                    Clock.unschedule(check_loads); popup.dismiss(); self.update_soundfont_labels()
            except Empty: pass
    def update_soundfont_labels(self):
        app = App.get_running_app()
        self.sf1_label.text = f"L1: {app.sf_layer1['name']}"
        self.sf2_label.text = f"L2: {app.sf_layer2['name']}"

    def on_enter(self, *args):
        self._update_audio_status_label(); self.update_soundfont_labels()
        self.populate_midi_devices(); self._update_mode_ui()

    def change_soundfont_manually(self, i): 
        app = App.get_running_app()
        app.return_to_screen = self.name
        self.manager.current = 'soundfont_select'
    def set_file(self, file_path, bpm=120):
        """
        Main entry point for loading a file into the enhancer.
        This now stores original paths and then calls the check/split logic.
        """
        # Store the *original* paths and BPM regardless of splitting
        self.original_file_path = file_path
        self.original_bpm = bpm
        
        # Set band/song names from the original file path
        try:
            band_dir = os.path.dirname(os.path.dirname(self.original_file_path)) 
            self.original_band_name = os.path.basename(band_dir).replace('_',' ')
            self.original_song_name = os.path.splitext(os.path.basename(file_path))[0].replace('_',' ')
        except Exception as e:
            logger.error(f"Could not parse band/song name: {e}")
            self.original_band_name = "Unknown Band"
            self.original_song_name = "Unknown Song"

        # Now, check if we need to split the file
        self._check_and_offer_split(file_path, bpm)

    def _check_and_offer_split(self, file_path, bpm):
        """
        Checks if the file is Type 0 multi-instrument and shows a popup if it is.
        """
        try:
            mid = mido.MidiFile(file_path)
            is_type_0_multi = False
            
            # Check if it's one track
            if len(mid.tracks) == 1:
                # Check if that one track has multiple instruments
                channels_with_programs = set()
                for msg in mid.tracks[0]:
                    if msg.type == 'program_change':
                        channels_with_programs.add(msg.channel)
                
                if len(channels_with_programs) > 1:
                    is_type_0_multi = True
            
            # If it's a normal file (Type 1 or Type 0 single-instrument), load directly
            if not is_type_0_multi:
                self._finish_loading_file(file_path, bpm)
                return

            # --- It IS a Type 0 Multi-Instrument File ---
            # Show the popup as requested
            content = BoxLayout(orientation='vertical', padding=10, spacing=10)
            content.add_widget(Label(
                text='[b]Warning: Single-Track MIDI[/b]\n\n'
                     'This file has all instruments on a single track (Type 0).\n'
                     'Splitting it into multiple tracks (Type 1) is highly recommended.',
                markup=True, halign='center', font_size=18
            ))
            button_box = BoxLayout(spacing=10, size_hint_y=None, height=50)
            
            split_btn = Button(text='Split into Multi-Track File', background_color=(0,0.8,0,1), font_size=16)
            load_as_is_btn = Button(text='Load As-Is (Not Recommended)', font_size=16)
            
            button_box.add_widget(split_btn)
            button_box.add_widget(load_as_is_btn)
            content.add_widget(button_box)

            popup = Popup(title='File Type Detected', content=content, size_hint=(0.6, 0.5), auto_dismiss=False)
            
            def on_split(instance):
                popup.dismiss()
                try:
                    # Run the splitting function
                    new_path = self._split_midi_file(file_path)
                    # Load the NEW, split file
                    self._finish_loading_file(new_path, bpm) 
                except Exception as e:
                    logger.error(f"Failed to split MIDI file: {e}", exc_info=True)
                    Popup(title='Split Error', content=Label(text=f'Could not split file:\n{e}'), size_hint=(0.5, 0.4)).open()
                    # Fallback: load the original file
                    self._finish_loading_file(file_path, bpm)

            def on_load_as_is(instance):
                popup.dismiss()
                # Load the ORIGINAL file
                self._finish_loading_file(file_path, bpm)

            split_btn.bind(on_release=on_split)
            load_as_is_btn.bind(on_release=on_load_as_is)
            popup.open()
        
        except Exception as e:
            logger.error(f"Error checking MIDI file type: {e}", exc_info=True)
            # Fallback on any error, just load the file
            self._finish_loading_file(file_path, bpm)

    def _split_midi_file(self, file_path):
        """
        Uses music21 to convert a Type 0 file to a Type 1 file.
        """
        logger.info(f"Splitting Type 0 MIDI file: {file_path}")
        
        # 1. Read the Type 0 file using mido
        mid_mido = mido.MidiFile(file_path)
        
        # 2. Convert mido object to music21 stream
        score = midi_translate.midiFileToStream(mid_mido)
        
        # 3. Write the stream back out. music21 defaults to Type 1 (multi-track).
        temp_dir = self.temp_midi_folder # Uses existing temp folder
        temp_filename = f"split_{os.path.basename(file_path)}"
        new_file_path = os.path.join(temp_dir, temp_filename)
        
        midi_file_obj = midi_translate.streamToMidiFile(score)
        midi_file_obj.open(new_file_path, 'wb')
        midi_file_obj.write()
        midi_file_obj.close()
        
        logger.info(f"Successfully split file and saved to: {new_file_path}")
        return new_file_path

    def _finish_loading_file(self, file_path, bpm):
        """
        This method contains all the logic that *used* to be in set_file.
        It's now called *after* the split-check is complete.
        """
        self.file_path = file_path  # This is the file to load (original or split)
        app = App.get_running_app()
        if self.is_playing(): self.stop_playback()
        
        app.current_file_path = self.file_path
        self.midi_path = file_path
        
        # Check if we are loading a temp file
        if 'temp_midi' not in self.file_path:
             # Only reset added_track_count if it's a freshly loaded file
             self.added_track_count = 0
             
        self.bpm_label.text = f"BPM: {bpm}"
        
        # Title label always uses the original, un-split name
        self.title_label.text = f"{self.original_band_name}\n{self.original_song_name}"
        
        # Run all the setup and analysis functions
        self.apply_intelligent_defaults()
        self.update_soundfont_labels()
        self.reset_mutes()
        insts = self.get_channel_instruments(file_path)
        for btn in self.channel_buttons:
            btn.text = f"{btn.channel_index+1}\n{textwrap.fill(insts.get(btn.channel_index, 'Empty'), 12)}"
        
        self.on_enhancement_channel_change(self.channel_effects_spinner, self.channel_effects_spinner.text)
        self.classify_channels_for_routing()
        self.find_best_soundfonts()
    def apply_intelligent_defaults(self, instance=None):
        self.enhancement_settings = self.analyze_midi_for_gm_settings(self.file_path)
        self.velocity_slider.value = 8
        self.on_enhancement_channel_change(self.channel_effects_spinner, self.channel_effects_spinner.text)

    def analyze_midi_for_gm_settings(self, file_path):
        settings = {i:{'reverb':40,'chorus':0,'cutoff':64,'resonance':64,'release':64,'volume':100} for i in range(16)}
        try:
            insts = self.get_channel_instruments(file_path)
            for ch, name in insts.items():
                prog = next((p for p,i in INSTRUMENT_DATABASE.items() if i['name']==name), None)
                if prog is None: continue
                fam = INSTRUMENT_DATABASE[prog].get('family','Other')
                if fam in ['Strings','Synth Pad','Ensemble']: settings[ch].update({'reverb':75,'chorus':40})
                elif fam == 'Piano': settings[ch].update({'reverb':60,'chorus':20})
                elif fam == 'Bass': settings[ch].update({'reverb':20,'chorus':5,'volume':120})
                if ch==9: settings[ch].update({'reverb':25,'chorus':0})
        except Exception as e: logger.error(f"Could not get instrument data: {e}")
        return settings

    def _update_mode_ui(self):
        app=App.get_running_app()
        self.mode_status_label.text = 'Mode: External' if app.external_midi_enabled else 'Mode: Internal'
        self.force_xg_button.state = 'down' if app.external_midi_enabled else 'normal'
    
    def toggle_mode(self, instance):
        app=App.get_running_app()
        output_name = app.selected_midi_output_name if instance.state == 'down' else None
        if instance.state == 'down' and not output_name:
            Popup(title='No MIDI Output', content=Label(text='Please select a MIDI Output Device first.')).open()
            instance.state = 'normal'; return
        app.player.set_output_device(output_name); self._update_mode_ui()

    def select_midi_output(self, spinner, text):
        app=App.get_running_app()
        app.selected_midi_output_name = self.output_device_map.get(text) if text!="-Not Selected-" else None
        app.save_midi_settings()
        if self.force_xg_button.state == 'down': app.player.set_output_device(app.selected_midi_output_name)
        self._update_mode_ui()

    def intelligently_add_track(self, empty_channel_index):
        if not self.file_path: return
        try:
            mid = mido.MidiFile(self.file_path)
            tracks_info, existing_programs = [], set()
            for i, track in enumerate(mid.tracks):
                note_count, program, channel = 0, None, None
                for msg in track:
                    if hasattr(msg, 'channel'): channel = msg.channel
                    if msg.type == 'program_change': program, existing_programs = msg.program, existing_programs | {msg.program}
                    if msg.type == 'note_on' and msg.velocity > 0: note_count += 1
                if all(x is not None for x in [program, channel]) and note_count > 10:
                    family = INSTRUMENT_DATABASE.get(program, {}).get('family')
                    tracks_info.append({'channel': channel, 'family': family, 'note_count': note_count, 'track_obj': track})

            source_track_info = max([t for t in tracks_info if t['family'] not in ['Bass', 'Percussive']], key=lambda x: x['note_count'], default=None)
            if not source_track_info: source_track_info = max(tracks_info, key=lambda x: x['note_count'], default=None)
            if not source_track_info:
                Popup(title='Cannot Add Track', content=Label(text='No suitable source track to build from.')).open(); return

            self.added_track_count += 1
            new_track = mido.MidiTrack(source_track_info['track_obj'])
            harmony_pool = [p for p in [48,49,50,52,53,88,89,90] if p not in existing_programs]
            new_instrument_program = random.choice(harmony_pool) if harmony_pool else 88
            has_program_change = False
            for msg in new_track:
                if hasattr(msg, 'channel'): msg.channel = empty_channel_index
                if msg.type == 'program_change': msg.program, has_program_change = new_instrument_program, True
                if msg.type == 'note_on': msg.velocity = int(msg.velocity * 0.65)
            if not has_program_change: new_track.insert(0, mido.Message('program_change', channel=empty_channel_index, program=new_instrument_program, time=0))
            mid.tracks.append(new_track)
            temp_filepath = os.path.join(self.temp_midi_folder, os.path.basename(self.file_path).replace('.mid', f'_v{self.added_track_count}.mid'))
            mid.save(temp_filepath)
            self.set_file(temp_filepath, self.original_bpm)
        except Exception as e:
            logger.error(f"Failed to intelligently add track: {e}", exc_info=True)
            Popup(title='Error', content=Label(text=f'Could not generate new track:\n{e}')).open()

    def on_channel_button_press(self, instance):
        channel_index = instance.channel_index
        if "Empty" in instance.text:
            instance.state = 'down'
            content = BoxLayout(orientation='vertical', padding=10, spacing=10)
            content.add_widget(Label(text='Intelligently add a new instrument to this empty channel?'))
            button_box = BoxLayout(spacing=10, size_hint_y=None, height=44)
            yes_btn, no_btn = Button(text='Yes, Add Part'), Button(text='Cancel')
            button_box.add_widget(yes_btn); button_box.add_widget(no_btn)
            content.add_widget(button_box)
            popup = Popup(title='Add New Track', content=content, size_hint=(0.5, 0.4))
            def add_track_action(button_instance):
                popup.dismiss(); self.intelligently_add_track(channel_index)
            yes_btn.bind(on_release=add_track_action); no_btn.bind(on_release=popup.dismiss)
            popup.open()
        else:
            app = App.get_running_app()
            is_muted = instance.state == 'normal'
            vol = 0 if is_muted else self.enhancement_settings.get(channel_index, {}).get('volume', 100)
            app.player.send_message(mido.Message('control_change', channel=channel_index, control=7, value=vol))
            instance.background_color = (0.2,0.2,0.2,1) if is_muted else instance.original_color

    def save_enhanced_midi(self, instance):
        if not self.file_path: return
        try:
            output_dir = os.path.join(ENHANCED_FOLDER, self.original_band_name, self.original_song_name)
            os.makedirs(output_dir, exist_ok=True)
            mid = mido.MidiFile(self.file_path)
            for track in mid.tracks:
                track_ch = next((msg.channel for msg in track if hasattr(msg, 'channel')), None)
                if track_ch and track_ch in self.enhancement_settings:
                    settings = self.enhancement_settings[track_ch]
                    cc_map = {'reverb':91,'chorus':93,'cutoff':74,'resonance':71,'release':72,'volume':7}
                    for k,v in settings.items():
                        if k in cc_map: track.insert(0, mido.Message('control_change', channel=track_ch, control=cc_map[k], value=v, time=0))
            app = App.get_running_app()
            mode = "xg" if app.external_midi_enabled else "gm"
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.original_song_name}_{mode}_{ts}.mid"
            mid.save(os.path.join(output_dir, filename))
            Popup(title='Success!', content=Label(text=f'Saved to:\n{output_dir}')).open()
        except Exception as e: logger.error(f"Failed to save MIDI: {e}", exc_info=True)

    def on_enhancement_channel_change(self, s, text):
        ch = int(text)-1; settings = self.enhancement_settings.get(ch,{})
        for name, slider in self.channel_effect_sliders.items():
            key = name.lower().replace(' send','').replace('filter ','').replace(' time','')
            slider.value = settings.get(key, 64)
        self.channel_effect_sliders['Volume'].value = settings.get('volume', 100)

    def send_enhancement_cc(self, slider, value):
        app=App.get_running_app()
        try:
            ch = int(self.channel_effects_spinner.text)-1
            settings = self.enhancement_settings.setdefault(ch,{})
            key = next(k for k,v in self.channel_effect_sliders.items() if v==slider).lower().replace(' send','').replace('filter ','').replace(' time','')
            settings[key] = int(value)
            app.player.send_message(mido.Message('control_change', channel=ch, control=slider.cc_number, value=int(value)))
        except Exception as e: logger.error(f"Error sending CC: {e}")

    def get_channel_instruments(self, file_path):
        insts = {}
        if not(file_path and os.path.exists(file_path)): return insts
        try:
            for msg in mido.merge_tracks(mido.MidiFile(file_path).tracks):
                if msg.type == 'program_change':
                    insts[msg.channel] = INSTRUMENT_DATABASE.get(msg.program,{}).get('name',f"Unknown {msg.program}")
        except Exception as e: logger.error(f"Failed to analyze MIDI: {e}")
        return insts

    def is_playing(self): return self.play_thread and self.play_thread.is_alive()

    def populate_midi_devices(self, i=None):
        app=App.get_running_app()
        self.output_device_map = {name:name for name in mido.get_output_names()}
        self.midi_output_spinner.values = sorted(self.output_device_map.keys())
        self.midi_output_spinner.text = app.selected_midi_output_name or "-Not Selected-"

    def update_main_volume(self, instance, value):
        app = App.get_running_app()
        app.current_gain = float(value) / 50.0
        if not app.external_midi_enabled:
            with app.fs_lock:
                for s in app.player.synths.values():
                    if s: s.gain = app.current_gain

    def _cleanup_playback_resources(self):
        self._all_notes_off(); self.play_thread = None
        if hasattr(self, 'play_button'): self.play_button.text,self.play_button.background_color = 'Play',(0,0.8,0,1)

    def stop_playback(self, i=None):
        if self.is_playing(): self.stop_event.set(); self.pause_event.set(); self.play_thread.join(0.5)
        self._cleanup_playback_resources()

    def reset_mutes(self, i=None):
        for btn in self.channel_buttons:
            if "Empty" not in btn.text: btn.state='down'; self.on_channel_button_press(btn)

    def _all_notes_off(self):
        app = App.get_running_app()
        if app and app.player:
            for ch in range(16):
                app.player.send_message(mido.Message('control_change',channel=ch,control=123,value=0))
            time.sleep(0.05)

    def view_instruments(self, i): self.manager.current = 'instrument_list'
    def go_back(self, i): self.stop_playback(); self.manager.current = 'files'

    def toggle_pause(self, i):
        if self.is_playing():
            if self.pause_event.is_set(): self.pause_event.clear()
            else: self.pause_event.set()
            
# -----------------------------------------------------------------------

class ChunkViewerScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        header = BoxLayout(size_hint_y=0.15, spacing=20)
        header.add_widget(Label(text="Chunk Note Viewer", font_size=32, color=(1, 0.84, 0, 1)))
        header.add_widget(Button(text="Select Chunk File to Analyze", on_release=self.open_file_chooser, size_hint_x=0.4))
        self.layout.add_widget(header)
        self.selected_file_label = Label(text="No file selected.", size_hint_y=0.1, font_size=18)
        self.layout.add_widget(self.selected_file_label)
        scroll = ScrollView(size_hint_y=0.6)
        self.notes_label = Label(text="Note numbers from the selected chunk will appear here.", font_size=24, size_hint_y=None, halign='center', valign='top')
        self.notes_label.bind(width=lambda *x: self.notes_label.setter('text_size')(self.notes_label, (self.notes_label.width - 20, None)))
        self.notes_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        scroll.add_widget(self.notes_label)
        self.layout.add_widget(scroll)
        self.layout.add_widget(make_nav([('Back to Main Menu', lambda *x: setattr(self.manager, 'current', 'files'))]))
        self.add_widget(self.layout)

    def open_file_chooser(self, instance):
        chooser = FileChooserListView(path=CONVERTED_FOLDER, filters=['*.mid', '*.midi'])
        box = BoxLayout(orientation='vertical')
        box.add_widget(chooser)
        btn_box = BoxLayout(size_hint_y=0.1, spacing=10)
        btn_load, btn_cancel = Button(text="Load File"), Button(text="Cancel")
        btn_box.add_widget(btn_load); btn_box.add_widget(btn_cancel)
        box.add_widget(btn_box)
        popup = Popup(title="Select a Chunk File", content=box, size_hint=(0.9, 0.9))
        btn_load.bind(on_release=lambda x: self.load_chunk_notes(chooser.selection, popup))
        btn_cancel.bind(on_release=popup.dismiss)
        popup.open()

    def load_chunk_notes(self, selection, popup):
        popup.dismiss()
        if not selection: return
        file_path = selection[0]
        self.selected_file_label.text = f"Analyzing: {os.path.basename(file_path)}"
        try:
            mid = mido.MidiFile(file_path)
            notes = sorted(list({msg.note for msg in mid if msg.type == 'note_on' and msg.velocity > 0}))
            self.notes_label.text = textwrap.fill(' '.join(map(str, notes)), 80) if notes else "No notes found."
        except Exception as e:
            self.notes_label.text = f"Error reading file: {e}"; logger.error(f"Error reading chunk file: {e}")

# -----------------------------------------------------------------------

class EnhancerFileSelectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = 0; self.band_dir = ''; self.files = []
        self._colors = get_contrasting_colors()
        root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text="Select a Song to Enhance", font_size=24, size_hint_y=0.1))
        self.grid = GridLayout(cols=7, rows=7, spacing=2, padding=2, size_hint_y=0.8); root.add_widget(self.grid)
        nav = [('Back to Main Browser', lambda *_: setattr(self.manager, 'current', 'files')), ('Prev Page', self.prev_page), ('Next Page', self.next_page)]
        root.add_widget(make_nav(nav)); self.add_widget(root)

    def setup_files(self, band_dir):
        self.page = 0; self.band_dir = band_dir
        self.files = sorted([f for f in os.listdir(band_dir) if f.lower().endswith(('.mid', '.midi'))])
        self.populate_grid()

    def populate_grid(self):
        self.grid.clear_widgets()
        start, page_items = self.page * FILES_PER_PAGE, self.files[self.page*FILES_PER_PAGE:(self.page+1)*FILES_PER_PAGE]
        for idx, fname in enumerate(page_items):
            btn = Button(background_normal='', background_color=self._colors[idx], font_size=12, text=f"Enhance\n{split_filename(fname.replace('.mid',''))}", halign='center')
            btn.file_path = os.path.join(self.band_dir, fname)
            btn.bind(on_release=self.select_file_for_enhancement)
            self.grid.add_widget(btn)
        for _ in range(len(page_items), FILES_PER_PAGE): self.grid.add_widget(Button(disabled=True, background_color=(0,0,0,0)))

    def select_file_for_enhancement(self, instance):
        # This now calls the same pre-processing as the main file selection
        file_screen = self.manager.get_screen('files')
        file_screen.select_file(instance)

    def next_page(self, *_):
        if (self.page + 1) * FILES_PER_PAGE < len(self.files): self.page += 1; self.populate_grid()
    def prev_page(self, *_):
        if self.page > 0: self.page -= 1; self.populate_grid()        

# -----------------------------------------------------------------------

FISHER_PRICE_NOTES = range(55, 77)
MIDI_NOTE_NAMES = {55:'G3',56:'G#3',57:'A3',58:'A#3',59:'B3',60:'C4',61:'C#4',62:'D4',63:'D#4',64:'E4',65:'F4',66:'F#4',67:'G4',68:'G#4',69:'A4',70:'A#4',71:'B4',72:'C5',73:'C#5',74:'D5',75:'D#5',76:'E5'}

class LiveInputScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input_port, self.base_midi_note = None, None
        self.is_recording, self.recorded_events, self.translate_notes = False, [], True
        layout = BoxLayout(orientation='vertical', spacing=5, padding=5)
        self.info_label = Label(text="Translate Mode ON. Press LOWEST key to map.", size_hint_y=0.15, font_size=20)
        layout.add_widget(self.info_label)
        grid = GridLayout(cols=11, size_hint_y=0.7, spacing=3)
        for note in sorted(list(FISHER_PRICE_NOTES)):
            name = MIDI_NOTE_NAMES.get(note, str(note))
            is_black = '#' in name
            btn = Button(text=name, font_size=18, color=(1,1,1,1) if is_black else (0,0,0,1), background_normal='', background_color=(0.2,0.2,0.2,1) if is_black else (0.9,0.9,0.9,1), outline_color=(0,0,0,1), outline_width=2)
            btn.bind(on_press=lambda i, n=note: self.play_note(n)); grid.add_widget(btn)
        layout.add_widget(grid)
        self.record_button = Button(text="Record")
        self.mode_toggle_button = ToggleButton(text="Translate: ON", state='down', size_hint_x=0.5)
        self.record_button.bind(on_press=self.toggle_record)
        self.mode_toggle_button.bind(on_press=self.toggle_translation_mode)
        nav_buttons = [('Reset Map', self.reset_mapping), ('Save', self.save_recording), ('Play Last', self.play_recording), ('Back', self.go_back)]
        nav_bar = make_nav(nav_buttons)
        nav_bar.add_widget(self.mode_toggle_button, index=len(nav_bar.children)); nav_bar.add_widget(self.record_button, index=len(nav_bar.children))
        layout.add_widget(nav_bar); self.add_widget(layout)
    
    def toggle_translation_mode(self, instance):
        self.translate_notes = instance.state == 'down'
        instance.text = "Translate: ON" if self.translate_notes else "Translate: OFF"
        self.reset_mapping(None)

    def reset_mapping(self, instance):
        self.base_midi_note = None
        self.info_label.text = "Translate ON: Press LOWEST key." if self.translate_notes else "Full Keyboard Mode: All notes recorded as played."

    def midi_callback(self, msg):
        app = App.get_running_app()
        if not self.translate_notes:
            app.player.send_message(msg)
            if self.is_recording and msg.type=='note_on':
                if not hasattr(self, 'start_time'): self.start_time = time.time()
                self.recorded_events.append((time.time()-self.start_time, msg))
            return
        if msg.type not in ('note_on','note_off'): app.player.send_message(msg); return
        if self.base_midi_note is None and msg.type=='note_on' and msg.velocity>0:
            self.base_midi_note = msg.note
            self.info_label.text = f"Map Set! Start: {self.base_midi_note}. Next 21 keys active."
        if self.base_midi_note is None: return
        offset = msg.note - self.base_midi_note
        if not(0<=offset<22): return
        trans_msg = msg.copy(note=55+offset); app.player.send_message(trans_msg)
        if self.is_recording:
            if not hasattr(self, 'start_time'): self.start_time = time.time()
            self.recorded_events.append((time.time()-self.start_time, trans_msg))

    def play_note(self, note, v=100, d=0.4):
        app=App.get_running_app(); msg_on=mido.Message('note_on',note=note,velocity=v)
        app.player.send_message(msg_on); msg_off=mido.Message('note_off',note=note,velocity=0)
        Clock.schedule_once(lambda dt: app.player.send_message(msg_off), d)

    def on_enter(self): self.reset_mapping(None); self.setup_midi_input()
    def setup_midi_input(self):
        if self.input_port: self.input_port.close()
        try:
            self.input_port = mido.open_input(callback=self.midi_callback)
            logger.info(f"Opened MIDI input: {self.input_port.name}")
        except Exception as e:
            logger.error(f"Could not open MIDI input: {e}")
            self.info_label.text = "No physical MIDI keyboard detected."
    def toggle_record(self, instance):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.recorded_events, self.start_time = [], time.time()
            self.record_button.text, self.record_button.background_color = "Stop", (1,0,0,1)
        else: self.record_button.text, self.record_button.background_color = "Record", (1,1,1,1)
    def save_recording(self, *_):
        if self.is_recording or not self.recorded_events: return
        mid=mido.MidiFile(); track=mido.MidiTrack(); last_time=0
        for event_time, msg in self.recorded_events:
            delta = event_time - last_time
            track.append(msg.copy(time=int(mido.second2tick(delta, mid.ticks_per_beat, 500000))))
            last_time = event_time
        mid.tracks.append(track)
        out_path = os.path.join(LIVE_FOLDER, f'Live_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mid')
        mid.save(out_path); Popup(title='Saved', content=Label(text=f'Saved:\n{out_path}'), size_hint=(0.6,0.4)).open()

    def play_recording(self, *_):
        files = sorted([os.path.join(LIVE_FOLDER,f) for f in os.listdir(LIVE_FOLDER) if f.endswith('.mid')], key=os.path.getmtime, reverse=True)
        if files:
            # The 'player' screen is not in this file, so we can't call it directly
            # This is a placeholder for how it would work.
            # self.manager.get_screen('player').play_midi(files[0], "Live Recordings", "Last Recording", self.name)
            self.manager.current = 'player'
    def go_back(self, instance): self.on_leave(); self.manager.current = 'files'
    def on_leave(self, *args):
        if self.input_port: self.input_port.close(); self.input_port=None

class InstrumentListScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        title = Label(text='Instrument & SoundFont Checklist', font_size=32, color=(1,0.84,0,1), outline_color=(0,0,0,1), outline_width=2, size_hint_y=0.15)
        self.layout.add_widget(title)
        scroll = ScrollView(size_hint_y=0.75)
        self.grid = GridLayout(cols=1, spacing=15, size_hint_y=None, padding=10)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        scroll.add_widget(self.grid); self.layout.add_widget(scroll)
        self.layout.add_widget(Button(text='Back to Enhancer', size_hint_y=0.1, on_release=self.go_back))
        self.add_widget(self.layout)

    def on_enter(self, *args):
        self.grid.clear_widgets(); app = App.get_running_app()
        if not(app.current_file_path and hasattr(app, 'soundfont_index') and app.soundfont_index):
            self.grid.add_widget(Label(text='Load a song and ensure soundfont_index.json exists.'))
            return
        sf1_f = set(app.soundfont_index.get('non_gm',{}).get(app.sf_layer1['name'],{}).keys())
        sf2_f = set(app.soundfont_index.get('gm',{}).get(app.sf_layer2['name'],{}).keys())
        header = f"[b]L1:[/b] {app.sf_layer1['name']}\n[b]L2:[/b] {app.sf_layer2['name']}"
        self.grid.add_widget(Label(text=header, markup=True, size_hint_y=None, height=70, font_size=16))
        try:
            from main import channel_routing
            mid = mido.MidiFile(app.current_file_path)
            insts = sorted([(msg.program, msg.channel) for msg in mido.merge_tracks(mid.tracks) if msg.type=='program_change'], key=lambda x:x[1])
            for prog, ch in insts:
                info = INSTRUMENT_DATABASE.get(prog, {'name':f'Unknown {prog}', 'family':'Unknown'})
                fam, is_rhythm = info['family'], channel_routing.get(ch)=='rhythm'
                fams, name = (sf2_f, app.sf_layer2['name']) if is_rhythm else (sf1_f, app.sf_layer1['name'])
                status = "[color=33FF33]MATCH[/color]" if fam in fams else "[color=FF3333]MISMATCH[/color]"
                text = f"[b]Ch {ch+1}:[/b] {info['name']} (Family: {fam})\n[size=14]Handled by '{name}': {status}[/size]"
                self.grid.add_widget(Label(text=text, markup=True, size_hint_y=None, height=60))
        except Exception as e: logger.error(f"Error displaying instrument list: {e}")
    def go_back(self, instance): self.manager.current = 'enhancer'