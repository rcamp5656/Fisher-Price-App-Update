#!/usr/bin/env python3
"""
main.py
Main application entry point for the Fisher Price Player.
This file initializes Kivy, Pygame, the audio engine, and the FluidSynth player.
It contains the main App class which manages global state and screen transitions.
"""

# --- Kivy Configuration (must be set before other imports) ---
from kivy.config import Config
Config.set('graphics', 'fullscreen', 'auto')
Config.set('graphics', 'width', '1920')
Config.set('graphics', 'height', '1080')

# --- Standard Library Imports ---
import os
import threading
import logging
import time
import json
import warnings

# --- Third-Party Imports ---
import pygame
import pygame.midi
import mido
import fluidsynth
import numpy as np
import pyaudio
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.clock import Clock
from kivy.core.window import Window
from music21.midi import translate as midi_translate

# --- Local Module Imports ---
from constants import APP_ROOT, MIDI_SETTINGS_FILE, GM_FALLBACK_FONT
from audio_processing import AudioProcessor
from midi_utils import convert_and_chunk_threaded
from ui.screens_main import (
    SplashScreen, SoundFontSelectScreen, BandSelectScreen, FileSelectScreen,
    EnhancementScreen, EnhancerFileSelectScreen, InstrumentListScreen, LiveInputScreen
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

# --- Audio and Synth Initialization ---
pygame.init()
pygame.midi.init()
fs = None
audio_processor = AudioProcessor()

try:
    p = pyaudio.PyAudio()
    def audio_callback(in_data, frame_count, time_info, status):
        app = App.get_running_app()
        # This callback now correctly silences FluidSynth when an external device is active
        if fs is None or (app and app.external_midi_enabled):
            return (np.zeros(frame_count * 2, dtype=np.int16).tobytes(), pyaudio.paContinue)

        raw_samples = fs.get_samples(frame_count)
        processed_samples = audio_processor.process(raw_samples)
        return (processed_samples.tobytes(), pyaudio.paContinue)
    audio_stream = p.open(format=pyaudio.paInt16, channels=2, rate=44100, output=True, stream_callback=audio_callback)
    fs = fluidsynth.Synth(samplerate=44100, gain=2.0)
    logger.info("FluidSynth instance initialized for manual audio handling.")
except Exception as e:
    logger.error(f"An error occurred during PyAudio/FluidSynth startup: {e}")
    p = audio_stream = fs = None

# --- FluidSynth Player Wrapper Class ---
class FluidSynthPlayer:
    def __init__(self, synth_instance):
        self.fs = synth_instance
        self.bank_msb_cache = {ch: 0 for ch in range(16)}
        self.midi_out = None

    def set_output_device(self, device_id):
        """
        Sets the MIDI output device and updates the app's state to reflect
        whether an external device is active, controlling FluidSynth's audio.
        """
        if self.midi_out:
            self.midi_out.close()
        
        app = App.get_running_app()
        if not app:
            logger.warning("App not running yet, cannot set output device.")
            return
            
        # --- MODIFIED LOGIC START ---
        # Default to internal synth state
        self.midi_out = None
        app.external_midi_enabled = False
        app.xg_mode_enabled = False

        if device_id is None:
            logger.info("External MIDI output disabled. Reverting to internal FluidSynth.")
            return

        try:
            self.midi_out = pygame.midi.Output(device_id)
            logger.info(f"External MIDI output enabled for device ID {device_id}.")
            
            # If we successfully opened the port, set flags to enable external mode
            app.external_midi_enabled = True
            app.xg_mode_enabled = True
            self.enable_xg_mode()

        except Exception as e:
            logger.error(f"Failed to open MIDI output device {device_id}: {e}")
            # Ensure we fall back to a clean internal state if opening fails
            self.midi_out = None
            app.external_midi_enabled = False
            app.xg_mode_enabled = False
        # --- MODIFIED LOGIC END ---

    def enable_xg_mode(self):
        """Sends the XG System On SysEx message to the output device."""
        if self.midi_out:
            xg_on_sysex = [0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00, 0xF7]
            try:
                self.midi_out.write_sysex(0, xg_on_sysex)
                logger.info("Sent XG System On message to external device.")
            except Exception as e:
                logger.error(f"Failed to send XG SysEx message: {e}")

    def note_on(self, note, velocity, channel=0):
        if self.midi_out: self.midi_out.note_on(note, velocity, channel)
        if self.fs and not self.midi_out: self.fs.noteon(channel, note, velocity)

    def note_off(self, note, velocity=0, channel=0):
        if self.midi_out: self.midi_out.note_off(note, velocity, channel)
        if self.fs and not self.midi_out: self.fs.noteoff(channel, note)

    def set_bank(self, bank_msb, channel=0):
        self.bank_msb_cache[channel] = bank_msb
        if self.midi_out:
            self.midi_out.write_short(0xB0 + channel, 0, bank_msb)
        if self.fs and not self.midi_out: self.fs.bank_select(channel, bank_msb)

    def set_instrument(self, program, channel=0):
        if self.midi_out: self.midi_out.set_instrument(program, channel)
        if self.fs and not self.midi_out:
            self.fs.cc(channel, 123, 0)
            app = App.get_running_app()
            bank_msb = self.bank_msb_cache.get(channel, 0)
            if app.sf1_id is not None:
                self.fs.program_select(channel, app.sf1_id, bank_msb, program)
            elif app.sf2_id is not None:
                self.fs.program_select(channel, app.sf2_id, bank_msb, program)

PLAYER = FluidSynthPlayer(fs)

# --- Main Application Class ---
class FisherPriceApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.return_to_screen = None
        self.selected_midi_input_id = None
        self.selected_midi_output_id = None
        self.last_audible_gain = 2.0
        self.current_file_path = None
        self.sf1_id = None
        self.sf1_name = "None"
        self.sf2_id = None
        self.sf2_name = "None"
        self.gm_sfid = None
        self.player = PLAYER
        self.external_midi_enabled = False # This will be controlled automatically by FluidSynthPlayer
        self.xg_mode_enabled = False # This will be controlled automatically by FluidSynthPlayer

    @property
    def current_soundfont_name(self):
        return self.sf1_name

    def load_midi_settings(self):
        try:
            if os.path.exists(MIDI_SETTINGS_FILE):
                with open(MIDI_SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.selected_midi_input_id = settings.get('input_id')
                    self.selected_midi_output_id = settings.get('output_id')
                    # external_midi_enabled is now set dynamically, but we can load it as an initial state
                    self.external_midi_enabled = bool(self.selected_midi_output_id)
                    logger.info("Loaded MIDI settings.")
        except Exception as e:
            logger.error(f"Could not load MIDI settings: {e}")

    def save_midi_settings(self):
        settings = {
            'input_id': self.selected_midi_input_id,
            'output_id': self.selected_midi_output_id,
            # external_midi_enabled is no longer saved as it's state, not a setting
        }
        try:
            with open(MIDI_SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
            logger.info("MIDI settings saved.")
        except Exception as e:
            logger.error(f"Could not save MIDI settings: {e}")

    def load_fallback_gm_font(self):
        if fs:
            fallback_path = os.path.join(APP_ROOT, 'soundfonts', GM_FALLBACK_FONT)
            if os.path.exists(fallback_path):
                try:
                    self.gm_sfid = fs.sfload(fallback_path)
                    self.sf2_id = self.gm_sfid
                    self.sf2_name = GM_FALLBACK_FONT
                    logger.info(f"Successfully loaded fallback GM soundfont into Layer 2: {GM_FALLBACK_FONT}")
                except Exception as e:
                    logger.error(f"Could not load fallback GM soundfont: {e}")
            else:
                logger.error(f"FATAL: Fallback GM soundfont not found at {fallback_path}")

    def build(self):
        self.load_midi_settings()

        # This will now automatically set external_midi_enabled and xg_mode
        self.player.set_output_device(self.selected_midi_output_id)

        self.load_fallback_gm_font()
        if audio_stream:
            audio_stream.start_stream()
        
        Window.clearcolor = (0, 0.8, 0.8, 1)
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
        
        sm.current = 'splash'
        return sm

    def on_stop(self):
        logger.info("Application stopping. Cleaning up resources.")
        if self.root:
            if self.root.has_screen('player'): self.root.get_screen('player').stop_playback()
            if self.root.has_screen('enhancer'): self.root.get_screen('enhancer').stop_playback()
        try:
            if self.player and self.player.midi_out: self.player.midi_out.close()
            if audio_stream and audio_stream.is_active():
                audio_stream.stop_stream(); audio_stream.close()
            if p:
                p.terminate()
            if fs:
                fs.delete()
        except Exception as e:
            logger.error(f"Error during audio/synth shutdown: {e}")

        if pygame.midi.get_init():
            pygame.midi.quit()
        if pygame.get_init():
            pygame.quit()

if __name__ == '__main__':
    try:
        FisherPriceApp().run()
    except Exception as e:
        logger.critical(f"FATAL UNHANDLED EXCEPTION in main loop: {e}", exc_info=True)