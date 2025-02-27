from .stores import initialize_stores_table
from .events import initialize_events_table
from .cameras import initialize_cameras_table
from .calibration import initialize_calibration_table

def initialize_db():
    """
    Initializes all tables in the correct order so foreign keys exist properly.
    """
    initialize_stores_table()       # store_id
    initialize_events_table()       # references stores(store_id)
    initialize_cameras_table()      # references stores(store_id)
    initialize_calibration_table()  # references cameras(camera_id)
