# create_dummy_clip.py

import os

def create_dummy_clip(filename="clips/dummy_clip_01.mp4"):
    # Make sure the folder exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Write some dummy data to mimic a small .mp4
    with open(filename, "wb") as f:
        f.write(b"Fake data for testing clip storage.\n")
    print(f"Dummy clip created: {filename}")
