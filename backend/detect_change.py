# backend/detect_change.py - Improved 10/10 Version

import numpy as np
import cv2
import os
from datetime import datetime
from sklearn.ensemble import IsolationForest
import base64
import logging
import asyncio
from typing import List, Dict, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache  # pip install cachetools
from scipy import ndimage  # For advanced preprocessing
import json  # For GeoJSON

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

mask_cache = TTLCache(maxsize=100, ttl=3600)  # 1-hour cache for masks

class DetectionError(Exception):
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(DetectionError))
def decode_image(image_b64: str) -> np.ndarray:
    try:
        img_data = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise DetectionError("Failed to decode image")
        return img
    except Exception as e:
        logger.error(f"Error decoding image: {e}")
        raise DetectionError(str(e))

def resize_images(img1: np.ndarray, img2: np.ndarray, size: Tuple[int, int] = (512, 512)) -> Tuple[np.ndarray, np.ndarray]:
    return cv2.resize(img1, size), cv2.resize(img2, size)

def align_images(img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
    # Innovation: Feature-based alignment using ORB
    orb = cv2.ORB_create()
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda x: x.distance)
    if len(matches) < 4:
        return img2  # No alignment if too few matches
    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches[:4]])
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches[:4]])
    M, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    return cv2.warpPerspective(img2, M, (img1.shape[1], img1.shape))

def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    return (nir - red) / (nir + red + 1e-6)

def compute_ndbi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    nir = nir / 10000.0
    swir = swir / 10000.0
    return (swir - nir) / (swir + nir + 1e-6)

async def detect_illegal_construction(old_b64: str, new_b64: str, output_dir: str = "static/masks") -> Dict:
    cache_key = f"{old_b64[:50]}_{new_b64[:50]}"  # Partial hash for cache
    if cache_key in mask_cache:
        logger.info(f"Cache hit for detection")
        return mask_cache[cache_key]

    os.makedirs(output_dir, exist_ok=True)
    old_img = decode_image(old_b64)
    new_img = decode_image(new_b64)
    if old_img is None or new_img is None:
        return {"detected": False}

    # Preprocessing: Resize, align, noise reduction
    old_img, new_img = resize_images(old_img, new_img)
    new_img = align_images(old_img, new_img)  # Align new to old
    old_img = cv2.GaussianBlur(old_img, (3,3), 0)  # Denoise
    new_img = cv2.GaussianBlur(new_img, (3,3), 0)

    # Extract bands
    nir_old = old_img[:, :, 3].astype(np.float32)
    red_old = old_img[:, :, 2].astype(np.float32)
    swir_old = old_img[:, :, 4].astype(np.float32)
    nir_new = new_img[:, :, 3].astype(np.float32)
    red_new = new_img[:, :, 2].astype(np.float32)
    swir_new = new_img[:, :, 4].astype(np.float32)

    # Compute indices (SRS F1.3)
    ndvi_old = compute_ndvi(nir_old, red_old)
    ndvi_new = compute_ndvi(nir_new, red_new)
    ndbi_old = compute_ndbi(nir_old, swir_old)
    ndbi_new = compute_ndbi(nir_new, swir_new)

    # Differences
    ndvi_diff = ndvi_new - ndvi_old
    ndbi_diff = ndbi_new - ndbi_old
    features = np.stack([ndvi_diff.flatten(), ndbi_diff.flatten()], axis=1)

    # Anomaly detection with confidence (innovation: decision_function for scores)
    clf = IsolationForest(contamination=0.05, random_state=42)
    clf.fit(features)
    scores = clf.decision_function(features)
    preds = clf.predict(features)
    anomaly_mask = (preds.reshape(ndvi_diff.shape) == -1).astype(np.uint8) * 255

    # Morphology and contours
    kernel = np.ones((5,5), np.uint8)
    anomaly_mask = cv2.morphologyEx(anomaly_mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(anomaly_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        logger.info("No changes detected")
        return {"detected": False}

    # BBox and Polygons for GeoJSON (SRS F2.3)
    x_min, y_min, x_max, y_max = 512, 512, 0, 0
    polygons = []
    for c in contours:
        if cv2.contourArea(c) < 50:
            continue
        x, y, w, h = cv2.boundingRect(c)
        x_min = min(x, x_min)
        y_min = min(y, y_min)
        x_max = max(x + w, x_max)
        y_max = max(y + h, y_max)
        # Polygon approx
        approx = cv2.approxPolyDP(c, 0.01 * cv2.arcLength(c, True), closed=True)
        polygons.append([[pt[0], pt[3]] for pt in approx])

    if x_min >= x_max or y_min >= y_max:
        return {"detected": False}

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    mask_path = os.path.join(output_dir, f"mask_{timestamp}.png")
    cv2.imwrite(mask_path, anomaly_mask)

    # Confidence: Average anomaly score
    confidence = np.mean(scores[preds == -1]) if np.any(preds == -1) else 0

    result = {
        "detected": True,
        "bbox": [x_min, y_min, x_max, y_max],
        "mask_path": mask_path.replace("\\", "/"),
        "timestamp": timestamp,
        "confidence": round(confidence, 2),
        "polygons": polygons,  # For GeoJSON
        "ndvi_diff_mean": np.mean(ndvi_diff),
        "ndbi_diff_mean": np.mean(ndbi_diff)
    }
    mask_cache[cache_key] = result
    logger.info(f"Change detected, mask saved at {mask_path}")
    return result

async def batch_detect(old_b64s: List[str], new_b64s: List[str], output_dir: str = "static/masks") -> List[Dict]:
    tasks = [asyncio.to_thread(detect_illegal_construction, old, new, output_dir) for old, new in zip(old_b64s, new_b64s)]
    return await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    # Test
    sample_b64 = base64.b64encode(np.random.rand(512,512,5).tobytes()).decode()  # Dummy
    result = detect_illegal_construction(sample_b64, sample_b64)
    print(result)
