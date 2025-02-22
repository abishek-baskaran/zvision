import requests

BASE_URL = "http://127.0.0.1:8000/api"

def test_post_events():
    endpoint = f"{BASE_URL}/events"
    payload = {
        "store_id": 1,
        "event_type": "entry",
        "clip_path": "clips/new_clip_99.mp4",
        "timestamp": "2025-02-22 10:30:00"
    }
    response = requests.post(endpoint, json=payload)
    print("POST /events status:", response.status_code)
    print("Response JSON:", response.json())

def test_get_logs():
    endpoint = f"{BASE_URL}/logs"
    params = {
        "store_id": 1
        # You can also add 'start_date', 'end_date', 'event_type', 'limit', etc.
    }
    response = requests.get(endpoint, params=params)
    print("GET /logs status:", response.status_code)
    print("Response JSON:", response.json())

if __name__ == "__main__":
    # 1. Test POST /events
    test_post_events()

    # 2. Test GET /logs
    test_get_logs()
