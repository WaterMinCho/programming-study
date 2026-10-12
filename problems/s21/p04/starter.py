from pathlib import Path

name = input()

folder = Path("new_folder")
folder.____(exist_ok=True)

file_path = folder ____ name
file_path.____()

print(folder.is_dir(), file_path.is_file())
print(file_path.suffix)
