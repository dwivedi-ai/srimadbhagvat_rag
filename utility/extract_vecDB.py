import os
import zipfile
import requests

def download_and_extract_vector_db(url, output_dir='/vector_db'):
    if os.path.exists(output_dir):
        print(f"[INFO] Vector DB already exists at {output_dir}")
        return
    
    print(f"[INFO] Downloading vector DB from: {url}")
    zip_path = 'vector_db.zip'

    # Download
    with requests.get(url, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    # Extract
    print("[INFO] Extracting vector_db.zip...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(output_dir)

    # Cleanup
    os.remove(zip_path)
    print("[INFO] Extraction complete.")