import subprocess
import os

if __name__ == "__main__":
    # Your previous checks or setup code (if any) can go here

    # Use the Gunicorn command again
    subprocess.run(["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "src.api:app"])