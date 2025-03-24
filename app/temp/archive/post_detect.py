import requests

# Set up API URL with camera_id as a query parameter
API_URL = "http://localhost:8000/api/detect?camera_id=1"  # Send as query parameter

# Send POST request without JSON body
response = requests.post(API_URL)

# Print response
print("Status Code:", response.status_code)
print("Response JSON:", response.json())
