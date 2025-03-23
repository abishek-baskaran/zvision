import requests

url = "http://localhost:8000/api/calibrate"

payload = {
    "camera_id": "1",
    "line": {"start": [1000, 2000], "end": [3000, 4000]}
}

headers = {"Content-Type": "application/json"}

response = requests.post(url, json=payload, headers=headers)

print(response.status_code)
print(response.json())
