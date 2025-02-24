import cv2
import time
import os
import psutil  # optional for CPU usage
from app.detection_deepsparse import run_yolo_inference

def process_camera_stream(
    source,
    output_path,
    downscale_width=640,
    downscale_height=480,
    skip_frame=1,            # If set to N, only run inference on every Nth frame (default=1 => no skip)
    write_mode="all"         # "all" => write every frame, "processed" => write only frames that got inference
):
    """
    Reads frames from `source` (file path or RTSP), runs YOLO inference (Ultralytics) on every Nth frame,
    and saves annotated output to `output_path`. Logs performance once per second.
    
    :param source: Path or RTSP URL.
    :param output_path: Where to save the annotated video.
    :param downscale_width: Downscale width (default 640).
    :param downscale_height: Downscale height (default 480).
    :param skip_frame: If set to N, only every Nth frame is processed/inferred.
    :param write_mode: 
        - "all": Write every frame to the output, with bounding boxes on processed frames, unannotated on skipped ones.
        - "processed": Write only frames that got inference (skipped frames won't appear in the final video).
    """

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: could not open {source}")
        return

    out_width = downscale_width
    out_height = downscale_height

    # Determine input FPS to set for output video
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps_input = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # If "processed" mode is chosen, it might produce a shorter video (since we only write frames that are actually processed).
    # We'll still use the same fps_input to keep consistent timing, but user can adjust if desired.
    writer = cv2.VideoWriter(output_path, fourcc, fps_input, (out_width, out_height))

    frame_count = 0
    start_time = time.time()

    last_print_time = time.time()
    frames_since_last_print = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of stream or read error.")
            break

        frame_count += 1
        frames_since_last_print += 1

        # Downscale if desired
        frame = cv2.resize(frame, (out_width, out_height), interpolation=cv2.INTER_LINEAR)

        # Check if we should run inference on this frame
        do_inference = (frame_count % skip_frame == 0)

        if do_inference:
            # Run YOLO inference
            boxes, scores, labels = run_yolo_inference(frame)

            # Draw bounding boxes
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                score = scores[i]
                label = labels[i]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                text = f"{label}: {score:.2f}"
                cv2.putText(
                    frame,
                    text,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        # Decide whether to write this frame to output
        if write_mode == "all":
            # Always write, even if it's an unprocessed frame
            writer.write(frame)
        else:
            # write_mode == "processed": only write frames that got inference
            if do_inference:
                writer.write(frame)

        # Print performance once per second
        current_time = time.time()
        if current_time - last_print_time >= 1.0:
            elapsed = current_time - last_print_time
            fps = frames_since_last_print / elapsed
            cpu_usage = psutil.cpu_percent()
            print(
                f"Time Interval: {elapsed:.2f}s | "
                f"Processed {frames_since_last_print} frames | "
                f"FPS={fps:.2f} | CPU={cpu_usage:.1f}%"
            )
            last_print_time = current_time
            frames_since_last_print = 0

    cap.release()
    writer.release()
    print(f"Saved annotated video to {output_path}")
