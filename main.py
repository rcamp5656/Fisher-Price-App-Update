#!/usr/bin/env python3
"""
main.py
Main application entry point for the Fisher Price Player.
This file initializes Kivy, Pygame, the audio engine, and the FluidSynth player.
It contains the main App class which manages global state and screen transitions.
"""

import os

# --- FIX 1: FORCE ANGLE BACKEND (Prevents Black Screen on Windows) ---
# This must run before any Kivy imports
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'

# --- Kivy Configuration (must be set before other imports) ---
from kivy.config import Config
# FIX: Disable auto fullscreen to prevent black screen issues on Windows
Config.set('graphics', 'fullscreen', '0') 
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'width', '1280') # Start smaller to ensure visibility
Config.set('graphics', 'height', '720')

# --- Standard Library Imports ---
import sys
import threading
import logging
import time
import json
import warnings
import random
from queue import Empty, Queue

# --- Third-Party Imports ---
import pygame
import pygame.midi
import mido
import fluidsynth
import numpy as np
import pyaudio
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView
from music21.midi import translate as midi_translate

# --- Local Module Imports ---
from constants import APP_ROOT, MIDI_SETTINGS_FILE, GM_FALLBACK_FONT, INSTRUMENT_DATABASE
from audio_processing import AudioProcessor
from ui.widgets import make_nav 
from ui.screens_main import (
    SplashScreen, SoundFontSelectScreen, BandSelectScreen, FileSelectScreen,
    EnhancementScreen, EnhancerFileSelectScreen, InstrumentListScreen, LiveInputScreen,
    ChunkViewerScreen
)
from ui.screens_playback import (
    EnhancedBandSelectScreen, EnhancedSongSelectScreen, EnhancedVersionSelectScreen,
    ConvertedArtistSelectScreen, ConvertedSongSelectScreen, ChunkSelectScreen,
    FisherPriceDisplayScreen
)

# --- Suppress music21 TranslateWarning ---
warnings.filterwarnings("ignore", category=midi_translate.TranslateWarning)

# --- Logging Setup ---
log_path = os.path.join(APP_ROOT, 'log.txt')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    try:
        fh = logging.FileHandler(log_path, mode='w')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)
    except Exception as e:
        print(f"FATAL ERROR: Could not initialize file logger: {e}")
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(ch)
        logger.error("Failed to set up file logging. Using console only.")
logger.info("Application starting...")

# --- Audio and Multi-Synth Initialization ---
pygame.init()
pygame.midi.init()
fs_lock = threading.Lock()

# Define synth keys for consistency
SYNTH_KEYS = ['melody', 'bass', 'harmony', 'rhythm']
synths = {key: None for key in SYNTH_KEYS}

p, audio_stream, audio_processor = None, None, None
channel_routing = {i: 'rhythm' for i in range(16)} 
output_channels = 0
final_rate = 0

def create_synth(rate, gain):
    try:
        return fluidsynth.Synth(samplerate=rate, gain=gain)
    except Exception as e:
        logger.error(f"Failed to create a FluidSynth instance: {e}")
        return None

