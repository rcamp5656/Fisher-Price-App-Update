import mido
import argparse
import os
import shutil

def main():
    parser = argparse.ArgumentParser(description="Check a MIDI file for a drum track on channel 9, moving conflicts if possible.")
    parser.add_argument("--input", required=True, help="Path to the input MIDI file.")
    parser.add_argument("--output", required=True, help="Path for the output MIDI file.")
    args = parser.parse_args()

    try:
        mid = mido.MidiFile(args.input)
    except Exception as e:
        print(f"--> ERROR: Could not read MIDI file {args.input}. Error: {e}")
        return

    has_notes_on_ch9 = False
    is_percussion_on_ch9 = True # Assume it's percussion unless we find a program change

    for track in mid.tracks:
        for msg in track:
            if hasattr(msg, 'channel') and msg.channel == 9:
                if msg.type == 'note_on' and msg.velocity > 0:
                    has_notes_on_ch9 = True
                # A program_change on channel 9 is non-standard and implies a melodic instrument.
                if msg.type == 'program_change':
                    is_percussion_on_ch9 = False
    
    # Case 1: Channel 9 has notes and is treated as percussion (no program changes found)
    if has_notes_on_ch9 and is_percussion_on_ch9:
        print("--> Drum track found on channel 10 (index 9). No changes needed.")
        shutil.copy(args.input, args.output)
        return

    # Case 2: Channel 9 has a melodic instrument that needs to be moved.
    if has_notes_on_ch9 and not is_percussion_on_ch9:
        print("--> Melodic instrument found on channel 10 (index 9). Attempting to move it...")
        
        # --- NEW: Find an empty channel ---
        used_channels = set()
        for i, track in enumerate(mid.tracks):
            for msg in track:
                if hasattr(msg, 'channel'):
                    used_channels.add(msg.channel)
        
        # Find the first available channel, excluding channel 9
        available_channels = set(range(16)) - used_channels
        if 9 in available_channels:
             available_channels.remove(9)

        if not available_channels:
            print("--> All other channels are in use. Cannot move the instrument. Leaving file as is.")
            shutil.copy(args.input, args.output)
            return

        new_channel = sorted(list(available_channels))[0]
        print(f"--> Moving instrument from channel 10 to empty channel {new_channel + 1}.")

        # --- NEW: Re-assign all messages from channel 9 to the new empty channel ---
        for track in mid.tracks:
            for msg in track:
                if hasattr(msg, 'channel') and msg.channel == 9:
                    msg.channel = new_channel
        
        # Now that channel 9 is free, we can proceed to generate the drum track.
        print("--> Channel 10 is now free. Generating new drum track...")
    
    # Case 3: Channel 9 is empty.
    if not has_notes_on_ch9:
        print("--> No drum track found. Generating a new, simple drum track...")

    # --- Drum Generation Logic (now runs for Case 2 and 3) ---
    new_mid = mido.MidiFile(type=1, ticks_per_beat=mid.ticks_per_beat)
    for track in mid.tracks:
        new_mid.tracks.append(track)

    drum_track = mido.MidiTrack()
    
    total_ticks = 0
    for track in mid.tracks:
        tick_counter = 0
        for msg in track:
            tick_counter += msg.time
        if tick_counter > total_ticks:
            total_ticks = tick_counter
            
    if total_ticks == 0:
        print("--> MIDI file has no notes. Cannot determine length to add drums.")
        shutil.copy(args.input, args.output)
        return

    ticks_per_beat = mid.ticks_per_beat
    kick_note = 36
    snare_note = 38
    
    drum_track.append(mido.Message('program_change', channel=9, program=0, time=0))

    last_event_tick = 0
    for current_tick in range(0, total_ticks, ticks_per_beat // 2):
        time_delta = current_tick - last_event_tick
        
        is_downbeat = (current_tick % (ticks_per_beat * 2)) == 0
        is_backbeat = (current_tick % (ticks_per_beat * 2)) == ticks_per_beat

        if is_downbeat:
            drum_track.append(mido.Message('note_on', channel=9, note=kick_note, velocity=100, time=time_delta))
            drum_track.append(mido.Message('note_off', channel=9, note=kick_note, velocity=0, time=ticks_per_beat // 2))
            last_event_tick = current_tick + ticks_per_beat // 2
        elif is_backbeat:
            drum_track.append(mido.Message('note_on', channel=9, note=snare_note, velocity=100, time=time_delta))
            drum_track.append(mido.Message('note_off', channel=9, note=snare_note, velocity=0, time=ticks_per_beat // 2))
            last_event_tick = current_tick + ticks_per_beat // 2

    new_mid.tracks.append(drum_track)
    new_mid.save(args.output)
    print(f"--> MIDI file has been updated with a new drum track on channel 10 (index 9).")

if __name__ == "__main__":
    main()