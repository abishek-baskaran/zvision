import requests
import json
import cv2
import numpy as np
import os
import sys

BASE_URL = "http://127.0.0.1:8000/api"

def main():
    # 1) CREATE A STORE
    print("\n=== Creating Store ===")
    store_data = {"store_name": "Test Store (SSH mode)"}
    resp = requests.post(f"{BASE_URL}/stores", json=store_data)
    if resp.status_code != 200:
        print("Failed to create store:", resp.text)
        return
    store_json = resp.json()
    store_id = store_json["store_id"]
    print("Created store with ID:", store_id)

    # 2) CREATE A CAMERA
    print("\n=== Creating Camera ===")
    camera_data = {
        "store_id": store_id,
        "camera_name": "SSH Test Camera",
        "source": "videos/source/cam_test.mp4"
    }
    resp = requests.post(f"{BASE_URL}/cameras", json=camera_data)
    if resp.status_code != 200:
        print("Failed to create camera:", resp.text)
        return
    camera_json = resp.json()
    camera_id = camera_json["camera_id"]
    print("Created camera with ID:", camera_id)

    # 3) GET SNAPSHOT & SAVE LOCALLY
    print("\n=== Fetching Snapshot ===")
    snapshot_url = f"{BASE_URL}/camera/{camera_id}/snapshot"
    snapshot_resp = requests.get(snapshot_url)
    if snapshot_resp.status_code != 200:
        print("Failed to get snapshot:", snapshot_resp.text)
        return

    snapshot_filename = "snapshot.jpg"
    with open(snapshot_filename, "wb") as f:
        f.write(snapshot_resp.content)

    print(f"Snapshot saved to '{snapshot_filename}'.")
    print("If you are on a purely headless SSH, you can:")
    print("  1) SCP this file to your local machine: scp pi@<your-pi-ip>:/home/pi/zvision/snapshot.jpg .")
    print("  2) Open snapshot.jpg in an image viewer locally.")
    print("  3) Inspect the image to find your line and rectangle corners.")
    print("  4) Then type the coords here.\n")

    # 4) ASK USER FOR CALIBRATION VALUES
    print("Enter LINE coordinates (start_x,start_y,end_x,end_y).")
    line_str = input("  For example, '100,200,300,400': ")
    lx1, ly1, lx2, ly2 = [float(x.strip()) for x in line_str.split(",")]

    print("\nEnter RECT (square) top-left and bottom-right corners.")
    rect_str = input("  For example, '50,50,400,400': ")
    rx1, ry1, rx2, ry2 = [float(x.strip()) for x in rect_str.split(",")]

    # 5) POST CALIBRATION (line + square) to /calibrate
    print("\n=== Sending Calibration Data ===")
    calibrate_data = {
        "camera_id": str(camera_id),
        "line": {
            "start": [lx1, ly1],
            "end":   [lx2, ly2]
        },
        "square": {
            "top_left":     [rx1, ry1],
            "bottom_right": [rx2, ry2]
        }
    }
    resp = requests.post(f"{BASE_URL}/calibrate", json=calibrate_data)
    if resp.status_code != 200:
        print("Failed to calibrate camera:", resp.text)
        return
    print("Calibration response:", resp.json())

    # 5b) LOAD SNAPSHOT & DRAW BOXES ON IT
    annotated_filename = "annotated_snapshot.jpg"
    image = cv2.imread(snapshot_filename)
    if image is None:
        print("Failed to load the snapshot for annotation.")
    else:
        # Convert to int so OpenCV can handle them
        lx1_i, ly1_i = int(lx1), int(ly1)
        lx2_i, ly2_i = int(lx2), int(ly2)
        rx1_i, ry1_i = int(rx1), int(ry1)
        rx2_i, ry2_i = int(rx2), int(ry2)

        # Draw the rectangle in GREEN (0,255,0) and the line in RED (0,0,255)
        cv2.rectangle(image, (rx1_i, ry1_i), (rx2_i, ry2_i), (0,255,0), 2)
        cv2.line(image, (lx1_i, ly1_i), (lx2_i, ly2_i), (0,0,255), 2)

        # Save the annotated image
        cv2.imwrite(annotated_filename, image)
        print(f"Annotated snapshot saved to '{annotated_filename}'.")

    # 6) RUN DETECTION
    print("\n=== Running Detection ===")
    detect_data = {"camera_id": str(camera_id)}
    resp = requests.post(f"{BASE_URL}/detect", json=detect_data)
    if resp.status_code not in (200, 201):
        print("Failed to detect:", resp.text)
        return
    print("Detection result:", resp.json())

    # 7) FETCH LOGS
    print("\n=== Fetching Logs ===")
    logs_url = f"{BASE_URL}/logs?store_id={store_id}"
    resp = requests.get(logs_url)
    if resp.status_code != 200:
        print("Failed to fetch logs:", resp.text)
        return
    logs_json = resp.json()
    print("Logs response:", json.dumps(logs_json, indent=2))

if __name__ == "__main__":
    main()
