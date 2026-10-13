import mido
import os
from queue import Queue
import math
import logging

# Set up a logger for this module
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# This is the strict physical limit for the plastic disks.
BEATS_PER_CHUNK = 86

def save_chunk(output_path, chunk_number, messages, ticks_per_beat):
    """Saves a list of MIDI messages as a new chunk file."""
    try:
        # Create a new MIDI file with one track
        chunk_mid = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
        track = mido.MidiTrack()
        
        # Add all the messages for this chunk to the track
        track.extend(messages)
        chunk_mid.tracks.append(track)

        # Format the filename, e.g., FP_Chunk_01_SongTitle.mid
        base_name = os.path.basename(output_path)
        file_name = f"FP_Chunk_{chunk_number:02d}_{base_name}"
        
        # Create the full path and save the file
        full_output_path = os.path.join(os.path.dirname(output_path), file_name)
        chunk_mid.save(full_output_path)
        logger.info(f"Successfully saved chunk: {full_output_path}")
        return 1 # Return 1 to count the number of chunks created
    except Exception as e:
        logger.error(f"Failed to save chunk {chunk_number}: {e}")
        return 0 # Return 0 if saving failed

def convert_and_chunk_threaded(file_path: str, progress_queue: Queue):
    """
    Processes a MIDI file, slices it into chunks of a fixed beat length,
    and handles note boundaries to prevent "stuck notes".
    """
    try:
        progress_queue.put(('progress', 10, 'Loading MIDI file...'))
        
        # --- 1. Load the original MIDI and get its properties ---
        original_mid = mido.MidiFile(file_path)
        ticks_per_beat = original_mid.ticks_per_beat
        
        # Default tempo is 120 BPM (500,000 microseconds per beat)
        tempo = 500000 
        for msg in mido.merge_tracks(original_mid.tracks):
            if msg.is_meta and msg.type == 'set_tempo':
                tempo = msg.tempo
                break

        def ticks_to_beats(ticks):
            return ticks / ticks_per_beat

        # --- 2. Prepare for chunking ---
        # Determine output directory based on input path
        band_name = os.path.basename(os.path.dirname(file_path))
        song_name = os.path.splitext(os.path.basename(file_path))[0]
        output_dir = os.path.join('Converted', band_name, song_name)
        os.makedirs(output_dir, exist_ok=True)
        output_path_base = os.path.join(output_dir, f"{song_name}.mid")

        progress_queue.put(('progress', 20, 'Preparing to create chunks...'))

        # --- 3. Main chunking loop ---
        current_chunk_messages = []
        active_notes = set() # Stores notes that are currently 'on'
        current_beat_count = 0.0
        chunk_number = 1
        total_chunks_created = 0
        total_note_ons = 0

        # Merge all tracks into a single stream for easier timekeeping
        merged_track = mido.merge_tracks(original_mid.tracks)

        for msg in merged_track:
            # Add message duration (in beats) to our counter
            if msg.time > 0:
                current_beat_count += ticks_to_beats(msg.time)

            # --- BOUNDARY CHECK ---
            if current_beat_count >= BEATS_PER_CHUNK:
                progress_queue.put(('progress', 20 + chunk_number * 5, f'Creating chunk {chunk_number}...'))
                
                # Calculate how many ticks we have "overshot" the boundary
                overshot_beats = current_beat_count - BEATS_PER_CHUNK
                overshot_ticks = int(overshot_beats * ticks_per_beat)

                # **CRITICAL: Terminate active notes at the boundary**
                # Create note_off messages for all notes still playing
                for note in active_notes:
                    channel = note[1]
                    note_val = note[0]
                    # This places the note_off right at the 86-beat mark
                    current_chunk_messages.append(mido.Message('note_off', note=note_val, velocity=0, channel=channel, time=0))
                
                # Save the completed chunk
                total_chunks_created += save_chunk(output_path_base, chunk_number, current_chunk_messages, ticks_per_beat)
                
                # --- Reset for the next chunk ---
                chunk_number += 1
                current_chunk_messages = []
                
                # The next chunk starts with the time we overshot
                current_beat_count = overshot_beats

                # **CRITICAL: Re-trigger sustained notes in the new chunk**
                # Add note_on messages for the notes we just terminated
                for note in active_notes:
                    channel = note[1]
                    note_val = note[0]
                    # Add with time=0 so they start immediately
                    current_chunk_messages.append(mido.Message('note_on', note=note_val, velocity=100, channel=channel, time=0))
            
            # Add the current message to the list for the current chunk
            # Adjust its time if it was the one that crossed the boundary
            msg_copy = msg.copy()
            if 'overshot_ticks' in locals() and overshot_ticks > 0:
                 msg_copy.time = overshot_ticks
                 del overshot_ticks # Use this variable only once

            current_chunk_messages.append(msg_copy)

            # Update the set of active notes
            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes.add((msg.note, msg.channel))
                total_note_ons +=1
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                active_notes.discard((msg.note, msg.channel))

        # --- 4. Save the final, incomplete chunk ---
        if current_chunk_messages:
            total_chunks_created += save_chunk(output_path_base, chunk_number, current_chunk_messages, ticks_per_beat)

        progress_queue.put(('progress', 95, 'Finalizing...'))
        progress_queue.put(('result', (total_note_ons, total_chunks_created)))

    except Exception as e:
        logger.error(f"An error occurred in convert_and_chunk_threaded: {e}", exc_info=True)
        progress_queue.put(('error', str(e)))