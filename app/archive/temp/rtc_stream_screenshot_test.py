import asyncio
import aiohttp
import cv2
import numpy as np
import uuid
from aiortc import RTCPeerConnection, RTCSessionDescription
import logging
import os

# Configurations (Update accordingly)
API_URL = "http://localhost:8000/api"
CAMERA_ID = 1
USERNAME = "admin"
PASSWORD = "123456"
FRAME_INTERVAL = 5      # Take a screenshot every 5 frames
OUTPUT_DIR = "./screenshots"

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc_test")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def get_token(session):
    token_url = f"{API_URL}/token"
    logger.info("Fetching JWT token...")
    data = {"username": USERNAME, "password": PASSWORD}
    async with session.post(token_url, data=data) as resp:
        resp.raise_for_status()
        result = await resp.json()
        token = result.get("access_token")
        if not token:
            raise Exception("No token in response")
        logger.info("Successfully obtained JWT token")
        return token

async def fetch_answer(session, connection_id, token):
    answer_url = f"{API_URL}/rtc/answer/{connection_id}?token={token}"
    logger.info(f"Fetching SDP answer from: {answer_url}")
    for _ in range(10):
        async with session.get(answer_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info("Answer received.")
                return data["answer"]
            elif resp.status == 202:
                logger.info("Answer pending...retrying in 1s")
                await asyncio.sleep(1)
            else:
                raise Exception(f"Failed to get answer: {resp.status}")
    raise Exception("Unable to fetch SDP answer.")

async def send_offer(session, sdp_offer, token):
    offer_url = f"{API_URL}/rtc/offer/{CAMERA_ID}?token={token}"
    logger.info(f"Sending SDP offer to: {offer_url}")
    payload = {"sdp": sdp_offer, "type": "offer"}
    async with session.post(offer_url, json=payload) as resp:
        resp.raise_for_status()
        data = await resp.json()
        logger.info(f"Offer accepted. Connection ID: {data['connection_id']}")
        return data["connection_id"]

async def capture_frames(track):
    logger.info("Starting frame capture...")
    frame_count = 0
    screenshot_count = 0

    while True:
        frame = await track.recv()
        frame_count += 1

        if frame_count % FRAME_INTERVAL == 0:
            img = frame.to_ndarray(format="bgr24")
            screenshot_count += 1
            filename = os.path.join(OUTPUT_DIR, f"screenshot_{screenshot_count}.jpg")
            cv2.imwrite(filename, img)
            logger.info(f"Saved screenshot: {filename}")

async def run():
    pc = RTCPeerConnection()
    pc.addTransceiver("video", direction="recvonly")

    @pc.on("track")
    def on_track(track):
        logger.info(f"Received track: {track.kind}")
        if track.kind == "video":
            asyncio.ensure_future(capture_frames(track))

    async with aiohttp.ClientSession() as session:
        token = await get_token(session)
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        connection_id = await send_offer(session, pc.localDescription.sdp, token)
        answer = await fetch_answer(session, connection_id, token)
        rtc_answer = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
        await pc.setRemoteDescription(rtc_answer)

        # Keep running indefinitely
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run())