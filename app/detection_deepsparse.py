import cv2
from ultralytics import YOLO

# Initialize the YOLO model (replace 'yolov8l.pt' with your actual model path if different)
yolo_model = YOLO("./checkpoints/yolov8l.onnx")

def run_yolo_inference(frame):
    """
    Accepts a BGR image (NumPy array), returns (boxes, scores, labels).
    boxes -> [ [x1, y1, x2, y2], ... ]
    scores -> [ s1, s2, ... ]
    labels -> [ l1, l2, ... ] (class IDs)
    """

    # Run inference on the input frame
    # Using model.predict for a single image
    results = yolo_model.predict(source=frame, device='cpu')

    # Typically, results is a list of Result objects (one per image if you're in batch mode)
    # We'll assume single-image so results[0] is our detection output
    yolo_result = results[0]

    # 'yolo_result.boxes' contains bounding boxes, class IDs, confidences, etc.
    # We can extract them as Tensors and convert to lists
    xyxy = yolo_result.boxes.xyxy.cpu().numpy()  # shape: (num_detections, 4)
    conf = yolo_result.boxes.conf.cpu().numpy()  # shape: (num_detections,)
    cls  = yolo_result.boxes.cls.cpu().numpy()   # shape: (num_detections,)

    boxes, scores, labels = [], [], []

    for i in range(len(xyxy)):
        x1, y1, x2, y2 = xyxy[i]
        score = float(conf[i])
        label = int(cls[i])
        boxes.append([int(x1), int(y1), int(x2), int(y2)])
        scores.append(score)
        labels.append(label)

    return boxes, scores, labels
