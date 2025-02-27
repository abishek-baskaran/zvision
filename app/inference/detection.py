# app/inference/detection.py

import cv2
import numpy as np
from ultralytics import YOLO

# Initialize the YOLO model once (or in a factory method) 
# Replace "yolov8l.pt" with your actual model path
_yolo_model = YOLO("yolov8l.pt")

def run_yolo_inference(frame):
    """
    Accepts a BGR image (NumPy array), returns (boxes, scores, labels).
    boxes -> [ [x1, y1, x2, y2], ... ]
    scores -> [ s1, s2, ... ]
    labels -> [ l1, l2, ... ]
    """
    results = _yolo_model.predict(source=frame)
    yolo_result = results[0]

    xyxy = yolo_result.boxes.xyxy.cpu().numpy()  # shape: (num_det, 4)
    conf = yolo_result.boxes.conf.cpu().numpy()  # shape: (num_det,)
    cls  = yolo_result.boxes.cls.cpu().numpy()   # shape: (num_det,)

    boxes, scores, labels = [], [], []
    for i in range(len(xyxy)):
        x1, y1, x2, y2 = xyxy[i]
        boxes.append([int(x1), int(y1), int(x2), int(y2)])
        scores.append(float(conf[i]))
        labels.append(int(cls[i]))

    return boxes, scores, labels
