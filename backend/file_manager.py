import os
import shutil
import zipfile
import io
from config import LOCAL_REPO_PATH

def init_folder(path=LOCAL_REPO_PATH):
    if not os.path.exists(path):
        os.makedirs(path)

def clear_folder(path=LOCAL_REPO_PATH):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def save_repo_archive(zip_bytes, path=LOCAL_REPO_PATH):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        temp_extract = path + "_tmp"
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)
        os.makedirs(temp_extract)

        archive.extractall(temp_extract)

        top_level = os.listdir(temp_extract)[0]
        top_path = os.path.join(temp_extract, top_level)

        for item in os.listdir(top_path):
            s = os.path.join(top_path, item)
            d = os.path.join(path, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

        shutil.rmtree(temp_extract)

def extract_zip(zip_path: str, dest_dir: str):
    """Extract a zip file to the provided destination directory.

    If the destination exists, it will be replaced.
    """
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as archive:
        archive.extractall(dest_dir)
