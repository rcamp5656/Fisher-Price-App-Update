"""
constants.py
Central repository for static data, paths, and constants used throughout the application.
"""
import os

# --- Directory Setup ---
APP_ROOT = os.path.dirname(os.path.realpath(__file__))
MIDI_FOLDER = os.path.join(APP_ROOT, 'MIDI')
CONVERTED_FOLDER = os.path.join(APP_ROOT, 'Converted')
LIVE_FOLDER = os.path.join(CONVERTED_FOLDER, 'Live')
RECORDS_FOLDER = os.path.join(APP_ROOT, 'Records')
ENHANCED_FOLDER = os.path.join(APP_ROOT, 'Enhanced_MIDI')
MAPPINGS_FOLDER = os.path.join(APP_ROOT, 'mappings')
MIDI_SETTINGS_FILE = os.path.join(APP_ROOT, 'midi_settings.json')

# Create directories on startup
for folder in (MIDI_FOLDER, CONVERTED_FOLDER, LIVE_FOLDER, RECORDS_FOLDER, ENHANCED_FOLDER, MAPPINGS_FOLDER):
    os.makedirs(folder, exist_ok=True)

# --- MIDI System Exclusive (SysEx) Messages ---
XG_ON_SYSEX = [240, 67, 16, 76, 0, 0, 126, 0, 247]
GM_RESET = (0x7E, 0x7F, 0x09, 0x01)
GS_RESET = (0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41)
XG_RESET = (0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00)

# --- SoundFont & UI Constants ---
GM_FALLBACK_FONT = 'Arachno SoundFont - Version 1.0.sf2'
FILES_PER_PAGE = 49
GM_SOUNDFONTS = [
    'arachno.sf2', 'arachnosoft.sf2', 'fluidr3_gm.sf2',
    'generaluser gs.sf2', 'omegamgs2.sf2'
]

# --- Music Constants ---
FP_MIDI_START_NOTE = 60
FP_MIDI_END_NOTE = 81
FP_CHUNK_LENGTH_BEATS = 86

