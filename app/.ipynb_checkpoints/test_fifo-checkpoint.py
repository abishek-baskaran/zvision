# test_fifo.py

import os
from clip_cleanup import fifo_clip_cleanup
from create_dummy_clip import create_dummy_clip

def produce_dummy_clips(folder="clips", count=5):
    os.makedirs(folder, exist_ok=True)
    for i in range(count):
        filename = os.path.join(folder, f"excess_clip_{i+1:02d}.mp4")
        create_dummy_clip(filename=filename)

def main():
    # 1. Produce 5 dummy clips (enough to exceed a threshold for testing)
    produce_dummy_clips(folder="clips", count=5)
    
    # 2. Suppose our threshold is 3
    fifo_clip_cleanup(clips_folder="clips", threshold=3)

if __name__ == "__main__":
    main()
