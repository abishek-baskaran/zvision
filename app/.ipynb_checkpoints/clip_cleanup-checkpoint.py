import os
import time

def fifo_clip_cleanup(clips_folder: str, threshold: int = 1000):
    """
    Checks the total number of clips in `clips_folder`.
    If it exceeds `threshold`, remove the oldest clips first.
    """
    # Get all mp4 files sorted by creation/modification time (ascending)
    clips = []
    for file in os.listdir(clips_folder):
        if file.lower().endswith(".mp4"):
            full_path = os.path.join(clips_folder, file)
            # (mtime stands for 'modification time')
            mtime = os.path.getmtime(full_path)
            clips.append((full_path, mtime))

    # Sort by oldest to newest
    clips.sort(key=lambda x: x[1])

    total_clips = len(clips)
    excess = total_clips - threshold

    if excess > 0:
        # We need to remove 'excess' files from the oldest
        for i in range(excess):
            oldest_clip_path = clips[i][0]
            try:
                os.remove(oldest_clip_path)
                print(f"[FIFO CLEANUP] Deleted old clip: {oldest_clip_path}")
            except Exception as e:
                print(f"[FIFO CLEANUP] Error deleting {oldest_clip_path}: {e}")
    else:
        print("[FIFO CLEANUP] No clips removed. Total clips within threshold.")

def periodic_cleanup(clips_folder: str, threshold: int = 1000, interval_seconds: int = 3600):
    """
    Runs the FIFO cleanup every `interval_seconds`.
    """
    while True:
        fifo_clip_cleanup(clips_folder, threshold)
        time.sleep(interval_seconds)

if __name__ == "__main__":
    clips_folder = "./clips"
    # Run a one-time cleanup
    fifo_clip_cleanup(clips_folder, threshold=1000)

    # Or start a periodic loop
    # periodic_cleanup(clips_folder, 1000, 3600)


