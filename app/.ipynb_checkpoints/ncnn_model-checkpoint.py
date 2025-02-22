import os
import cv2
import ncnn
import numpy as np

class YOLO_NCNN:
    """
    Minimal YOLO NCNN wrapper that:
      - Loads an NCNN param/bin model from model_dir.
      - Provides a .predict(frame) method returning a list of detections.
    """

    def __init__(self, model_dir, verbose=True):
        self.verbose = verbose
        self.net = ncnn.Net()

        # Construct paths to param/bin files
        param_file = os.path.join(model_dir, "yolov8s.param")
        bin_file = os.path.join(model_dir, "yolov8s.bin")

        if not os.path.exists(param_file) or not os.path.exists(bin_file):
            raise FileNotFoundError(f"Missing NCNN model files in {model_dir}")

        if self.verbose:
            print(f"Loading NCNN model: {param_file}, {bin_file}")

        # Load the model
        self.net.load_param(param_file)
        self.net.load_model(bin_file)

    def predict(self, image):
        """
        Run inference on a single frame (BGR, np.array).
        Returns a list of dicts: [{"bbox": (x,y,w,h), "confidence": float, "class_id": int}, ...].
        """

        # 1) Resize to the model’s expected input size (640×640 here)
        img_resized = cv2.resize(image, (640, 640), interpolation=cv2.INTER_LINEAR)

        # 2) Convert to NCNN Mat
        mat_in = ncnn.Mat.from_pixels_resize(
            img_resized,
            ncnn.Mat.PixelType.PIXEL_BGR,
            640,  # width
            640,  # height
            640,  # target width (same in this example)
            640   # target height (same in this example)
        )

        # 3) Mean / normalization if required (this example normalizes by 1/255.0)
        mean_vals = [0.0, 0.0, 0.0]
        norm_vals = [1 / 255.0, 1 / 255.0, 1 / 255.0]
        mat_in.substract_mean_normalize(mean_vals, norm_vals)

        # 4) Create an NCNN extractor
        ex = self.net.create_extractor()

        # 5) Provide the input (layer name may differ depending on your model)
        ex.input("in0", mat_in)

        # 6) Extract the output (layer name may differ depending on your model)
        ret, mat_out = ex.extract("out0")
        if ret != 0:
            print("NCNN inference failed.")
            return []

        # 7) Convert to NumPy (float32) and ensure shape is (N, 6)
        #    Suppose YOLO-like format: x, y, w, h, conf, class_id
        output_data = np.array(mat_out, dtype=np.float32).reshape(-1, 6)

        detections = []
        for row in output_data:
            x, y, w, h, conf, cls_id = map(float, row)  # Convert each element to a Python float

            # Confidence threshold
            if conf > 0.5:
                detections.append({
                    "bbox": (x, y, w, h),
                    "confidence": conf,
                    "class_id": int(cls_id)
                })

        return detections