# --- Embedded Master Instrument Database ---
INSTRUMENT_DATABASE = {
    0: {'name': 'Acoustic Grand Piano', 'family': 'Piano'}, 1: {'name': 'Bright Acoustic Piano', 'family': 'Piano'},
    2: {'name': 'Electric Grand Piano', 'family': 'Piano'}, 3: {'name': 'Honky-tonk Piano', 'family': 'Piano'},
    4: {'name': 'Electric Piano 1', 'family': 'Piano'}, 5: {'name': 'Electric Piano 2', 'family': 'Piano'},
    6: {'name': 'Harpsichord', 'family': 'Piano'}, 7: {'name': 'Clavinet', 'family': 'Piano'},
    8: {'name': 'Celesta', 'family': 'Chromatic Percussion'}, 9: {'name': 'Glockenspiel', 'family': 'Chromatic Percussion'},
    10: {'name': 'Music Box', 'family': 'Chromatic Percussion'}, 11: {'name': 'Vibraphone', 'family': 'Chromatic Percussion'},
    12: {'name': 'Marimba', 'family': 'Chromatic Percussion'}, 13: {'name': 'Xylophone', 'family': 'Chromatic Percussion'},
    14: {'name': 'Tubular Bells', 'family': 'Chromatic Percussion'}, 15: {'name': 'Dulcimer', 'family': 'Chromatic Percussion'},
    16: {'name': 'Drawbar Organ', 'family': 'Organ'}, 17: {'name': 'Percussive Organ', 'family': 'Organ'},
    18: {'name': 'Rock Organ', 'family': 'Organ'}, 19: {'name': 'Church Organ', 'family': 'Organ'},
    20: {'name': 'Reed Organ', 'family': 'Organ'}, 21: {'name': 'Accordion', 'family': 'Organ'},
    22: {'name': 'Harmonica', 'family': 'Organ'}, 23: {'name': 'Tango Accordion', 'family': 'Organ'},
    24: {'name': 'Acoustic Guitar (nylon)', 'family': 'Guitar'}, 25: {'name': 'Acoustic Guitar (steel)', 'family': 'Guitar'},
    26: {'name': 'Electric Guitar (jazz)', 'family': 'Guitar'}, 27: {'name': 'Electric Guitar (clean)', 'family': 'Guitar'},
    28: {'name': 'Electric Guitar (muted)', 'family': 'Guitar'}, 29: {'name': 'Overdriven Guitar', 'family': 'Guitar'},
    30: {'name': 'Distortion Guitar', 'family': 'Guitar'}, 31: {'name': 'Guitar Harmonics', 'family': 'Guitar'},
    32: {'name': 'Acoustic Bass', 'family': 'Bass'}, 33: {'name': 'Electric Bass (finger)', 'family': 'Bass'},
    34: {'name': 'Electric Bass (pick)', 'family': 'Bass'}, 35: {'name': 'Fretless Bass', 'family': 'Bass'},
    36: {'name': 'Slap Bass 1', 'family': 'Bass'}, 37: {'name': 'Slap Bass 2', 'family': 'Bass'},
    38: {'name': 'Synth Bass 1', 'family': 'Bass'}, 39: {'name': 'Synth Bass 2', 'family': 'Bass'},
    40: {'name': 'Violin', 'family': 'Strings'}, 41: {'name': 'Viola', 'family': 'Strings'},
    42: {'name': 'Cello', 'family': 'Strings'}, 43: {'name': 'Contrabass', 'family': 'Strings'},
    44: {'name': 'Tremolo Strings', 'family': 'Strings'}, 45: {'name': 'Pizzicato Strings', 'family': 'Strings'},
    46: {'name': 'Orchestral Harp', 'family': 'Strings'}, 47: {'name': 'Timpani', 'family': 'Strings'},
    48: {'name': 'String Ensemble 1', 'family': 'Ensemble'}, 49: {'name': 'String Ensemble 2', 'family': 'Ensemble'},
    50: {'name': 'Synth Strings 1', 'family': 'Ensemble'}, 51: {'name': 'Synth Strings 2', 'family': 'Ensemble'},
    52: {'name': 'Choir Aahs', 'family': 'Ensemble'}, 53: {'name': 'Voice Oohs', 'family': 'Ensemble'},
    54: {'name': 'Synth Voice', 'family': 'Ensemble'}, 55: {'name': 'Orchestra Hit', 'family': 'Ensemble'},
    56: {'name': 'Trumpet', 'family': 'Brass'}, 57: {'name': 'Trombone', 'family': 'Brass'},
    58: {'name': 'Tuba', 'family': 'Brass'}, 59: {'name': 'Muted Trumpet', 'family': 'Brass'},
    60: {'name': 'French Horn', 'family': 'Brass'}, 61: {'name': 'Brass Section', 'family': 'Brass'},
    62: {'name': 'Synth Brass 1', 'family': 'Brass'}, 63: {'name': 'Synth Brass 2', 'family': 'Brass'},
    64: {'name': 'Soprano Sax', 'family': 'Reed'}, 65: {'name': 'Alto Sax', 'family': 'Reed'},
    66: {'name': 'Tenor Sax', 'family': 'Reed'}, 67: {'name': 'Baritone Sax', 'family': 'Reed'},
    68: {'name': 'Oboe', 'family': 'Reed'}, 69: {'name': 'English Horn', 'family': 'Reed'},
    70: {'name': 'Bassoon', 'family': 'Reed'}, 71: {'name': 'Clarinet', 'family': 'Reed'},
    72: {'name': 'Piccolo', 'family': 'Pipe'}, 73: {'name': 'Flute', 'family': 'Pipe'},
    74: {'name': 'Recorder', 'family': 'Pipe'}, 75: {'name': 'Pan Flute', 'family': 'Pipe'},
    76: {'name': 'Blown Bottle', 'family': 'Pipe'}, 77: {'name': 'Shakuhachi', 'family': 'Pipe'},
    78: {'name': 'Whistle', 'family': 'Pipe'}, 79: {'name': 'Ocarina', 'family': 'Pipe'},
    80: {'name': 'Lead 1 (square)', 'family': 'Synth Lead'}, 81: {'name': 'Lead 2 (sawtooth)', 'family': 'Synth Lead'},
    82: {'name': 'Lead 3 (calliope)', 'family': 'Synth Lead'}, 83: {'name': 'Lead 4 (chiff)', 'family': 'Synth Lead'},
    84: {'name': 'Lead 5 (charang)', 'family': 'Synth Lead'},
    85: {'name': 'Lead 6 (voice)', 'family': 'Synth Lead'}, 86: {'name': 'Lead 7 (fifths)', 'family': 'Synth Lead'},
    87: {'name': 'Lead 8 (bass + lead)', 'family': 'Synth Lead'},
    88: {'name': 'Pad 1 (new age)', 'family': 'Synth Pad'}, 89: {'name': 'Pad 2 (warm)', 'family': 'Synth Pad'},
    90: {'name': 'Pad 3 (polysynth)', 'family': 'Synth Pad'}, 91: {'name': 'Pad 4 (choir)', 'family': 'Synth Pad'},
    92: {'name': 'Pad 5 (bowed)', 'family': 'Synth Pad'}, 93: {'name': 'Pad 6 (metallic)', 'family': 'Synth Pad'},
    94: {'name': 'Pad 7 (halo)', 'family': 'Synth Pad'}, 95: {'name': 'Pad 8 (sweep)', 'family': 'Synth Pad'},
    96: {'name': 'FX 1 (rain)', 'family': 'Synth Effects'}, 97: {'name': 'FX 2 (soundtrack)', 'family': 'Synth Effects'},
    98: {'name': 'FX 3 (crystal)', 'family': 'Synth Effects'}, 99: {'name': 'FX 4 (atmosphere)', 'family': 'Synth Effects'},
    100: {'name': 'FX 5 (brightness)', 'family': 'Synth Effects'}, 101: {'name': 'FX 6 (goblins)', 'family': 'Synth Effects'},
    102: {'name': 'FX 7 (echoes)', 'family': 'Synth Effects'}, 103: {'name': 'FX 8 (sci-fi)', 'family': 'Synth Effects'},
    104: {'name': 'Sitar', 'family': 'Ethnic'}, 105: {'name': 'Banjo', 'family': 'Ethnic'},
    106: {'name': 'Shamisen', 'family': 'Ethnic'}, 107: {'name': 'Koto', 'family': 'Ethnic'},
    108: {'name': 'Kalimba', 'family': 'Ethnic'}, 109: {'name': 'Bag pipe', 'family': 'Ethnic'},
    110: {'name': 'Fiddle', 'family': 'Ethnic'}, 111: {'name': 'Shanai', 'family': 'Ethnic'},
    112: {'name': 'Tinkle Bell', 'family': 'Percussive'}, 113: {'name': 'Agogo', 'family': 'Percussive'},
    114: {'name': 'Steel Drums', 'family': 'Percussive'}, 115: {'name': 'Woodblock', 'family': 'Percussive'},
    116: {'name': 'Taiko Drum', 'family': 'Percussive'}, 117: {'name': 'Melodic Tom', 'family': 'Percussive'},
    118: {'name': 'Synth Drum', 'family': 'Percussive'}, 119: {'name': 'Reverse Cymbal', 'family': 'Percussive'},
    120: {'name': 'Guitar Fret Noise', 'family': 'Sound Effects'}, 121: {'name': 'Breath Noise', 'family': 'Sound Effects'},
    122: {'name': 'Seashore', 'family': 'Sound Effects'}, 123: {'name': 'Bird Tweet', 'family': 'Sound Effects'},
    124: {'name': 'Telephone Ring', 'family': 'Sound Effects'}, 125: {'name': 'Helicopter', 'family': 'Sound Effects'},
    126: {'name': 'Applause', 'family': 'Sound Effects'}, 127: {'name': 'Gunshot', 'family': 'Sound Effects'},
}

