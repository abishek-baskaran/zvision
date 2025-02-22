# test_flow.py

from database import initialize_db, add_store, get_all_stores, add_event
import os

def test_db_insertion():
    # 1. Initialize tables if not already done
    initialize_db()

    # 2. Get or create a test store
    stores = get_all_stores()
    if not stores:
        store_id = add_store("Test Store")
    else:
        store_id = stores[0]["store_id"]

    # 3. Insert a dummy event referencing a future clip path
    event_id = add_event(
        store_id=store_id,
        event_type="entry",
        clip_path="clips/dummy_clip_01.mp4",
        timestamp="2025-02-20 12:00:00"
    )
    print(f"Inserted dummy event (ID={event_id}) into DB.")

if '__name__' == '__main__':
    test_db_insertion()