try:
    p = pyaudio.PyAudio()

    def audio_callback(in_data, frame_count, time_info, status):
        app = App.get_running_app()
        if any(s is None for s in synths.values()) or (app and app.external_midi_enabled):
            return (np.zeros(frame_count * output_channels, dtype=np.int16).tobytes(), pyaudio.paContinue)

        with fs_lock:
            melody_samples = synths['melody'].get_samples(frame_count)
            bass_samples = synths['bass'].get_samples(frame_count)
            harmony_samples = synths['harmony'].get_samples(frame_count)
            rhythm_samples = synths['rhythm'].get_samples(frame_count)

        # Convert samples from int16 to float for processing (handled internally by processor now)
        processed_melody = audio_processor.process(melody_samples).reshape(-1, 2)
        processed_bass = audio_processor.process(bass_samples).reshape(-1, 2)
        processed_harmony = audio_processor.process(harmony_samples).reshape(-1, 2)
        processed_rhythm = audio_processor.process(rhythm_samples).reshape(-1, 2)

        output_buffer = np.zeros((frame_count, output_channels), dtype=np.int16)
        
        if output_channels == 8: # 7.1 Surround Mix
            output_buffer[:, 0] = processed_melody[:, 0]    # Front L
            output_buffer[:, 1] = processed_melody[:, 1]    # Front R
            output_buffer[:, 6] = processed_harmony[:, 0]   # Side L
            output_buffer[:, 7] = processed_harmony[:, 1]   # Side R
            output_buffer[:, 4] = processed_bass[:, 0]      # Rear L
            output_buffer[:, 5] = processed_bass[:, 1]      # Rear R
            rhythm_mono = (processed_rhythm[:, 0].astype(np.float32) * 0.707 + 
                           processed_rhythm[:, 1].astype(np.float32) * 0.707).astype(np.int16)
            output_buffer[:, 2] = rhythm_mono               # Center
            output_buffer[:, 3] = rhythm_mono               # LFE (Sub)
        elif output_channels == 2: # Stereo Fallback Mixer
            mixed_left = (processed_melody[:,0].astype(np.int32) + processed_bass[:,0] + processed_harmony[:,0] + processed_rhythm[:,0])
            mixed_right = (processed_melody[:,1].astype(np.int32) + processed_bass[:,1] + processed_harmony[:,1] + processed_rhythm[:,1])
            output_buffer[:, 0] = np.clip(mixed_left, -32768, 32767)
            output_buffer[:, 1] = np.clip(mixed_right, -32768, 32767)

        return (output_buffer.flatten().tobytes(), pyaudio.paContinue)

    # Simplified audio setup for stability
    configs = [
        {'name': '7.1 Surround', 'rate': 48000, 'channels': 8},
        {'name': 'Stereo', 'rate': 44100, 'channels': 2}
    ]
    
    success = False
    for config in configs:
        try:
            logger.info(f"Attempting to initialize {config['name']} audio ({config['rate']}Hz, {config['channels']}-ch)...")
            audio_stream = p.open(format=pyaudio.paInt16, channels=config['channels'], rate=config['rate'], output=True, stream_callback=audio_callback)
            
            rate, channels = config['rate'], config['channels']
            for key in SYNTH_KEYS:
                synths[key] = create_synth(rate, 2.0)
            
            audio_processor = AudioProcessor(samplerate=float(rate))
            output_channels, final_rate = channels, rate
            
            if any(s is None for s in synths.values()): raise Exception("One or more synth instances failed to create.")
            
            logger.info(f"Successfully initialized {config['name']} audio.")
            success = True
            break
        except Exception as e:
            logger.warning(f"{config['name']} audio failed: {e}. Trying next configuration.")
            
    if not success:
        logger.error("FATAL: All audio initialization attempts failed.")
        p, audio_stream = None, None
        synths = {k: None for k in synths}

except Exception as e_fatal:
    logger.critical(f"CRITICAL: PyAudio failed to initialize at all: {e_fatal}")
    p, audio_stream = None, None
    synths = {k: None for k in synths}

