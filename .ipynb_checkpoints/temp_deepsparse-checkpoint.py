from deepsparse import Pipeline

# Specify the path to your YOLOv8 ONNX model
model_path = "yolov8l.onnx"

# Set up the DeepSparse Pipeline
yolo_pipeline = Pipeline.create(task="yolov8", model_path=model_path)

# Run the model on your images
images = ["temp.png"]
pipeline_outputs = yolo_pipeline(images=images)
print(pipeline_outputs)