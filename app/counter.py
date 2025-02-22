import os
import cv2
from deepsparse import Pipeline

def annotate_videos_with_deepsparse_legacy(
    source_dir="videos/source",
    output_dir="videos/annotated",
    model_path="checkpoints/yolov8l.onnx"
):
    # Create the DeepSparse pipeline
    # Legacy fallback still works with task="yolov8"
    # (or "yolo"), but it returns data as attributes, not a dictionary.
    yolo_pipeline = Pipeline.create(task="yolov8", model_path=model_path)

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
            # The legacy pipeline returns an object with .boxes, .scores, .labels, etc.
            outputs = yolo_pipeline(images=[frame])  # a single result for 1 image

            # Each attribute is a list of length=number_of_images; index [0] for our single frame
            # boxes is shape: [num_detections, 4]
            # scores is shape: [num_detections]
            # labels is shape: [num_detections]
            frame_boxes = outputs.boxes[0]   # e.g. [[x1, y1, x2, y2], [...], ...]
            frame_scores = outputs.scores[0] # e.g. [score1, score2, ...]
            frame_labels = outputs.labels[0] # e.g. [class_id1, class_id2, ...]

            # Draw bounding boxes and labels on the frame
            for i, box in enumerate(frame_boxes):
                x1, y1, x2, y2 = map(int, box)
                score = frame_scores[i]
                label = frame_labels[i]  # can cast to int if you prefer

                # Draw the box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Annotate with class and confidence
                label_text = f"{int(label)}: {score:.2f}"
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
    annotate_videos_with_deepsparse_legacy()
    print("All videos processed and annotated.")
