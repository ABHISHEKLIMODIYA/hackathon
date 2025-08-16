# backend/configa_h.py
from dotenv import load_dotenv
import os

load_dotenv()

# Validate required environment variables
required_vars = ["SENTINEL_CLIENT_ID", "SENTINEL_CLIENT_SECRET", "MONGO_URI"]
for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing environment variable: {var}")

SENTINEL_CLIENT_ID = os.getenv("SENTINEL_CLIENT_ID")
SENTINEL_CLIENT_SECRET = os.getenv("SENTINEL_CLIENT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "bhushuraksha")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "detections")
INDORE_BBOX =   [75.8895, 22.7525, 75.9150, 22.7700]# Approx bounding box for Indore[75.8, 22.5, 76.1, 23.0]