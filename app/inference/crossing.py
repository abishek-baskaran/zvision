from typing import List, Tuple, Dict
from datetime import datetime
from app.database.cameras import get_store_for_camera
from app.database.events import add_event

def compute_side_of_line(px: float, py: float,
                         x1: float, y1: float, x2: float, y2: float) -> int:
    """
    Returns +1 or -1 depending on which side of the line (x1,y1)->(x2,y2) the point (px,py) is on.
    0 if exactly on the line.
    """
    vx = x2 - x1
    vy = y2 - y1
    dx = px - x1
    dy = py - y1
    cross = vx * dy - vy * dx
    if cross > 0:
        return +1
    elif cross < 0:
        return -1
    else:
        return 0

def find_closest_center(cx: float, cy: float, old_centers: List[Tuple[float, float, int]], max_dist=50.0):
    """
    Return old center within max_dist, or None if none close enough.
    old_centers is a list of (oldCx, oldCy, oldSide).
    """
    best_center = None
    best_dist = max_dist
    for (ocx, ocy, oside) in old_centers:
        dist = ((cx - ocx)**2 + (cy - ocy)**2)**0.5
        if dist < best_dist:
            best_dist = dist
            best_center = (ocx, ocy, oside)
    return best_center

def check_line_crossings(
    this_frame_centers, old_centers, line_data, entry_count, exit_count, camera_id_int, orientation="leftToRight"
):
    """
    Compare new centers to old centers, checking if side changed across the line.
    Return updated (entry_count, exit_count).
    Additionally, log the crossing event to the DB if desired.
    
    orientation: "leftToRight" or "rightToLeft" - changes which direction is considered entry vs exit
    """

    if not old_centers:
        return entry_count, exit_count

    x1 = line_data["line_start_x"]
    y1 = line_data["line_start_y"]
    x2 = line_data["line_end_x"]
    y2 = line_data["line_end_y"]

    # Get store_id once, reuse it
    try:
        store_id = get_store_for_camera(camera_id_int)
    except ValueError as e:
        print(f"Warning: {e}, cannot log events.")
        store_id = None

    for (cx, cy) in this_frame_centers:
        old_center = find_closest_center(cx, cy, old_centers)
        if old_center is None:
            continue

        (ocx, ocy, old_side) = old_center
        if old_side is None:
            old_side = compute_side_of_line(ocx, ocy, x1, y1, x2, y2)
        new_side = compute_side_of_line(cx, cy, x1, y1, x2, y2)

        if old_side != 0 and new_side != 0 and old_side != new_side:
            # crossing occurred
            event_type = None
            
            # Default orientation (leftToRight):
            # - going from +1 to -1 means entry
            # - going from -1 to +1 means exit
            if orientation == "leftToRight":
                if old_side < 0 and new_side > 0:
                    exit_count += 1
                    event_type = "exit"
                elif old_side > 0 and new_side < 0:
                    entry_count += 1
                    event_type = "entry"
            # Reversed orientation (rightToLeft):
            # - going from +1 to -1 means exit
            # - going from -1 to +1 means entry
            elif orientation == "rightToLeft":
                if old_side < 0 and new_side > 0:
                    entry_count += 1
                    event_type = "entry"
                elif old_side > 0 and new_side < 0:
                    exit_count += 1
                    event_type = "exit"

            # If store_id was found, log the event
            if store_id and event_type:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # e.g., we might set clip_path to empty or a known file
                clip_path = "annotated_clip.mp4"
                add_event(store_id, event_type, clip_path, now_str)

    return entry_count, exit_count
