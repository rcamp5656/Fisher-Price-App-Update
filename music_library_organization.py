import os
import shutil
from tqdm import tqdm

def clear_screen():
    """Clears the console screen."""
    os.system("cls" if os.name == "nt" else "clear")

def format_artist_name(artist_name):
    """Formats an artist name to be ALL CAPS with spaces replaced by underscores."""
    return artist_name.strip().upper().replace(' ', '_')

def prompt_path(prompt_text):
    """
    Prompts the user for a valid directory path, offering to create it if it doesn't exist.
    """
    while True:
        path = input(prompt_text).strip().strip('"')
        if not path:
            print("Error: Path cannot be empty.")
            continue

        if os.path.exists(path):
            if os.path.isdir(path):
                return path
            else:
                print("Error: The path exists but is a file, not a directory.")
        else:
            create = input(f"Path does not exist. Create it? (y/n): ").lower()
            if create == "y":
                try:
                    os.makedirs(path)
                    print(f"Path '{path}' created.")
                    return path
                except OSError as e:
                    print(f"Error creating directory: {e}")
            else:
                print("Please enter a valid, existing path.")


def prompt_yesno(prompt_text):
    """Prompts the user for a yes/no answer."""
    while True:
        resp = input(prompt_text + " (y/n): ").lower()
        if resp in ("y", "n"):
            return resp == "y"

def organize_midi_library_by_folder(source_dir, master_dir, dry_run):
    """
    Organizes MIDI files from a source directory where each sub-folder is an artist's name.
    The folder name is used as the artist, and the files within are copied.
    """
    log_lines = []
    supported_exts = (".mid", ".midi")

    # --- Pre-scan to count total files for the progress bar ---
    print("\nScanning source directory for MIDI files...")
    files_to_process = []
    try:
        # Walk the source directory to find all artist subfolders
        for artist_folder_name in os.listdir(source_dir):
            artist_source_path = os.path.join(source_dir, artist_folder_name)
            if os.path.isdir(artist_source_path):
                # Find all MIDI files within the artist folder
                for filename in os.listdir(artist_source_path):
                    if filename.lower().endswith(supported_exts):
                        files_to_process.append((artist_folder_name, filename))
    except FileNotFoundError:
        print(f"Error: Source directory not found: {source_dir}")
        return

    if not files_to_process:
        print("No MIDI files found in any sub-folders to process.")
        return

    print(f"Found {len(files_to_process)} total MIDI files to process.")

    with tqdm(total=len(files_to_process), desc="Processing files", unit="file") as pbar:
        for raw_artist_name, filename in files_to_process:
            pbar.set_postfix_str(f"{raw_artist_name}/{filename}")

            # Format the artist name from the source folder name
            final_artist = format_artist_name(raw_artist_name)

            # --- Define source and destination paths ---
            artist_source_path = os.path.join(source_dir, raw_artist_name)
            src_file_path = os.path.join(artist_source_path, filename)
            
            dest_artist_dir = os.path.join(master_dir, final_artist)
            dest_file_path = os.path.join(dest_artist_dir, filename) # Filename is copied directly

            if not dry_run:
                os.makedirs(dest_artist_dir, exist_ok=True)

            # --- Handle potential filename conflicts in the destination ---
            counter = 1
            base, ext = os.path.splitext(dest_file_path)
            while not dry_run and os.path.exists(dest_file_path):
                dest_file_path = f"{base}_({counter}){ext}"
                counter += 1

            # --- Perform copy or log for dry run ---
            if dry_run:
                action = f"[DRY RUN] Would copy: {src_file_path} -> {dest_file_path}"
            else:
                shutil.copy2(src_file_path, dest_file_path)
                action = f"Copied: {src_file_path} -> {dest_file_path}"
            log_lines.append(action)
            
            pbar.update(1)

    log_path = os.path.join(master_dir, "organize_log.txt")
    print("\n\nWriting log file...")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            for line in log_lines:
                f.write(line + "\n")
        print(f"✅ Process complete. Log saved to {log_path}.")
    except IOError as e:
        print(f"Error writing log file: {e}")


if __name__ == "__main__":
    clear_screen()
    print("🎹 MIDI Library Organizer (Folder Mode) 🎹\n")
    print("This script organizes MIDI files based on their parent folder's name.")
    print("It assumes your source directory is structured like: .../Source/ARTIST_NAME/Song.mid")
    print("Artist folder names will be created in the destination as ALL_CAPS_WITH_UNDERSCORES.")
    print("-" * 60)

    source_dir = prompt_path("Enter the SOURCE folder containing your artist sub-folders: ")
    master_dir = prompt_path("Enter the MASTER destination folder: ")
    dry_run = prompt_yesno("Run in Dry Run mode (won't copy any files)?")

    print("\n✅ Configuration:")
    print(f"  Source Directory: {source_dir}")
    print(f"  Master Directory: {master_dir}")
    print(f"  Dry Run: {'Yes' if dry_run else 'No'}")
    print("-" * 60)

    if prompt_yesno("Proceed with organization?"):
        organize_midi_library_by_folder(source_dir, master_dir, dry_run)
    else:
        print("❌ Operation cancelled.")
    
    print("\n--- All tasks are done. ---")