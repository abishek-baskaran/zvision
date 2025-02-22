import os
import sys
import time
import cv2
import numpy as np
import ncnn


class YOLOv8NCNN:
    def __init__(
        self,
        param_path,
        bin_path,
        target_size=(640, 640),
        conf_threshold=0.25,
        nms_threshold=0.45,
        num_classes=80,
        use_gpu=False
    ):
        self.net = ncnn.Net()
        self.net.opt.use_vulkan_compute = use_gpu

        # >>> Set threads BEFORE load_param <<<
        self.net.opt.num_threads = 4  # or whatever you want

        self.net.load_param(param_path)
        self.net.load_model(bin_path)

        self.target_size = target_size
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.num_classes = num_classes

        # >>> Match these to your param file <<<
        self.input_name = "in0"
        self.output_name = "out0"

    def detect(self, bgr_img):
        orig_h, orig_w = bgr_img.shape[:2]

        # Letterbox
        new_w, new_h = self.target_size
        scale = min(new_w / orig_w, new_h / orig_h)
        resized_w = int(orig_w * scale)
        resized_h = int(orig_h * scale)

        resized = cv2.resize(bgr_img, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((new_h, new_w, 3), 114, dtype=np.uint8)
        top = (new_h - resized_h) // 2
        left = (new_w - resized_w) // 2
        canvas[top:top+resized_h, left:left+resized_w] = resized

        # BGR -> RGB
        ncnn_input = ncnn.Mat.from_pixels(
            canvas,
            ncnn.Mat.PixelType.PIXEL_BGR2RGB,
            new_w,
            new_h
        )
        mean_vals = [0.0, 0.0, 0.0]
        norm_vals = [1 / 255.0, 1 / 255.0, 1 / 255.0]
        ncnn_input.substract_mean_normalize(mean_vals, norm_vals)

        ex = self.net.create_extractor()
        # ex.set_num_threads(4)  # No-op in recent ncnn. Already done via self.net.opt.num_threads

        # >>> Use the actual input name from your param file <<<
        ex.input(self.input_name, ncnn_input)

        # >>> Use the actual output name(s) from your param file <<<
        ret, ncnn_output = ex.extract(self.output_name)
        if ret != 0:
            print("extract failed, check output name!")
            return []

        data = np.array(ncnn_output, dtype=np.float32).reshape(-1, self.num_classes + 5)

        # Post-process
        boxes = []
        for row in data:
            box_conf = row[4]
            class_scores = row[5:]
            class_id = np.argmax(class_scores)
            class_conf = class_scores[class_id]
            score = box_conf * class_conf
            if score > self.conf_threshold:
                cx, cy, w, h = row[0:4]
                x0 = cx - w * 0.5
                y0 = cy - h * 0.5
                x1 = cx + w * 0.5
                y1 = cy + h * 0.5

                # Reverse letterbox
                scale_for_o = 1 / scale
                x0 = (x0 - left) * scale_for_o
                y0 = (y0 - top) * scale_for_o
                x1 = (x1 - left) * scale_for_o
                y1 = (y1 - top) * scale_for_o

                boxes.append([x0, y0, x1, y1, float(score), class_id])

        boxes = self.non_max_suppression(boxes)
        return boxes

    def non_max_suppression(self, boxes):
        boxes = sorted(boxes, key=lambda x: x[4], reverse=True)
        filtered = []
        for box in boxes:
            keep = True
            for fb in filtered:
                if box[5] == fb[5]:
                    iou_val = self.iou(box, fb)
                    if iou_val > self.nms_threshold:
                        keep = False
                        break
            if keep:
                filtered.append(box)
        return filtered

    @staticmethod
    def iou(b1, b2):
        x0 = max(b1[0], b2[0])
        y0 = max(b1[1], b2[1])
        x1 = min(b1[2], b2[2])
        y1 = min(b1[3], b2[3])
        inter = max(0, x1 - x0) * max(0, y1 - y0)
        area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
        area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
        return inter / (area1 + area2 - inter + 1e-16)



class Counter:
    def __init__(
        self,
        ncnn_param="app/yolov8s_ncnn_model/yolov8s.param",
        ncnn_bin="app/yolov8s_ncnn_model/yolov8s.bin",
        downscale_width=320,
        downscale_height=240,
        output_fps=20,
        skip_plot_frames=10,
        use_gpu=False,
        target_classes=None
    ):
        """
        Processes video or RTSP streams with YOLOv8 (ncnn version).
        
        :param ncnn_param: Path to YOLOv8 ncnn .param file.
        :param ncnn_bin: Path to YOLOv8 ncnn .bin file.
        :param downscale_width: Width to which frames will be resized before saving.
        :param downscale_height: Height to which frames will be resized before saving.
        :param output_fps: FPS for the output annotated video.
        :param skip_plot_frames: Draw bounding boxes every N frames. If 0, draws on every frame.
        :param use_gpu: If True, attempt to enable Vulkan GPU in ncnn (must be compiled).
        :param target_classes: List of class IDs to keep. If None, do not filter by class.
        """
        print(f"Loading ncnn model:\n  param={ncnn_param}\n  bin={ncnn_bin}")
        # Adjust your target_size, conf_thresh, nms_thresh as needed
        self.model = YOLOv8NCNN(
            param_path=ncnn_param,
            bin_path=ncnn_bin,
            target_size=(640, 640),  # Typical YOLOv8 input size
            conf_threshold=0.25,
            nms_threshold=0.45,
            num_classes=80,         # Or the correct number for your model
            use_gpu=use_gpu
        )

        self.downscale_width = downscale_width
        self.downscale_height = downscale_height
        self.output_fps = output_fps
        self.skip_plot_frames = skip_plot_frames

        if target_classes is None:
            self.target_classes = []
        else:
            self.target_classes = target_classes
            print(f"Filtering to classes={self.target_classes}")

    def process_stream(self, source: str, output_path: str):
        """
        Reads frames from `source`, runs detection, and writes annotated frames to `output_path`.
        """
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"Error: cannot open video source {source}")
            return

        # Prepare VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, self.output_fps,
                                 (self.downscale_width, self.downscale_height))

        print(f"\nProcessing: {source}")
        print(f"Output: {output_path} at {self.output_fps} FPS")
        print(f"Downscaled to: {self.downscale_width}x{self.downscale_height}")
        if self.target_classes:
            print(f"Only keeping class IDs: {self.target_classes}")

        frame_count = 0
        start_time = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                print("End of stream or unable to read frame.")
                break

            frame_count += 1

            # Resize frame if you want the output to be smaller
            frame_resized = cv2.resize(
                frame, 
                (self.downscale_width, self.downscale_height),
                interpolation=cv2.INTER_LINEAR
            )

            # Run detection on the (original or resized) frame
            # In this example, we run it on the original frame for better accuracy,
            # but you can also run it on `frame_resized` if you prefer speed.
            detections = self.model.detect(frame)

            # Optionally filter detections by target_classes
            if self.target_classes:
                detections = [d for d in detections if int(d[5]) in self.target_classes]

            # Decide whether to plot bounding boxes
            if self.skip_plot_frames == 0:
                do_plot = True
            else:
                do_plot = (frame_count % self.skip_plot_frames == 0)

            annotated_frame = frame_resized.copy()
            if do_plot:
                # Draw bounding boxes on the *output* frame (frame_resized).
                # We need to scale bounding boxes from original to the downscaled size.
                scale_x = self.downscale_width / frame.shape[1]
                scale_y = self.downscale_height / frame.shape[0]

                for det in detections:
                    x0, y0, x1, y1, score, class_id = det
                    x0_out = int(x0 * scale_x)
                    y0_out = int(y0 * scale_y)
                    x1_out = int(x1 * scale_x)
                    y1_out = int(y1 * scale_y)

                    cv2.rectangle(annotated_frame, (x0_out, y0_out), (x1_out, y1_out),
                                  (0, 255, 0), 2)
                    cv2.putText(
                        annotated_frame,
                        f"cls:{int(class_id)} {score:.2f}",
                        (x0_out, max(0, y0_out - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1
                    )

            # Debug FPS
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            print(f"  Frame {frame_count} - {len(detections)} detections. FPS: {fps:.2f}")

            # Write annotated frame
            writer.write(annotated_frame)

            time.sleep(0.01)

        cap.release()
        writer.release()
        print("Finished processing stream.")


if __name__ == "__main__":
    """
    Main block:
     1. Reads all files from 'videos/source/' folder.
     2. Checks if there's a corresponding file in 'videos/annotated/'.
     3. If the annotated file exists, asks user to [R]eplace or [I]gnore.
     4. Process only if user chooses to replace or if no existing file is found.
    """
    source_folder = "videos/source"
    annotated_folder = "videos/annotated"

    os.makedirs(source_folder, exist_ok=True)
    os.makedirs(annotated_folder, exist_ok=True)

    # Initialize Counter with your ncnn param/bin
    counter = Counter(
        ncnn_param="app/yolov8s_ncnn_model/yolov8s.param",
        ncnn_bin="app/yolov8s_ncnn_model/yolov8s.bin",
        downscale_width=640,
        downscale_height=480,
        output_fps=20,
        skip_plot_frames=0,   # draw boxes on every frame
        use_gpu=False,        # set True if your ncnn supports Vulkan on Pi
        target_classes=[0]    # for example, class 0 for person
    )

    # Gather source files
    source_files = sorted(f for f in os.listdir(source_folder)
                          if f.lower().endswith(('.mp4', '.mov', '.avi')))
    if not source_files:
        print(f"No video files found in {source_folder}.")
        sys.exit(0)

    for src_file in source_files:
        src_path = os.path.join(source_folder, src_file)
        # We'll name the annotated file similarly but in 'videos/annotated' folder
        annotated_filename = os.path.splitext(src_file)[0] + "_annotated.mp4"
        annotated_path = os.path.join(annotated_folder, annotated_filename)

        if os.path.exists(annotated_path):
            print(f"\nAnnotated file '{annotated_path}' already exists.")
            choice = input("Replace [R] or Ignore [I]? (default I): ").strip().lower()
            if choice != 'r':
                print("  Ignoring and moving to next file.")
                continue
            else:
                print("  Replacing existing file...")

        # Process
        counter.process_stream(src_path, annotated_path)

    print("\nAll done.")
