# app/inference/pipeline.py

import cv2
import time
import os
import psutil
from typing import Optional, List, Tuple
from app.database.calibration import fetch_calibration_for_camera
from app.inference.detection import run_yolo_inference
from app.inference.crossing import compute_side_of_line, check_line_crossings

# We'll keep global or local state for naive approach
def process_camera_stream(
    source: str,
    output_path: str,
    camera_id: Optional[str] = None,
    downscale_width=640,
    downscale_height=480,
    skip_frame=1,
    write_mode="all"
):
    """
    Similar to your existing approach, but now referencing detection and crossing logic
    from separate modules.
    """

    # 1. Possibly fetch calibration line
    line_data = None
    if camera_id:
        line_data = fetch_calibration_for_camera(camera_id)
        if line_data:
            print(f"Loaded calibration for {camera_id}: {line_data}")

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: could not open {source}")
        return

    out_width = downscale_width
    out_height = downscale_height

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps_input = cap.get(cv2.CAP_PROP_FPS) or 30.0
    writer = cv2.VideoWriter(output_path, fourcc, fps_input, (out_width, out_height))

    frame_count = 0
    start_time = time.time()

    # We'll track naive crossing stats
    entry_count = 0
    exit_count = 0
    old_centers = []  # list of (cx, cy, side)

    last_print_time = time.time()
    frames_since_last_print = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of stream or read error.")
            break

        frame_count += 1
        frames_since_last_print += 1

        # Downscale
        frame = cv2.resize(frame, (out_width, out_height), interpolation=cv2.INTER_LINEAR)

        do_inference = (frame_count % skip_frame == 0)
        this_frame_centers = []

        if do_inference:
            boxes, scores, labels = run_yolo_inference(frame)
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
                text = f"{labels[i]}: {scores[i]:.2f}"
                cv2.putText(frame, text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

                # center
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                this_frame_centers.append((cx, cy))

            # line crossing
            if line_data:
                camera_id_int = int(camera_id) if camera_id else None
                entry_count, exit_count = check_line_crossings(
                    this_frame_centers, 
                    old_centers, 
                    line_data, 
                    entry_count, 
                    exit_count,
                    camera_id_int  # pass as int
                )

        # write frames
        if write_mode == "all":
            writer.write(frame)
        elif write_mode == "processed" and do_inference:
            writer.write(frame)

        # print performance once per second
        current_time = time.time()
        if current_time - last_print_time >= 1.0:
            elapsed = current_time - last_print_time
            fps = frames_since_last_print / elapsed
            cpu_usage = psutil.cpu_percent()
            print(f"Time Interval: {elapsed:.2f}s | "
                  f"Frames={frames_since_last_print} | "
                  f"FPS={fps:.2f} | CPU={cpu_usage:.1f}% | "
                  f"Entries={entry_count}, Exits={exit_count}")
            last_print_time = current_time
            frames_since_last_print = 0

        # update old_centers
        # We store each center with a "side" if we want. But let's set side=None for now
        old_centers = []
        for (cx, cy) in this_frame_centers:
            old_side = None  # we can compute it if needed
            old_centers.append((cx, cy, old_side))

    cap.release()
    writer.release()
    print(f"Saved annotated video to {output_path}")
    print(f"Final entry={entry_count}, exit={exit_count}")
