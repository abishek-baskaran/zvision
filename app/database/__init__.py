from app.database.stores import initialize_stores_table
from app.database.events import initialize_events_table
from app.database.cameras import initialize_cameras_table
from app.database.calibration import initialize_calibration_table
from app.database.users import initialize_users_table

def initialize_db():
    """
    Initializes all tables in the correct order so foreign keys exist properly.
    """
    initialize_users_table()
    initialize_stores_table()       # store_id
    initialize_events_table()       # references stores(store_id)
    initialize_cameras_table()      # references stores(store_id)
    initialize_calibration_table()  # references cameras(camera_id)
