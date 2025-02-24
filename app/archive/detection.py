import cv2
from ultralytics import YOLO

def load_model(model_path='yolov8n.pt'):
    """
    Loads and returns the YOLO model from Ultralytics.
    Default model is 'yolov8n.pt' (lightweight).
    """
    model = YOLO(model_path)
    return model.to('cpu')

def run_inference(model, image_path):
    """
    Runs inference on the given image and returns detection results.
    """
    results = model(image_path)
    return results

def run_inference_on_video(model, video_path):
    """
    Runs inference on the given video (file path).
    Prints or returns the bounding boxes and class labels for each frame.
    """
    # Example approach:
    results = model.predict(source=video_path, show=False)
    return results


def main_test():
    # 1. Load the model
    model = load_model()

    # 2. Provide a sample image path (ensure the file exists)
    sample_image = "videos/zvision_test.mp4"

    # 3. Run inference
    results = run_inference(model, sample_image)

    # 4. Print or inspect detection outputs
    for result in results:
        # Each 'result' has boxes, class names, etc.
        print("Detections:")
        print(result.boxes)  # bounding boxes
        print(result.names)  # class names
        # You can also visualize:
        # result.show()  # Opens an image window with detections
        annotated_image = result.plot()
        cv2.imwrite("../annotated_result.jpg", annotated_image)

if __name__ == "__main__":
    main_test()
