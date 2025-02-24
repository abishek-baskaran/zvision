import os
import cv2
from ultralytics import YOLO

def annotate_videos_with_ultralytics(
    source_dir="videos/source",
    output_dir="videos/annotated",
    model_path="yolov8l.pt"
):
    # Create the YOLO model
    model = YOLO(model_path)

    # Ensure our output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Loop over each video in the source directory
    for file_name in os.listdir(source_dir):
        if not file_name.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            continue  # Skip non-video files

        input_path = os.path.join(source_dir, file_name)
        output_path = os.path.join(output_dir, file_name)

        # Open video capture
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            print(f"Could not open video {input_path}, skipping...")
            continue

        # Prepare output video writer
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Run inference on the current frame
            # results is a list of 'Results' objects, one for each image processed
            results = model(frame)  
            
            # We'll take the first (and only) 'Results' object for our single frame
            result = results[0]

            # result.boxes is a 'Boxes' object with .xyxy, .conf, .cls, etc.
            frame_boxes = result.boxes.xyxy  # shape: (num_detections, 4)
            frame_scores = result.boxes.conf # shape: (num_detections,)
            frame_labels = result.boxes.cls   # shape: (num_detections,)

            # Draw bounding boxes and labels on the frame
            for i in range(len(frame_boxes)):
                x1, y1, x2, y2 = map(int, frame_boxes[i])
                score = float(frame_scores[i])
                label = int(frame_labels[i])

                # Draw the box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Annotate with class (numeric ID) and confidence
                label_text = f"{label}: {score:.2f}"
                cv2.putText(
                    frame,
                    label_text,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

            # Write the annotated frame to our output video
            out.write(frame)

        cap.release()
        out.release()
        print(f"Annotated video saved to: {output_path}")

if __name__ == "__main__":
    annotate_videos_with_ultralytics()
    print("All videos processed and annotated.")
