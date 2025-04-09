import subprocess

import os
from scripts.indexing.vec_indexing import build_vector_db
from utility.extract_vecDB import download_and_extract_vector_db


if __name__ == "__main__":
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
    if not os.path.exists(os.getenv("VECTOR_DB_PATH", "./vector_db")):
        print("No vector DB found. Building it from raw data...")
        # Call this before app starts
        download_and_extract_vector_db("https://github.com/dwivedi-ai/sb_vectorDB/raw/main/vector_db.zip")


    subprocess.run(["python", "-m", "src.api"])