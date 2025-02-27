from app.database import (
    initialize_db,
    stores,
    cameras,
    calibration
)

initialize_db()

# 1. Create a store
store_id = stores.add_store("My First Store")

# 2. Add a camera
cam_id = cameras.add_camera(store_id, "Front Door Cam")

# 3. Store a calibration line for that camera
calibration.store_calibration(cam_id, 100.0, 200.0, 300.0, 400.0)

# 4. Retrieve it
line_data = calibration.fetch_calibration_for_camera(1)
print("Calibration line:", line_data)