# --- Player Class ---
class FluidSynthPlayer:
    def __init__(self, synth_map):
        self.synths = synth_map
        self.midi_out = None

    def set_output_device(self, device_name):
        app = App.get_running_app()
        if self.midi_out:
            self.midi_out.close()
        
        app.external_midi_enabled = False
        with fs_lock:
            for synth in self.synths.values():
                if synth: synth.gain = app.last_audible_gain

        if not device_name:
            logger.info("External MIDI output disabled. Using internal Multi-Synth.")
            return

        try:
            self.midi_out = mido.open_output(device_name)
            app.external_midi_enabled = True
            with fs_lock:
                for synth in self.synths.values():
                    if synth: synth.gain = 0.0
            self.enable_xg_mode()
            logger.info(f"External MIDI output enabled for device '{device_name}'.")
        except Exception as e:
            logger.error(f"Failed to open MIDI output device '{device_name}': {e}")

    def enable_xg_mode(self):
        if self.midi_out and not self.midi_out.closed:
            xg_on_sysex = mido.Message.from_bytes([0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00, 0xF7])
            self.midi_out.send(xg_on_sysex)
            logger.info("Sent XG System On message to external device.")

    def send_message(self, msg):
        if msg.is_meta: return
        
        if self.midi_out and not self.midi_out.closed:
            self.midi_out.send(msg)
            return

        if not hasattr(msg, 'channel'): return

        target_group = channel_routing.get(msg.channel, 'rhythm')
        target_synth = self.synths.get(target_group)

        if target_synth:
            app = App.get_running_app()
            with fs_lock:
                if msg.type == 'program_change':
                    soundfont_id = None
                    if target_group != 'rhythm' and app.sf_layer1['ids'].get(target_group):
                        soundfont_id = app.sf_layer1['ids'][target_group]
                    else:
                        soundfont_id = app.sf_layer2['ids'].get(target_group)

                    if soundfont_id is not None:
                        target_synth.program_select(msg.channel, soundfont_id, 0, msg.program)
                    else:
                        target_synth.program_change(msg.channel, msg.program)

                elif msg.type == 'note_on':
                    target_synth.noteon(msg.channel, msg.note, msg.velocity)
                elif msg.type == 'note_off':
                    target_synth.noteoff(msg.channel, msg.note)
                elif msg.type == 'control_change':
                    target_synth.cc(msg.channel, msg.control, msg.value)

# Create the global player instance
PLAYER = FluidSynthPlayer(synths)

# DiagnosticScreen class
class DiagnosticScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        title = Label(text='System Diagnostics', font_size=32, size_hint_y=0.15, color=(1, 0.84, 0, 1), outline_color=(0,0,0,1), outline_width=2)
        self.layout.add_widget(title)
        
        scroll_view = ScrollView(size_hint_y=0.75)
        self.info_label = Label(text='Gathering info...', size_hint_y=None, markup=True, font_size=16, halign='left', valign='top')
        self.info_label.bind(width=lambda *x: self.info_label.setter('text_size')(self.info_label, (self.info_label.width, None)))
        scroll_view.add_widget(self.info_label)
        self.layout.add_widget(scroll_view)

        nav_bar = make_nav([
            ('Refresh', self.populate_info),
            ('Panic (All Notes Off)', self.send_panic_command),
            ('Back to Files', self.go_back)
        ])
        self.layout.add_widget(nav_bar)
        
        self.add_widget(self.layout)

    def on_enter(self):
        self.populate_info()

    def send_panic_command(self, instance):
        app = App.get_running_app()
        if app and app.player:
            logger.info("DIAGNOSTIC: Sending 'All Notes Off' panic command.")
            for ch in range(16):
                msg = mido.Message('control_change', channel=ch, control=123, value=0)
                app.player.send_message(msg)
            Popup(title="Command Sent", content=Label(text="Sent 'All Notes Off' to all channels."), size_hint=(.5,.3)).open()

    def populate_info(self, instance=None):
        app = App.get_running_app()
        info_text = ""
        
        info_text += f"[b]-- Audio Engine --[/b]\n"
        info_text += f"Status: {'Active' if audio_stream and audio_stream.is_active() else 'Inactive'}\n"
        info_text += f"Channels: {output_channels}\nSample Rate: {final_rate} Hz\n"
        
        fs = synths.get('rhythm')
        if fs:
            settings = fs.get_settings()
            info_text += f"Polyphony: {settings['synth.polyphony']}\n"
            info_text += f"Reverb Active: {settings['synth.reverb.active']}\n"
            info_text += f"Chorus Active: {settings['synth.chorus.active']}\n\n"
        else:
            info_text += "\n"

        info_text += "[b]-- MIDI Devices --[/b]\n"
        info_text += f"Inputs: {', '.join(mido.get_input_names()) or 'None'}\n"
        info_text += f"Outputs: {', '.join(mido.get_output_names()) or 'None'}\n"
        info_text += f"Selected Output: {app.selected_midi_output_name or 'None'}\n\n"
        
        info_text += "[b]-- SoundFont Layers & IDs --[/b]\n"
        info_text += f"Layer 1 (Melody/Custom): {app.sf_layer1['name']}\n"
        for key, sfid in app.sf_layer1['ids'].items():
            info_text += f"  - {key.capitalize()} Synth ID: {sfid}\n"
        info_text += f"Layer 2 (Rhythm/GM): {app.sf_layer2['name']}\n"
        for key, sfid in app.sf_layer2['ids'].items():
            info_text += f"  - {key.capitalize()} Synth ID: {sfid}\n"
            
        self.info_label.text = info_text
        self.info_label.height = self.info_label.texture_size[1]

    def go_back(self, instance):
        self.manager.current = 'files'

