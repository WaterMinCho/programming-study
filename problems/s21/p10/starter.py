from pathlib import Path


def delete_txt_files(folder_path):
    count = 0
    for item in Path(folder_path).____():
        if item.is_file() and item.____ == ".txt":
            item.____()
            count += 1
    return count
