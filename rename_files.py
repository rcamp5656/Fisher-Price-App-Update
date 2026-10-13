import os

def batch_rename_files(target_directory):
    """
    Walks through subdirectories of a target directory and replaces spaces
    in filenames with underscores.
    """
    renamed_count = 0
    # os.walk efficiently traverses the directory tree (root, dirs, files)
    for root, dirs, files in os.walk(target_directory):
        for filename in files:
            # Check if the filename contains a space
            if ' ' in filename:
                # Construct the full path for the old filename
                old_filepath = os.path.join(root, filename)
                
                # Create the new filename by replacing spaces
                new_filename = filename.replace(' ', '_')
                new_filepath = os.path.join(root, new_filename)
                
                # Rename the file
                os.rename(old_filepath, new_filepath)
                renamed_count += 1
                print(f'Renamed: "{old_filepath}" -> "{new_filepath}"')

    if renamed_count == 0:
        print("\nNo files with spaces in their names were found to rename.")
    else:
        print(f"\n✅ Success! Renamed {renamed_count} file(s).")

if __name__ == "__main__":
    print("--- Filename Space to Underscore Replacer ---")
    
    # Prompt the user for the root directory containing the 'bands' folders
    path = input("Enter the path to the root directory (e.g., C:\\My_Music): ").strip().strip('"')

    if os.path.isdir(path):
        batch_rename_files(path)
    else:
        print(f"❌ Error: The path '{path}' is not a valid directory.")_organization.py