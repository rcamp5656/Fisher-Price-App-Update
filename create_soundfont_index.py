import os
import json
import logging

try:
    from sf2utils.sf2parse import Sf2File
except ImportError:
    print("ERROR: The 'sf2utils' library is not installed.")
    print("Please install it by running: pip install sf2utils")
    exit()

try:
    # This script now depends on the same database as the main app
    from constants import INSTRUMENT_DATABASE, FAMILY_KEYWORDS
except ImportError:
    print("ERROR: Could not find 'constants.py'.")
    print("Please ensure this script is run from your project's root directory.")
    exit()

# --- CONFIGURATION ---
SOUNDFONT_DIR = "soundfonts"  # Assumes a 'soundfonts' folder in the same directory
OUTPUT_JSON_FILE = "soundfont_index.json"

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- FIX: New function for robust family matching ---
def get_family_by_name(instrument_name):
    """
    Finds the instrument family by checking the instrument name against keywords.
    This is more robust than a direct name-to-name lookup.
    """
    instrument_name_lower = instrument_name.lower()
    for family, keywords in FAMILY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in instrument_name_lower:
                return family
    return "Other" # Default if no keyword match is found

def create_soundfont_index():
    """
    Scans the SOUNDFONT_DIR, normalizes instrument names, groups them by the correct family
    using keyword matching, and saves this structured index to a JSON file.
    """
    if not os.path.isdir(SOUNDFONT_DIR):
        logging.error(f"SoundFont directory '{SOUNDFONT_DIR}' not found.")
        return

    soundfont_index = {"gm": {}, "non_gm": {}}
    sf2_files = sorted([f for f in os.listdir(SOUNDFONT_DIR) if f.lower().endswith('.sf2')])

    if not sf2_files:
        logging.warning(f"No .sf2 files found in '{SOUNDFONT_DIR}'.")
        return

    logging.info(f"Found {len(sf2_files)} SoundFont files. Starting indexing process...")

    for sf2_filename in sf2_files:
        sf2_path = os.path.join(SOUNDFONT_DIR, sf2_filename)
        logging.info(f"--> Processing '{sf2_filename}'...")
        try:
            with open(sf2_path, 'rb') as f:
                sf = Sf2File(f)

            instruments_by_family = {}
            for preset in sf.presets:
                # Skip the default EOP preset which is not a real instrument
                if preset.name == 'EOP':
                    continue
                
                # --- FIX: Use the robust get_family_by_name function ---
                # This correctly identifies the family even with messy names
                family = get_family_by_name(preset.name)

                if family not in instruments_by_family:
                    instruments_by_family[family] = []
                
                instruments_by_family[family].append(preset.name)

            if instruments_by_family:
                # Sort instruments within each family alphabetically
                for family in instruments_by_family:
                    instruments_by_family[family].sort()

                filename_lower = sf2_filename.lower()
                is_gm = 'gm' in filename_lower or 'general' in filename_lower
                
                if is_gm:
                    soundfont_index["gm"][sf2_filename] = instruments_by_family
                    category = "GM"
                else:
                    soundfont_index["non_gm"][sf2_filename] = instruments_by_family
                    category = "Non-GM"
                
                logging.info(f"    Found {sum(len(v) for v in instruments_by_family.values())} instruments across {len(instruments_by_family)} families. Categorized as [{category}].")

            else:
                logging.warning(f"    No valid instruments found in '{sf2_filename}'. Skipping.")

        except Exception as e:
            logging.error(f"    Could not parse SoundFont {sf2_filename}: {e}")

    if not soundfont_index["gm"] and not soundfont_index["non_gm"]:
        logging.error("No data was collected. Index file will not be created.")
        return

    try:
        with open(OUTPUT_JSON_FILE, 'w') as f:
            json.dump(soundfont_index, f, indent=4)
        logging.info(f"\nSUCCESS: Index created successfully!")
        logging.info(f"Instrument catalog saved to: {os.path.abspath(OUTPUT_JSON_FILE)}")
    except Exception as e:
        logging.error(f"\nERROR: Could not write to JSON file: {e}")


if __name__ == '__main__':
    create_soundfont_index()