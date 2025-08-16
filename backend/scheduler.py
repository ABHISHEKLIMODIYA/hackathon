# backend/scheduler.py - Improved Automatic Image Fetch Scheduler

import logging
from datetime import datetime, timedelta
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fetch_satellite import manual_fetch  # [3] - Your fetch function
from notifier import send_email  # [4] - For post-fetch notifications (optional)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

def auto_fetch_images():
    """
    Automatically fetch images:
    - Current: Today's date
    - Previous: 20 days prior
    Retries up to 2 times on failure.
    Optionally triggers detection and sends admin email.
    """
    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        try:
            today = datetime.utcnow().date()
            end_date_str = today.strftime("%Y-%m-%d")
            past_date = today - timedelta(days=20)
            start_date_str = past_date.strftime("%Y-%m-%d")

            logger.info(f"Auto-fetch started (Attempt {attempts + 1}): From {start_date_str} to {end_date_str}")

            manual_fetch(start_date_str, end_date_str)  # Fetch and store images [14]

            logger.info("Auto-fetch completed successfully.")

            # Optional: Trigger detection (call your /api/detect internally)
            # from app import detect
            # detect()  # Or use requests.post('http://localhost:5000/api/detect')

            # Optional: Notify admin via email [4]
            send_email(
                os.getenv("IMC_EMAIL", "admin@example.com"),
                "Bhushuraksha AI: Automatic Image Fetch Completed",
                f"Images fetched for {start_date_str} (previous) and {end_date_str} (current)."
            )

            return True
        except Exception as e:
            attempts += 1
            logger.error(f"Auto-fetch failed (Attempt {attempts}): {e}")
            if attempts >= max_attempts:
                logger.critical("Max retries reached. Fetch aborted.")
                return False

# Schedule to run every 5 days at 00:00 UTC (adjust cron as needed)
scheduler.add_job(
    auto_fetch_images,
    trigger=CronTrigger(day='*/5', hour=0, minute=0),  # Every 5th day
    id='auto_fetch_job',
    name='Automatic Satellite Image Fetch (Every 5 Days)',
    misfire_grace_time=7200,  # Allow 2-hour delay for missed runs
    max_instances=1  # Prevent overlapping runs
)

# Manual trigger function (for API integration)
def manual_scheduler_trigger():
    return auto_fetch_images()

# For standalone testing or cron simulation
if __name__ == "__main__":
    import time
    auto_fetch_images()  # Test run
    while True:  # Keep scheduler alive
        time.sleep(1)
