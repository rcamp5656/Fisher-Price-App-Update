
import logging
from generate_1024_instrument_midi import generate_1024_instrument_midi

# Configure logging
logging.basicConfig(
    filename="conversion.log",
    filemode="w",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

input_path = "The_Number_Of_The_Beast.mid"
output_path = "Enhanced/IRON_MAIDEN/The_Number_Of_The_Beast_1024.mid"

logging.info("Starting enhancement...")
try:
    generate_1024_instrument_midi(input_path, output_path, logger=logging)
    logging.info(f"Saved enhanced MIDI to {output_path}")
except Exception as e:
    logging.error(f"Enhancement failed: {e}")