# --- Main App Class ---
class FisherPriceApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = PLAYER
        self.fs_lock = fs_lock
        
        self.selected_midi_output_name = None
        self.last_audible_gain = 2.0
        self.current_file_path = None
        self.external_midi_enabled = False
        self.soundfont_index = self._load_soundfont_index()
        self.audio_channels = output_channels
        self.audio_rate = final_rate
        
        self.sf_layer1 = {'name': 'None', 'ids': {}}
        self.sf_layer2 = {'name': 'None', 'ids': {}}
        self.soundfont_load_queue = Queue()
        self.loads_pending = 0

    def _load_soundfont_index(self):
        index_path = os.path.join(APP_ROOT, 'soundfont_index.json')
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r') as f:
                    logger.info("Soundfont index loaded successfully.")
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading soundfont_index.json: {e}")
        return None

    def analyze_midi_for_families(self):
        if not self.current_file_path: return set()
        required_families = set()
        try:
            mid = mido.MidiFile(self.current_file_path)
            for track in mid.tracks:
                for msg in track:
                    if msg.type == 'program_change':
                        family = INSTRUMENT_DATABASE.get(msg.program, {}).get('family', 'Other')
                        required_families.add(family)
        except Exception as e:
            logger.error(f"Could not analyze MIDI for families: {e}")
        return required_families
        
    def find_best_font(self, font_types: list, required_families: set):
        if not self.soundfont_index or not required_families: return None
        search_pool = {}
        for font_type in font_types:
            search_pool.update(self.soundfont_index.get(font_type, {}))
        if not search_pool: return None
        candidates = [(name, len(set(f.keys()).intersection(required_families))) for name, f in search_pool.items()]
        if not candidates: return None
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0] if candidates[0][1] > 0 else None

    def load_midi_settings(self):
        try:
            if os.path.exists(MIDI_SETTINGS_FILE):
                with open(MIDI_SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.selected_midi_output_name = settings.get('output_name')
                    logger.info("Loaded MIDI settings.")
        except Exception as e:
            logger.error(f"Could not load MIDI settings: {e}")

    def save_midi_settings(self):
        settings = {'output_name': self.selected_midi_output_name}
        try:
            with open(MIDI_SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
            logger.info("MIDI settings saved.")
        except Exception as e:
            logger.error(f"Could not save MIDI settings: {e}")

    def load_fallback_gm_font(self):
        if all(s is not None for s in synths.values()):
            fallback_path = os.path.join(APP_ROOT, 'soundfonts', GM_FALLBACK_FONT)
            if os.path.exists(fallback_path):
                logger.info(f"Loading fallback GM font: {GM_FALLBACK_FONT}")
                loaded_ids = {}
                with fs_lock:
                    for key, synth in synths.items():
                        try:
                            sfid = synth.sfload(fallback_path)
                            if sfid != -1:
                                loaded_ids[key] = sfid
                        except Exception as e:
                            logger.error(f"Could not load fallback font into '{key}' synth: {e}")
                
                self.sf_layer2['name'] = GM_FALLBACK_FONT
                self.sf_layer2['ids'] = loaded_ids
                logger.info(f"Fallback GM font loaded with IDs: {loaded_ids}")

    def build(self):
        self.load_midi_settings()
        
        # --- FIX 2: REMOVED HEAVY LOADING FROM HERE ---
        # We now delay self.player.set_output_device and 
        # audio_stream.start_stream() until on_start().
        
        # Set clear color to Robin's Egg Blue
        Window.clearcolor = (129/255, 216/255, 208/255, 1) 
        
        sm = ScreenManager(transition=NoTransition())
        
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(SoundFontSelectScreen(name='soundfont_select'))
        sm.add_widget(BandSelectScreen(name='bands'))
        sm.add_widget(FileSelectScreen(name='files'))
        sm.add_widget(EnhancementScreen(name='enhancer'))
        sm.add_widget(InstrumentListScreen(name='instrument_list'))
        sm.add_widget(FisherPriceDisplayScreen(name='player'))
        sm.add_widget(ChunkSelectScreen(name='chunks'))
        sm.add_widget(LiveInputScreen(name='live'))
        sm.add_widget(ConvertedArtistSelectScreen(name='converted_artists'))
        sm.add_widget(ConvertedSongSelectScreen(name='converted_songs'))
        sm.add_widget(EnhancerFileSelectScreen(name='enhancer_file_select'))
        sm.add_widget(EnhancedBandSelectScreen(name='enhanced_bands'))
        sm.add_widget(EnhancedSongSelectScreen(name='enhanced_songs'))
        sm.add_widget(EnhancedVersionSelectScreen(name='enhanced_versions'))
        sm.add_widget(DiagnosticScreen(name='diagnostic'))
        sm.add_widget(ChunkViewerScreen(name='chunk_viewer'))
        
        sm.current = 'splash'
        return sm

    def on_start(self):
        """
        FIX 2 CONTINUED:
        This method is called by Kivy as soon as the window is visible.
        We schedule the audio setup for the very next frame, allowing
        the UI (Splash Screen) to render first.
        """
        Clock.schedule_once(self.deferred_audio_setup, 0)

    def deferred_audio_setup(self, dt):
        """
        Performs the heavy lifting (loading soundfonts and starting audio)
        after the UI is up and running.
        """
        logger.info("UI is up. Starting deferred audio setup...")
        self.player.set_output_device(self.selected_midi_output_name)
        
        if audio_stream:
            logger.info("Loading initial GM font (Deferred)...")
            self.load_fallback_gm_font()
            audio_stream.start_stream()
            logger.info("Audio stream started.")

    def check_loads(self, dt):
        try:
            status, data = self.soundfont_load_queue.get_nowait()
            self.loads_pending -= 1
            if status == 'success':
                layer, name, new_ids_map = data['layer'], data['sf_name'], data['new_ids']
                logger.info(f"Main thread: Processing success for '{name}' on layer {layer} with new IDs: {new_ids_map}")
                
                target_layer = self.sf_layer1 if layer == 1 else self.sf_layer2

                with self.fs_lock:
                    for synth_key in new_ids_map.keys():
                        old_sfid = target_layer['ids'].get(synth_key)
                        synth = self.player.synths.get(synth_key)
                        if synth and old_sfid is not None:
                            logger.debug(f"Unloading old SFID {old_sfid} from synth '{synth_key}' for best-font load.")
                            synth.sfunload(old_sfid)
                
                if layer == 1:
                    target_layer['name'] = name
                    target_layer['ids'] = new_ids_map 
                else:
                    target_layer['name'] = name 
                    target_layer['ids'].update(new_ids_map) 
            
            if self.loads_pending <= 0:
                Clock.unschedule(self.check_loads)
                self.update_soundfont_labels()
        except Empty: 
            pass
    
    def update_soundfont_labels(self):
        pass

if __name__ == '__main__':
    try:
        FisherPriceApp().run()
    except Exception as e:
        logger.critical(f"FATAL UNHANDLED EXCEPTION in main loop: {e}", exc_info=True)