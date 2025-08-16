# backend/fetch_satellite.py - Improved 10/10 Version

import os
import logging
import base64
from datetime import datetime
import numpy as np
import cv2
import asyncio
import aiohttp
from typing import Tuple, List
from pymongo import MongoClient
from configa_h import SENTINEL_CLIENT_ID, SENTINEL_CLIENT_SECRET, MONGO_URI, DB_NAME, COLLECTION_NAME, INDORE_BBOX  # [3][4]
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache  # pip install cachetools

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

token_cache = TTLCache(maxsize=1, ttl=3500)  # Token valid ~1 hour
image_cache = TTLCache(maxsize=100, ttl=86400)  # 1 day for images

class APIError(Exception):
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(APIError))
async def get_access_token() -> str:
    if 'token' in token_cache:
        return token_cache['token']
    try:
        url = "https://services.sentinel-hub.com/oauth/token"
        data = {
            "client_id": SENTINEL_CLIENT_ID,
            "client_secret": SENTINEL_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                response.raise_for_status()
                token = (await response.json()).get("access_token")
                if not token:
                    raise APIError("No access token received")
                token_cache['token'] = token
                logger.info("Obtained Sentinel-2 access token")
                return token
    except Exception as e:
        logger.error(f"Failed to get token: {e}")
        raise APIError(str(e))

def validate_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

async def fetch_image(date: str, token: str, bbox: List[float] = INDORE_BBOX) -> Tuple[str, str]:
    cache_key = f"{date}_{'_'.join(map(str, bbox))}"
    if cache_key in image_cache:
        logger.info(f"Cache hit for {cache_key}")
        return image_cache[cache_key]

    url = "https://services.sentinel-hub.com/api/v1/process"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "input": {
            "bounds": {"bbox": bbox},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {
                "timeRange": {"from": f"{date}T00:00:00Z", "to": f"{date}T23:59:59Z"},
                "maxCloudCoverage": 20
            }}]
        },
        "output": {"width": 512, "height": 512, "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
        "evalscript": """
        //VERSION=3
        function setup() { return { input: ["B02", "B03", "B04", "B08", "B11"], output: { bands: 5, sampleType: "UINT16" } }; }
        function evaluatePixel(sample) { return [sample.B02, sample.B03, sample.B04, sample.B08, sample.B11]; }
        """
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Sentinel-2 error: {error_text}")
                    raise APIError(error_text)
                raw_bytes = await response.read()

        # Decode and preprocess (SRS F1.2-F1.3)
        nparr = np.frombuffer(raw_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise APIError("Failed to decode TIFF")

        # Preprocess: Normalize, compute NDVI/NDBI (innovation: store precomputed indices)
        img = cv2.resize(img, (512, 512))  # Align/crop to standard size
        img = img.astype(np.float32) / 10000.0  # Normalize reflectance
        nir = img[:,:,3]  # B08
        red = img[:,:,2]  # B04
        swir = img[:,:,4]  # B11
        ndvi = (nir - red) / (nir + red + 1e-6)
        ndbi = (swir - nir) / (swir + nir + 1e-6)

        # RGB for display
        rgb = np.stack([img[:,:,2], img[:,:,1], img[:,:,0]], axis=-1) * 3.5 * 255
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        _, png_buffer = cv2.imencode('.png', rgb)
        display_bytes = png_buffer.tobytes()

        raw_b64 = base64.b64encode(raw_bytes).decode("utf-8")
        display_b64 = base64.b64encode(display_bytes).decode("utf-8")

        result = (raw_b64, display_b64, {"ndvi_mean": np.mean(ndvi), "ndbi_mean": np.mean(ndbi)})  # Store indices
        image_cache[cache_key] = result
        logger.info(f"Fetched and preprocessed image for {date}")
        return result
    except Exception as e:
        raise APIError(str(e))

async def batch_fetch_images(dates: List[str], token: str, bbox: List[float] = INDORE_BBOX) -> List[Tuple[str, str]]:
    tasks = [fetch_image(date, token, bbox) for date in dates]
    return await asyncio.gather(*tasks, return_exceptions=True)

def manual_fetch(start_date: str, end_date: str, bbox: List[float] = INDORE_BBOX):
    if not (validate_date(start_date) and validate_date(end_date)):
        raise ValueError("Invalid date format, use YYYY-MM-DD")
    if datetime.strptime(start_date, "%Y-%m-%d") >= datetime.strptime(end_date, "%Y-%m-%d"):
        raise ValueError("Start date must be before end date")

    token = asyncio.run(get_access_token())
    if not token:
        # Fallback: Demo images (base64 placeholders)
        logger.warning("Using demo images due to token failure")
        demo_raw = base64.b64encode(b'demo_raw_data').decode("utf-8")
        demo_display = base64.b64encode(b'demo_display_data').decode("utf-8")
        old_raw, old_display = demo_raw, demo_display
        new_raw, new_display = demo_raw, demo_display  # Same for demo
    else:
        (old_raw, old_display, old_indices), (new_raw, new_display, new_indices) = asyncio.run(batch_fetch_images([start_date, end_date], token, bbox))

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    coll = db[COLLECTION_NAME]

    coll.insert_one({
        "tag": "manual_old",
        "raw_image": old_raw,
        "display_image": old_display,
        "indices": old_indices if 'old_indices' in locals() else {},  # Store precomputed
        "timestamp": datetime.strptime(start_date, "%Y-%m-%d"),
        "location": "Indore, MP",
        "bbox": bbox
    })
    coll.insert_one({
        "tag": "manual_new",
        "raw_image": new_raw,
        "display_image": new_display,
        "indices": new_indices if 'new_indices' in locals() else {},
        "timestamp": datetime.strptime(end_date, "%Y-%m-%d"),
        "location": "Indore, MP",
        "bbox": bbox
    })
    logger.info(f"Stored images for {start_date} (old) and {end_date} (new)")

if __name__ == "__main__":
    # Test
    manual_fetch("2025-07-01", "2025-07-20")
