# zvision: Basic Server Structure

## How to Run the FastAPI Server

1. Activate your Python environment:
   conda activate zvision

2. Navigate to the 'app' directory (or wherever main.py is located):
   cd zvision/app

3. Launch the server:
   uvicorn main:app --reload

4. Test the health-check endpoint:
   Open your browser at http://127.0.0.1:8000/ping
   You should see: {"status": "ok"}

## Next Steps
- Implement the /detect route to accept image data and run YOLO detection.
- Add calibration logic in /calibrate.
- Integrate with the detection.py module for real inference.
