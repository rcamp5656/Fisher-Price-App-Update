import mido

# Create a new MIDI file (type 0) and a track
mid = mido.MidiFile(type=0)
track = mido.MidiTrack()
mid.tracks.append(track)

# Add a C-Major scale (one octave)
# Notes are: C, D, E, F, G, A, B, C
notes = [60, 62, 64, 65, 67, 69, 71, 72]
ticks_per_beat = mid.ticks_per_beat # Usually 480
note_duration = ticks_per_beat // 2 # Eighth note

for note_val in notes:
    # Note On: velocity=64 (standard), time=0 (play immediately after previous)
    track.append(mido.Message('note_on', note=note_val, velocity=64, time=0))
    # Note Off: velocity=64, time=note_duration (hold the note for this long)
    track.append(mido.Message('note_off', note=note_val, velocity=64, time=note_duration))

# Define the output filename
output_filename = 'test_scale.mid'
output_path = os.path.join('..', 'Records', output_filename) # Save it to the Records folder

# Save the MIDI file
mid.save(output_path)

print(f"Successfully created '{output_path}'.")
print("You can now use 'test_scale' as the filename in your batch script.")