from app.inference.pipeline import process_camera_stream

process_camera_stream(
    source="videos/source/zvision_test_1.mp4",
    output_path="videos/annotated/test1_annot.mp4",
    camera_id="1"
)