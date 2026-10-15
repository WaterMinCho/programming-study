# 여기에 코드를 작성하세요

import os

folder_name = "sample_folder"
target_name = input()

file_list = os.listdir(folder_name)

print(f"항목 수: {len(file_list)}")

if target_name in file_list:
    print(f"{target_name} 있음")
else:
    print(f"{target_name} 없음")
