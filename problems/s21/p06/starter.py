import os
import shutil


def copy_txt_files(source_folder, destination_folder):
    if not os.path.____(destination_folder):
        os.mkdir(destination_folder)
    count = 0
    for name in os.listdir(source_folder):
        if name[-4:] == ".txt":
            source = os.path.join(source_folder, name)
            destination = os.path.____(destination_folder, name)
            shutil.____(source, destination)
            count += 1
    return count