# --- Instrument Family Keywords for flexible matching ---
FAMILY_KEYWORDS = {
    'Piano': ['piano', 'grand', 'keyboard', 'rhodes', 'clavinet'],
    'Chromatic Percussion': ['celesta', 'glockenspiel', 'box', 'vibraphone', 'marimba', 'xylophone', 'bells'],
    'Organ': ['organ', 'accordion', 'harmonica'],
    'Guitar': ['guitar', 'acoustic', 'steel', 'electric', 'jazz', 'clean', 'muted', 'overdriven', 'distortion'],
    'Bass': ['bass', 'fretless', 'slap', 'synth'],
    'Strings': ['strings', 'violin', 'viola', 'cello', 'contrabass', 'harp', 'tremolo', 'pizzicato'],
    'Ensemble': ['ensemble', 'choir', 'voice', 'hit'],
    'Brass': ['brass', 'trumpet', 'trombone', 'tuba', 'horn'],
    'Reed': ['sax', 'oboe', 'english', 'bassoon', 'clarinet'],
    'Pipe': ['flute', 'recorder', 'pan', 'bottle', 'shakuhachi', 'whistle', 'ocarina'],
    'Synth Lead': ['lead', 'square', 'sawtooth', 'calliope', 'chiff', 'charang', 'fifths'],
    'Synth Pad': ['pad', 'new age', 'warm', 'polysynth', 'choir', 'bowed', 'metallic', 'halo', 'sweep'],
    'Synth Effects': ['fx', 'rain', 'soundtrack', 'crystal', 'atmosphere', 'brightness', 'goblins', 'echoes', 'sci-fi'],
    'Ethnic': ['sitar', 'banjo', 'shamisen', 'koto', 'kalimba', 'bag pipe', 'fiddle', 'shanai'],
    'Percussive': ['tinkle', 'agogo', 'steel drums', 'woodblock', 'taiko', 'tom', 'synth drum'],
    'Sound Effects': ['fret', 'breath', 'seashore', 'tweet', 'telephone', 'helicopter', 'applause', 'gunshot']
}