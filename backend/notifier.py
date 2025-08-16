# backend/notifier.py - Improved 10/10 Version

from datetime import datetime
import os
import smtplib
import json
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
import requests
import threading
from queue import PriorityQueue, Empty
from twilio.rest import Client  # For SMS
from tenacity import retry, stop_after_attempt, wait_fixed  # pip install tenacity

logger = logging.getLogger(__name__)

# Env vars
IMC_EMAIL = os.getenv("IMC_EMAIL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
IMC_WEBHOOK_URL = os.getenv("IMC_WEBHOOK_URL", "")
TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "")  # e.g., +1234567890

# Priority queue for async notifications (high priority first)
notify_queue = PriorityQueue()

# Twilio client
twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN) if TWILIO_SID and TWILIO_AUTH_TOKEN else None

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def send_email(to_email: str, subject: str, html_body: str) -> bool:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and to_email):
        logger.warning("Email config incomplete. Skipping.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def send_sms(to_phone: str, message: str) -> bool:
    if not (twilio_client and TWILIO_PHONE and to_phone):
        logger.warning("SMS config incomplete. Skipping.")
        return False
    try:
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=to_phone
        )
        logger.info(f"SMS sent to {to_phone}")
        return True
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def send_webhook(payload: dict) -> bool:
    if not IMC_WEBHOOK_URL:
        logger.warning("Webhook URL not set. Skipping.")
        return False
    try:
        r = requests.post(IMC_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code // 100 == 2:
            logger.info("Webhook sent successfully")
            return True
        logger.error(f"Webhook failed: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise

def process_notify_queue():
    while True:
        try:
            priority, task = notify_queue.get(timeout=1)
            if task['type'] == 'email':
                send_email(task['to'], task['subject'], task['body'])
            elif task['type'] == 'sms':
                send_sms(task['to'], task['message'])
            elif task['type'] == 'webhook':
                send_webhook(task['payload'])
            notify_queue.task_done()
        except Empty:
            pass  # Queue empty, continue looping

# Start background thread for queue processing
threading.Thread(target=process_notify_queue, daemon=True).start()

# Enqueue functions (priority: 1=high, 2=medium, 3=low)
def enqueue_email(to: str, subject: str, body: str, priority: int = 2):
    notify_queue.put((priority, {'type': 'email', 'to': to, 'subject': subject, 'body': body}))

def enqueue_sms(to: str, message: str, priority: int = 1):  # High priority for urgent alerts
    notify_queue.put((priority, {'type': 'sms', 'to': to, 'message': message}))

def enqueue_webhook(payload: dict, priority: int = 3):
    notify_queue.put((priority, {'type': 'webhook', 'payload': payload}))

# Example templated functions
def notify_detection(record: dict, to_email: str, to_phone: Optional[str] = None):
    subject = "Bhushuraksha AI Alert: Suspected Illegal Construction"
    body = f"""
    <h3>New Detection</h3>
    <p><b>Time:</b> {record['timestamp']}</p>
    <p><b>Owner:</b> {record.get('owner', {}).get('owner_name', 'N/A')}</p>
    <p><b>Coords:</b> {record.get('geometry', {}).get('coordinates', 'N/A')}</p>
    """
    enqueue_email(to_email, subject, body, priority=1)
    
    if to_phone:
        sms_msg = f"Alert: Illegal construction detected at {record['timestamp']}. Check dashboard."
        enqueue_sms(to_phone, sms_msg, priority=1)
    
    webhook_payload = {"event": "detection", "data": record}
    enqueue_webhook(webhook_payload, priority=2)

# For grievance status updates (SRS F5.3)
def notify_grievance_update(grievance: dict, status: str):
    to_email = grievance.get('email')
    to_phone = grievance.get('phone')  # Assuming phone in record
    if to_email:
        subject = "Grievance Update"
        body = f"Your grievance #{grievance['_id']} status: {status}"
        enqueue_email(to_email, subject, body)
    if to_phone:
        enqueue_sms(to_phone, f"Grievance update: Status changed to {status}")

if __name__ == "__main__":
    # Test
    notify_detection({"timestamp": datetime.now(), "owner": {"owner_name": "Test"}, "geometry": {"coordinates": [0,0]}}, "test@email.com", "+1234567890")
