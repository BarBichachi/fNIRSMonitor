import os

# --- CONFIGURATION ---
# Get the folder where THIS script is located
script_location = os.path.dirname(os.path.abspath(__file__))

# Go up one level to find the Project Root
# (Change to os.path.dirname(script_location) again if you nest it deeper)
project_root = os.path.dirname(script_location)

# Files/Folders to ignore (Added .venv here)
IGNORE_DIRS = {
    '.idea', 'venv', '.venv', 'env', '__pycache__', 'assets',
    '.git', 'build', 'dist', '.vs', 'bin', 'obj', '.pytest_cache'
}

IGNORE_EXT = {
    '.pyc', '.exe', '.dll', '.so', '.zip', '.png', '.jpg', '.jpeg',
    '.ico', '.svg', '.eot', '.woff', '.ttf'
}

OUTPUT_FILE = os.path.join(script_location, 'full_project_code.txt')

# --- EXECUTION ---
print(f"Scanning project starting at: {project_root}")
print(f"Saving output to: {OUTPUT_FILE}")
print("-" * 30)

with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk(project_root):
        # 1. Prune the directory list (This stops os.walk from entering ignored folders)
        # We use a set intersection to filter the list in-place
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            file_ext = os.path.splitext(file)[1].lower()

            # 2. Skip this script itself, the output file, and ignored extensions
            if file == os.path.basename(__file__) or file == 'full_project_code.txt':
                continue
            if file_ext in IGNORE_EXT:
                continue

            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, project_root)

            # 3. Print to console so you know what is happening
            print(f"Adding: {relative_path}")

            outfile.write(f"\n{'=' * 20}\nFILE: {relative_path}\n{'=' * 20}\n")

            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
            except Exception as e:
                error_msg = f"Could not read file: {e}"
                print(f"  -> ERROR: {error_msg}")
                outfile.write(error_msg)

print("-" * 30)
print("Done!")