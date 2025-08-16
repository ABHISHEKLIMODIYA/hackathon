# app.py — Bhushuraksha AI (NO-SECURITY DEMO BUILD)
import os
import base64
import datetime as dt
import logging
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, request, jsonify, render_template, send_file, session, g
from flask_cors import CORS
import functools

# Add socketio
SAFE_REASON: List[str] = []
try:
    from flask_socketio import SocketIO, emit
except Exception as e:
    SAFE_REASON.append(f"flask_socketio missing/invalid ({e})")
    SocketIO = None
    emit = None

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("bhushuraksha")

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "secret")
CORS(app)
# Force threading async mode to avoid eventlet bind issues on Windows
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*") if SocketIO else None

# -----------------------------------------------------------------------------
# SAFE MODE (fallback when Mongo or modules are unavailable)
# -----------------------------------------------------------------------------
SAFE_MODE = False
SAFE_REASON: List[str] = []
mem: Dict[str, List[Dict[str, Any]]] = {
    "detections": [],
    "grievances": [],
    "images": [],     # stores {tag: 'manual_old'|'manual_new', timestamp, image: base64, ...}
    "reports": [],    # stores {id, type, location, date, status, file?}
    "contacts": [],
    "users": [],
}

# Defaults (overridable by configa_h or env)
INDORE_BBOX: Tuple[float, float, float, float] = (75.74, 22.58, 76.02, 22.84)
DB_NAME = "bhushuraksha"
COLLECTION_NAME = "records"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/bhushuraksha")

# Dummy base64 for a 1x1 red pixel image
DUMMY_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

# Translations dict
translations = {
    "en": {
        "hero_title": "Protecting Land Rights with",
        "ai_intelligence": "AI Intelligence",
        "hero_subtitle": "Advanced satellite-based land encroachment detection system powered by artificial intelligence. Monitor, detect, and prevent unauthorized land use with 95% accuracy.",
        "get_started": "Get Started",
        "watch_demo": "Watch Demo",
        "accuracy": "Accuracy",
        "monitoring": "Monitoring",
        "alerts": "Alerts",
        "features_title": "Comprehensive Land Protection",
        "features_subtitle": "Advanced AI-powered features for complete land monitoring and encroachment detection",
        "satellite_monitoring": "Satellite Monitoring",
        "satellite_desc": "Real-time satellite imagery analysis using high-resolution data from Sentinel-2 and other sources.",
        "ai_detection": "AI Detection",
        "ai_detection_desc": "Advanced machine learning algorithms including OpenCV and Isolation Forest for accurate encroachment detection.",
        "legal_validation": "Legal Validation",
        "legal_validation_desc": "Automated cross-referencing with land records and legal databases to verify legitimacy of land use changes.",
        "instant_alerts": "Instant Alerts",
        "instant_alerts_desc": "Real-time notifications and alerts sent to relevant authorities when unauthorized activities are detected.",
        "automated_reports": "Automated Reports",
        "automated_reports_desc": "Generate comprehensive reports with evidence, coordinates, and legal documentation for enforcement actions.",
        "analytics_dashboard": "Analytics Dashboard",
        "analytics_dashboard_desc": "Interactive dashboard with trends, statistics, and insights for better land management decisions.",
        "technology_title": "Cutting-Edge Technology Stack",
        "technology_subtitle": "Built with the latest AI and satellite technology for maximum accuracy and reliability",
        "satellite_data": "Satellite Data",
        "ai_processing": "AI Processing",
        "image_analysis": "Image Analysis",
        "alert_system": "Alert System",
        "computer_vision": "Computer Vision",
        "computer_vision_desc": "OpenCV-based image processing for detecting changes in land use patterns and identifying unauthorized constructions.",
        "image_processing": "Image Processing",
        "pattern_recognition": "Pattern Recognition",
        "machine_learning": "Machine Learning",
        "machine_learning_desc": "Advanced ML algorithms trained on extensive datasets to achieve 95% accuracy in encroachment detection.",
        "neural_networks": "Neural Networks",
        "classification": "Classification",
        "satellite_integration": "Satellite Integration",
        "satellite_integration_desc": "Integration with Sentinel-2 for high-resolution imagery and change detection.",
        "satellite_imagery": "Satellite Imagery",
        "gis_integration": "GIS Integration",
        "legal_database": "Legal Database",
        "legal_database_desc": "Integration with land records, property databases, and legal documentation systems for validation.",
        "database_integration": "Database Integration",
        "legal_records": "Legal Records",
        "validation_system": "Validation System",
        "benefits_title": "Why Choose Bhushuraksha AI?",
        "benefits_subtitle": "Comprehensive benefits for government agencies, property owners, and legal authorities",
        "cost_effective": "Cost Effective",
        "cost_effective_desc": "Reduce manual monitoring costs by up to 80% while increasing coverage and accuracy of land surveillance.",
        "high_accuracy": "High Accuracy",
        "high_accuracy_desc": "95% accuracy rate in detecting unauthorized land use changes, significantly reducing false positives and negatives.",
        "real_time_monitoring": "Real-time Monitoring",
        "real_time_monitoring_desc": "24/7 automated monitoring with instant alerts, enabling rapid response to encroachment activities.",
        "legal_compliance": "Legal Compliance",
        "legal_compliance_desc": "Automated legal validation and documentation generation for streamlined enforcement procedures.",
        "scalable_solution": "Scalable Solution",
        "scalable_solution_desc": "Easily scalable to monitor large areas, from individual properties to entire districts or states.",
        "evidence_generation": "Evidence Generation",
        "evidence_generation_desc": "Automatic generation of court-admissible evidence with timestamps, coordinates, and legal documentation.",
        "demo_title": "See Bhushuraksha AI in Action",
        "demo_subtitle": "Experience the power of AI-driven land encroachment detection",
        "dashboard_title": "Bhushuraksha AI Dashboard",
        "encroachment_detected": "Encroachment Detected",
        "unauthorized_construction": "Unauthorized Construction",
        "detected_ago": "Detected: 2 hours ago",
        "land_use_change": "Land Use Change",
        "resolved_case": "Resolved Case",
        "resolved_ago": "Resolved: 1 day ago",
        "real_time_detection": "Real-time Detection",
        "real_time_detection_desc": "Continuous monitoring with instant alerts",
        "precise_location": "Precise Location",
        "precise_location_desc": "Accurate GPS coordinates and mapping",
        "detailed_reports": "Detailed Reports",
        "detailed_reports_desc": "Comprehensive documentation and evidence",
        "detection_title": "🛰️ Illegal Construction Detection",
        "start_date": "Start Date (YYYY-MM-DD):",
        "end_date": "End Date (YYYY-MM-DD):",
        "fetch_images": "Fetch Images",
        "run_detection": "Run Detection",
        "anomaly_images": "Detected Anomaly Images",
        "detection_result": "📄 Detection Result (JSON)",
        "contact_title": "Get Started with Bhushuraksha AI",
        "contact_subtitle": "Ready to protect your land with advanced AI technology? Contact us today.",
        "email_us": "Email Us",
        "call_us": "Call Us",
        "visit_us": "Visit Us",
    },
    "hi": {
        "hero_title": "एआई बुद्धिमत्ता के साथ भूमि अधिकारों की रक्षा",
        "ai_intelligence": "एआई बुद्धिमत्ता",
        "hero_subtitle": "कृत्रिम बुद्धिमत्ता द्वारा संचालित उन्नत उपग्रह-आधारित भूमि अतिक्रमण पहचान प्रणाली। 95% सटीकता के साथ अनधिकृत भूमि उपयोग की निगरानी, पहचान और रोकथाम करें।",
        "get_started": "शुरू करें",
        "watch_demo": "डेमो देखें",
        "accuracy": "सटीकता",
        "monitoring": "निगरानी",
        "alerts": "चेतावनियाँ",
        "features_title": "व्यापक भूमि सुरक्षा",
        "features_subtitle": "पूर्ण भूमि निगरानी और अतिक्रमण पहचान के लिए उन्नत एआई-संचालित सुविधाएँ",
        "satellite_monitoring": "उपग्रह निगरानी",
        "satellite_desc": "सेंटिनेल-2 और अन्य स्रोतों से उच्च-रिज़ॉल्यूशन डेटा का उपयोग करके वास्तविक समय उपग्रह छवि विश्लेषण।",
        "ai_detection": "एआई पहचान",
        "ai_detection_desc": "सटीक अतिक्रमण पहचान के लिए ओपनसीवी और आइसोलेशन फॉरेस्ट सहित उन्नत मशीन लर्निंग एल्गोरिदम।",
        "legal_validation": "कानूनी सत्यापन",
        "legal_validation_desc": "भूमि उपयोग परिवर्तनों की वैधता सत्यापित करने के लिए भूमि रिकॉर्ड और कानूनी डेटाबेस के साथ स्वचालित क्रॉस-रेफरेंसिंग।",
        "instant_alerts": "त्वरित चेतावनियाँ",
        "instant_alerts_desc": "अनधिकृत गतिविधियों का पता लगने पर प्रासंगिक अधिकारियों को वास्तविक समय सूचनाएँ और चेतावनियाँ भेजी जाती हैं।",
        "automated_reports": "स्वचालित रिपोर्ट",
        "automated_reports_desc": "प्रवर्तन कार्रवाइयों के लिए साक्ष्य, निर्देशांक और कानूनी दस्तावेज़ीकरण के साथ व्यापक रिपोर्ट उत्पन्न करें।",
        "analytics_dashboard": "विश्लेषण डैशबोर्ड",
        "analytics_dashboard_desc": "बेहतर भूमि प्रबंधन निर्णयों के लिए प्रवृत्तियों, सांख्यिकी और अंतर्दृष्टि के साथ इंटरैक्टिव डैशबोर्ड।",
        "technology_title": "अत्याधुनिक प्रौद्योगिकी स्टैक",
        "technology_subtitle": "अधिकतम सटीकता और विश्वसनीयता के लिए नवीनतम एआई और उपग्रह प्रौद्योगिकी के साथ निर्मित",
        "satellite_data": "उपग्रह डेटा",
        "ai_processing": "एआई प्रसंस्करण",
        "image_analysis": "छवि विश्लेषण",
        "alert_system": "चेतावनी प्रणाली",
        "computer_vision": "कंप्यूटर विज़न",
        "computer_vision_desc": "भूमि उपयोग पैटर्न में परिवर्तनों का पता लगाने और अनधिकृत निर्माणों की पहचान के लिए ओपनसीवी-आधारित छवि प्रसंस्करण।",
        "image_processing": "छवि प्रसंस्करण",
        "pattern_recognition": "पैटर्न पहचान",
        "machine_learning": "मशीन लर्निंग",
        "machine_learning_desc": "95% सटीकता प्राप्त करने के लिए व्यापक डेटासेट पर प्रशिक्षित उन्नत एमएल एल्गोरिदम।",
        "neural_networks": "न्यूरल नेटवर्क",
        "classification": "वर्गीकरण",
        "satellite_integration": "उपग्रह एकीकरण",
        "satellite_integration_desc": "उच्च-रिज़ॉल्यूशन इमेजरी और परिवर्तन पहचान के लिए सेंटिनेल-2 के साथ एकीकरण।",
        "satellite_imagery": "उपग्रह इमेजरी",
        "gis_integration": "जीआईएस एकीकरण",
        "legal_database": "कानूनी डेटाबेस",
        "legal_database_desc": "सत्यापन के लिए भूमि रिकॉर्ड, संपत्ति डेटाबेस और कानूनी दस्तावेज़ीकरण प्रणालियों के साथ एकीकरण।",
        "database_integration": "डेटाबेस एकीकरण",
        "legal_records": "कानूनी रिकॉर्ड",
        "validation_system": "सत्यापन प्रणाली",
        "demo_title": "भूशुरक्षा एआई को कार्रवाई में देखें",
        "demo_subtitle": "एआई-संचालित भूमि अतिक्रमण पहचान की शक्ति का अनुभव करें",
        "dashboard_title": "भूशुरक्षा एआई डैशबोर्ड",
        "encroachment_detected": "अतिक्रमण पता चला",
        "unauthorized_construction": "अनधिकृत निर्माण",
        "detected_ago": "पता चला: 2 घंटे पहले",
        "land_use_change": "भूमि उपयोग परिवर्तन",
        "resolved_case": "समाधानित मामला",
        "resolved_ago": "समाधानित: 1 दिन पहले",
        "real_time_detection": "वास्तविक समय पहचान",
        "real_time_detection_desc": "त्वरित चेतावनियों के साथ निरंतर निगरानी",
        "precise_location": "सटीक स्थान",
        "precise_location_desc": "सटीक जीपीएस निर्देशांक और मैपिंग",
        "detailed_reports": "विस्तृत रिपोर्ट",
        "detailed_reports_desc": "व्यापक दस्तावेज़ीकरण और साक्ष्य",
        "detection_title": "🛰️ अवैध निर्माण पहचान",
        "start_date": "प्रारंभ तिथि (YYYY-MM-DD):",
        "end_date": "समाप्ति तिथि (YYYY-MM-DD):",
        "fetch_images": "छवियाँ प्राप्त करें",
        "run_detection": "पहचान चलाएँ",
        "anomaly_images": "पता चली असामान्य छवियाँ",
        "detection_result": "📄 पहचान परिणाम (JSON)",
        "contact_title": "भूशुरक्षा एआई के साथ शुरू करें",
        "contact_subtitle": "उन्नत एआई प्रौद्योगिकी के साथ अपनी भूमि की रक्षा करने के लिए तैयार हैं? आज हमसे संपर्क करें।",
        "email_us": "हमें ईमेल करें",
        "call_us": "हमें कॉल करें",
        "visit_us": "हमसे मिलें",
    }
}

# -----------------------------------------------------------------------------
# Try to import real modules; stub if not available
# -----------------------------------------------------------------------------
def try_imports():
    global MONGO_URI, DB_NAME, COLLECTION_NAME, INDORE_BBOX
    global detect_illegal_construction, manual_fetch, validate_date
    global lookup_owner_by_coords, list_reports, generate_and_save

    # configa_h
    try:
        from configa_h import (
            MONGO_URI as CFG_MONGO_URI,
            DB_NAME as CFG_DB,
            COLLECTION_NAME as CFG_COLL,
            INDORE_BBOX as CFG_BBOX,
        )
        MONGO_URI = os.getenv("MONGO_URI", CFG_MONGO_URI)
        DB_NAME = CFG_DB or DB_NAME
        COLLECTION_NAME = CFG_COLL or COLLECTION_NAME
        INDORE_BBOX = CFG_BBOX or INDORE_BBOX
    except Exception as e:
        SAFE_REASON.append(f"configa_h missing/invalid ({e})")

    # detect_change
    try:
        from detect_change import detect_illegal_construction  # type: ignore
    except Exception as e:
        SAFE_REASON.append(f"detect_change missing/invalid ({e})")
        def detect_illegal_construction(old_img, new_img):
            return {
                "detected": True,
                "bbox": [200, 210, 300, 290],
                "mask_path": f"data:image/png;base64,{DUMMY_BASE64}",
                "area_m2": 180,
                "severity": 0.82
            }

    # fetch_satellite
    try:
        from fetch_satellite import manual_fetch, validate_date  # type: ignore
    except Exception as e:
        SAFE_REASON.append(f"fetch_satellite missing/invalid ({e})")
        def manual_fetch(start, end):
            mem["images"].append({
                "tag": "manual_old",
                "timestamp": dt.datetime.utcnow().isoformat(),
                "image": DUMMY_BASE64
            })
            mem["images"].append({
                "tag": "manual_new",
                "timestamp": dt.datetime.utcnow().isoformat(),
                "image": DUMMY_BASE64
            })
        def validate_date(s: str) -> bool:
            try:
                dt.datetime.strptime(s, "%Y-%m-%d")
                return True
            except Exception:
                return False

    # iccc_client
    try:
        from iccc_client import lookup_owner_by_coords  # type: ignore
    except Exception as e:
        SAFE_REASON.append(f"iccc_client missing/invalid ({e})")
        def lookup_owner_by_coords(lat, lng):
            return {"owner_name": "Demo Owner", "khasra_no": "123/45", "address": "Indore", "property_id": "IMC-0001"}

    # reports
    try:
        from reports import list_reports, generate_and_save  # type: ignore
    except Exception as e:
        SAFE_REASON.append(f"reports.py missing/invalid ({e})")
        def list_reports():
            return [{"id": 1, "type": "Detection", "location": "Indore", "date": dt.datetime.utcnow().isoformat(), "status": "Open"}]
        def generate_and_save(records, rtype, title_prefix="detections"):
            os.makedirs("reports", exist_ok=True)
            name = f"{title_prefix}_{int(dt.datetime.utcnow().timestamp())}.txt"
            path = os.path.join("reports", name)
            with open(path, "w", encoding="utf-8") as f:
                f.write("Demo report\n")
            return path, name

try_imports()

# -----------------------------------------------------------------------------
# Mongo (optional). If it fails, we switch to SAFE_MODE (memory).
# -----------------------------------------------------------------------------
db = None
coll = None
users_coll = None
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING  # type: ignore
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=int(os.getenv("MONGO_SERVER_TIMEOUT_MS", "4000")),
        connectTimeoutMS=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "4000")),
        socketTimeoutMS=int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "4000")),
        tz_aware=True,
    )
    client.admin.command("ping")
    db = client[DB_NAME]
    coll = db[COLLECTION_NAME]
    users_coll = db["users"]
    try:
        coll.create_index([("timestamp", DESCENDING)])
        coll.create_index([("type", ASCENDING), ("timestamp", DESCENDING)])
        coll.create_index([("tag", ASCENDING), ("timestamp", DESCENDING)])
        users_coll.create_index("email", unique=True)
    except Exception:
        pass
    log.info("✅ Mongo connected")
except Exception as e:
    SAFE_MODE = True
    SAFE_REASON.append(f"Mongo connect failed: {e}")
    log.warning("⚠️  Running in SAFE MODE (memory). Reason(s): %s", "; ".join(SAFE_REASON))

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _cxcy(bbox: List[float]) -> Tuple[float, float]:
    if not bbox or len(bbox) < 4:
        return 256.0, 256.0
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0

def _px_to_ll(cx: float, cy: float) -> Tuple[float, float]:
    minx, miny, maxx, maxy = INDORE_BBOX
    lat = miny + (cy / 512.0) * (maxy - miny)
    lng = minx + (cx / 512.0) * (maxx - minx)
    return lat, lng

def _persist(doc: Dict[str, Any]):
    doc["status"] = "pending"
    if coll:
        try:
            result = coll.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            if socketio:
                socketio.emit('new_detection', {'message': 'New illegal construction detected!'})
            return
        except Exception as e:
            log.warning("DB insert failed: %s", e)
    mem["detections"].insert(0, doc)
    doc["id"] = str(len(mem["detections"]))
    if socketio:
        socketio.emit('new_detection', {'message': 'New illegal construction detected!'})

def _latest_image(tag: str) -> Optional[Dict[str, Any]]:
    if coll:
        d = coll.find_one({"tag": tag}, sort=[("timestamp", -1)], projection={"_id": 0, "image": 1, "timestamp": 1})
        if d:
            return d
    for it in reversed(mem["images"]):
        if it.get("tag") == tag:
            return it
    return None

# -----------------------------------------------------------------------------
# SocketIO handlers
# -----------------------------------------------------------------------------
if socketio:
    @socketio.on('ping')
    def handle_ping():
        emit('pong')

# -----------------------------------------------------------------------------
# Pages (ensure aliases work)
# -----------------------------------------------------------------------------
@app.get("/")
def index_page():
    return render_template("index.html")

@app.get("/map")
@app.get("/map_view")
def map_page():
    return render_template("map_view.html")

@app.get("/admin_dashboard")
@app.get("/admin_dashboard")
def admin_page():
    return render_template("admin_dashboard.html")

@app.get("/grievance")
@app.get("/grievance_form")
def grievance_page():
    return render_template("grievance_form.html")

@app.get("/reports_viewer")
@app.get("/report_viewer")
def report_viewer_page():
    return render_template("report_viewer.html")

# Auth pages
@app.get("/login")
def login_page():
    return render_template("login.html")

@app.get("/register")
def register_page():
    return render_template("register.html")

@app.get("/forgot_password")
def forgot_password_page():
    return render_template("forgot_password.html")

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/api/health")
def api_health():
    out = {"ok": True, "mode": "SAFE" if SAFE_MODE else "FULL"}
    if SAFE_MODE:
        out["reason"] = SAFE_REASON
    else:
        try:
            db.command("ping")
            out["mongo"] = "up"
        except Exception as e:
            out["mongo"] = f"down: {e}"
    return jsonify(out)

# -----------------------------------------------------------------------------
# Translations
# -----------------------------------------------------------------------------
@app.get("/api/translations")
def api_translations():
    lang = request.args.get("lang", session.get("language", "en"))
    trans = translations.get(lang, translations["en"])
    return jsonify(trans)

@app.post("/set_language")
def api_set_language():
    data = request.get_json(silent=True) or {}
    lang = data.get("language", "en")
    session["language"] = lang
    return jsonify({"success": True})

# -----------------------------------------------------------------------------
# Auth (NO SECURITY: demo-only, no JWT)
# -----------------------------------------------------------------------------
@app.post("/api/register")
def api_register():
    data = request.get_json() or {}
    if not all(k in data for k in ["name", "email", "password", "role"]):
        return jsonify({"success": False, "message": "Missing fields"}), 400
    email = data["email"]
    if users_coll and users_coll.find_one({"email": email}):
        return jsonify({"success": False, "message": "User exists"}), 400
    if any(u["email"] == email for u in mem["users"]):
        return jsonify({"success": False, "message": "User exists"}), 400
    doc = {"name": data["name"], "email": email, "password": data["password"], "role": data["role"]}
    if users_coll:
        users_coll.insert_one(doc)
    else:
        mem["users"].append(doc)
    return jsonify({"success": True})

@app.post("/api/login")
def api_login():
    data = request.get_json() or {}
    if not all(k in data for k in ["email", "password", "role"]):
        return jsonify({"success": False, "message": "Missing fields"}), 400
    user = users_coll.find_one({"email": data["email"]}) if users_coll else next((u for u in mem["users"] if u["email"] == data["email"]), None)
    if not user or user["password"] != data["password"] or user["role"] != data["role"]:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    # No token in demo build
    return jsonify({"success": True, "role": user["role"]})

@app.post("/api/forgot-password")
def api_forgot_password():
    data = request.get_json() or {}
    email = data.get("email")
    return jsonify({"message": "If the email exists, a reset link has been sent."})

# -----------------------------------------------------------------------------
# Users management (NO AUTH: demo-only)
# -----------------------------------------------------------------------------
@app.route("/api/users", methods=["GET", "POST", "PUT", "DELETE"])
def api_users():
    if request.method == "GET":
        if users_coll:
            users = list(users_coll.find({}, {"_id": 0}))
        else:
            users = mem["users"]
        # hide passwords in response for cosmetic reasons
        safe_users = [{k: v for k, v in u.items() if k != "password"} for u in users]
        return jsonify({"users": safe_users})

    data = request.get_json() or {}
    email = data.get("email")

    if request.method == "POST":
        if not all(k in data for k in ["name", "email", "password", "role"]):
            return jsonify({"error": "Missing fields"}), 400
        if users_coll and users_coll.find_one({"email": email}):
            return jsonify({"error": "User exists"}), 400
        if any(u["email"] == email for u in mem["users"]):
            return jsonify({"error": "User exists"}), 400
        doc = {"name": data["name"], "email": email, "password": data["password"], "role": data["role"]}
        if users_coll:
            users_coll.insert_one(doc)
        else:
            mem["users"].append(doc)
        return jsonify({"success": True})

    if request.method == "PUT":
        updates = {}
        if "name" in data: updates["name"] = data["name"]
        if "role" in data: updates["role"] = data["role"]
        if "password" in data: updates["password"] = data["password"]
        if not updates:
            return jsonify({"error": "No updates provided"}), 400
        if users_coll:
            result = users_coll.update_one({"email": email}, {"$set": updates})
            if result.matched_count == 0:
                return jsonify({"error": "User not found"}), 404
        else:
            for u in mem["users"]:
                if u["email"] == email:
                    u.update(updates)
                    break
            else:
                return jsonify({"error": "User not found"}), 404
        return jsonify({"success": True})

    if request.method == "DELETE":
        if users_coll:
            result = users_coll.delete_one({"email": email})
            if result.deleted_count == 0:
                return jsonify({"error": "User not found"}), 404
        else:
            mem["users"] = [u for u in mem["users"] if u["email"] != email]
        return jsonify({"success": True})

# -----------------------------------------------------------------------------
# Dashboard Stats
# -----------------------------------------------------------------------------
@app.get("/api/dashboard_stats")
def api_dashboard_stats():
    if coll:
        total = coll.count_documents({"type": "detection_result"})
        pending = coll.count_documents({"type": "detection_result", "status": "pending"})
        resolved = coll.count_documents({"type": "detection_result", "status": "resolved"})
    else:
        total = len(mem["detections"])
        pending = len([d for d in mem["detections"] if d.get("status") == "pending"])
        resolved = len([d for d in mem["detections"] if d.get("status") == "resolved"])
    return jsonify({
        "total_detections": total,
        "pending_alerts": pending,
        "resolved_cases": resolved
    })

# -----------------------------------------------------------------------------
# Alerts
# -----------------------------------------------------------------------------
@app.get("/api/alerts")
def api_alerts():
    if coll:
        dets = list(coll.find({"type": "detection_result"}, {"_id": 0}).sort("timestamp", -1))
    else:
        dets = mem["detections"]
    alerts = []
    for d in dets:
        alerts.append({
            "ward": d.get("ward", "Unknown"),
            "location": d.get("owner", {}).get("address", "Indore"),
            "coordinates": f"{d.get('geometry', {}).get('coordinates', [0,0])[1]:.4f}, {d.get('geometry', {}).get('coordinates', [0,0])[0]:.4f}",
            "date": d.get("timestamp"),
            "severity": "High" if d.get("severity", 0) > 0.7 else "Medium" if d.get("severity", 0) > 0.4 else "Low",
            "status": d.get("status", "Open")
        })
    return jsonify({"alerts": alerts})

# -----------------------------------------------------------------------------
# Contact
# -----------------------------------------------------------------------------
@app.post("/api/contact")
def api_contact():
    try:
        data = request.get_json()
        doc = {"type": "contact", "timestamp": dt.datetime.utcnow(), "data": data}
        if coll:
            coll.insert_one(doc)
        else:
            mem["contacts"].append(doc)
        return jsonify({"success": True, "message": "Contact submitted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# -----------------------------------------------------------------------------
# Fetch images (manual)
# -----------------------------------------------------------------------------
@app.post("/api/fetch/manual")
def api_fetch_manual():
    data = request.get_json(silent=True) or {}
    start = data.get("start_date") or data.get("from_date")
    end   = data.get("end_date") or data.get("to_date")
    if not (start and end):
        return jsonify({"error": "Missing start_date or end_date"}), 400
    try:
        dt.datetime.strptime(start, "%Y-%m-%d")
        dt.datetime.strptime(end, "%Y-%m-%d")
    except Exception:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
    try:
        manual_fetch(start, end)
        if not _latest_image("manual_old"):
            mem["images"].append({"tag": "manual_old", "timestamp": dt.datetime.utcnow().isoformat(), "image": DUMMY_BASE64})
        if not _latest_image("manual_new"):
            mem["images"].append({"tag": "manual_new", "timestamp": dt.datetime.utcnow().isoformat(), "image": DUMMY_BASE64})
        return jsonify({"status": "images fetched"})
    except Exception as e:
        return jsonify({"error": f"fetch failed: {e}"}), 500

# -----------------------------------------------------------------------------
# List images (for debugging/UX)
# -----------------------------------------------------------------------------
@app.get("/api/images")
def api_images():
    try:
        if coll:
            cur = coll.find({"tag": {"$exists": True}}, {"_id": 0, "tag": 1, "timestamp": 1, "image": 1}).sort("timestamp", -1).limit(2)
            data = list(cur)
        else:
            data = mem["images"][-2:]
        for item in data:
            item["display_image"] = item.get("image")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# Detection (GET legacy & POST modern)
# -----------------------------------------------------------------------------
@app.get("/api/detect")
def api_detect_get():
    return _run_detect(wrap_ok=False)

@app.post("/api/detect/run")
def api_detect_post():
    data = request.get_json(silent=True) or {}
    start = data.get("from_date") or data.get("start_date")
    end   = data.get("to_date") or data.get("end_date")
    if start and end:
        try:
            manual_fetch(start, end)
        except Exception as e:
            log.warning("manual_fetch non-fatal failure: %s", e)
    return _run_detect(wrap_ok=True)

def _run_detect(wrap_ok: bool):
    try:
        old_doc = _latest_image("manual_old")
        new_doc = _latest_image("manual_new")
        if not (old_doc and new_doc):
            resp = {"error": "No scenes. Call /api/fetch/manual first."}
            return (jsonify({"ok": False, **resp}), 400) if wrap_ok else (jsonify(resp), 400)

        result = detect_illegal_construction(old_doc.get("image"), new_doc.get("image"))
        anomalies = []
        detected = result.get("detected", False)
        if detected:
            bbox = result.get("bbox") or [0, 0, 0, 0]
            cx, cy = _cxcy(bbox)
            lat, lng = _px_to_ll(cx, cy)

            try:
                owner = lookup_owner_by_coords(lat, lng) or {}
            except Exception:
                owner = {}

            area = float(result.get("area_m2") or 120.0)
            sev  = float(result.get("severity") or 0.8)
            sev = max(0.0, min(1.0, sev))

            anomaly = {
                "type": "land_clearing",
                "bbox": bbox,
                "area_m2": round(area, 1),
                "severity": sev,
                "lat": lat,
                "lng": lng,
                "owner": owner,
            }
            anomalies = [anomaly]

            _persist({
                "type": "detection_result",
                "timestamp": dt.datetime.utcnow(),
                "bbox": bbox,
                "area_m2": area,
                "severity": sev,
                "owner": owner,
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "mask_path": result.get("mask_path"),
                "ward": None,
            })

        resp = {"detected": detected, "mask_path": result.get("mask_path"), "anomalies": anomalies}
        return (jsonify({"ok": True, **resp}), 200) if wrap_ok else jsonify(resp)
    except Exception as e:
        resp = {"error": str(e)}
        return (jsonify({"ok": False, **resp}), 500) if wrap_ok else (jsonify(resp), 500)

# -----------------------------------------------------------------------------
# Map + Admin data
# -----------------------------------------------------------------------------
@app.get("/api/map-data")
def api_map_data():
    if coll:
        imgs = list(coll.find({"tag": {"$exists": True}}, {"_id": 0}).sort("timestamp", -1).limit(4))
        dets = list(coll.find({"type": "detection_result"}, {"_id": 0}).sort("timestamp", -1).limit(500))
    else:
        imgs = mem["images"][-4:]
        dets = mem["detections"][:500]
    return jsonify({"images": imgs, "detections": dets})

@app.get("/api/detect/hotspots")
def api_hotspots():
    return jsonify({"ok": True, "hotspots": [
        {"ward": 12, "risk": 0.83},
        {"ward": 41, "risk": 0.71},
        {"ward": 3,  "risk": 0.66},
    ]})

@app.get("/api/admin-dashboard")
def api_admin_dashboard():
    try:
        users = 0
        reports = 0
        grievances = 0
        if coll:
            if "users" in db.list_collection_names():
                users = db.users.count_documents({})
            if "reports" in db.list_collection_names():
                reports = db.reports.count_documents({})
            grievances = coll.count_documents({"type": "grievance"})
        else:
            users = len(mem["users"])
            reports = max(1, len(mem["reports"]))
            grievances = len(mem["grievances"])
        return jsonify({"users_count": users, "reports_count": reports, "grievances_count": grievances})
    except Exception:
        return jsonify({"users_count": 0, "reports_count": 0, "grievances_count": 0})

# -----------------------------------------------------------------------------
# Reports
# -----------------------------------------------------------------------------
@app.get("/api/reports")
def api_reports():
    try:
        return jsonify(list_reports())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/reports/download")
def api_reports_download():
    rid = request.args.get("id")
    rtype = (request.args.get("type") or "pdf").lower()
    try:
        if coll:
            records = list(
                coll.find({"type": "detection_result"}, {"_id": 0})
                .sort("timestamp", -1)
                .limit(20)
            )
        else:
            records = mem["detections"][:20]

        base = os.path.abspath("reports")
        os.makedirs(base, exist_ok=True)
        if rid:
            path = os.path.abspath(os.path.join(base, rid))
            if not path.startswith(base) or not os.path.isfile(path):
                return jsonify({"error": "Report not found"}), 404
            return send_file(path, as_attachment=True, download_name=os.path.basename(path))

        path, fname = generate_and_save(records, rtype, title_prefix="detections")
        return send_file(path, as_attachment=True, download_name=fname)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# Grievances
# -----------------------------------------------------------------------------
@app.post("/api/grievance")
def api_grievance_submit():
    try:
        if request.is_json:
            p = request.get_json() or {}
            name = p.get("name"); email = p.get("email")
            ward = p.get("ward"); location = p.get("location")
            desc = p.get("description"); image_b64 = p.get("image")
        else:
            name = request.form.get("name"); email = request.form.get("email")
            ward = request.form.get("ward"); location = request.form.get("location")
            desc = request.form.get("description"); image_b64 = None
            if "image" in request.files:
                f = request.files["image"]; raw = f.read()
                mime = f.mimetype or "application/octet-stream"
                image_b64 = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        doc = {
            "type": "grievance",
            "name": name, "email": email, "ward": ward,
            "location": location, "description": desc,
            "image": image_b64, "timestamp": dt.datetime.utcnow(),
        }
        if coll:
            coll.insert_one(doc)
        else:
            mem["grievances"].insert(0, doc)
        return jsonify({"success": True, "message": "Grievance submitted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.get("/api/grievances")
def api_grievances():
    if coll:
        rows = list(coll.find({"type": "grievance"}, {"_id": 0}).sort("timestamp", -1).limit(500))
    else:
        rows = mem["grievances"][:500]
    return jsonify(rows)

@app.get("/api/grievance/leaderboard")
def api_grievance_leaderboard():
    try:
        items: Dict[str, Dict[str, Any]] = {}
        data = (list(coll.find({"type": "grievance"}, {"_id": 0})) if coll else mem["grievances"])
        for g in data:
            key = (g.get("email") or "anon").lower()
            if key not in items:
                items[key] = {"name": g.get("name") or key, "email": key, "count": 0}
            items[key]["count"] += 1
        out = sorted(items.values(), key=lambda x: x["count"], reverse=True)[:10]
        return jsonify({"ok": True, "items": out})
    except Exception as e:
        return jsonify({"ok": False, "items": [], "error": str(e)}), 500

# -----------------------------------------------------------------------------
# GeoJSON feed (map fallback)
# -----------------------------------------------------------------------------
@app.get("/api/detections.geojson")
def api_detections_geojson():
    try:
        if coll:
            data = list(coll.find({"type": "detection_result"}, {"_id": 0}).sort("timestamp", -1).limit(1000))
        else:
            data = mem["detections"][:1000]
        feats = []
        for d in data:
            feats.append({
                "type": "Feature",
                "geometry": d.get("geometry"),
                "properties": {
                    "timestamp": str(d.get("timestamp")),
                    "severity": d.get("severity", 0.6),
                    "ward": d.get("ward", "NA"),
                    "owner": (d.get("owner") or {}).get("owner_name") or (d.get("owner") or {}).get("owner"),
                    "khasra": (d.get("owner") or {}).get("khasra_no"),
                    "property_id": (d.get("owner") or {}).get("property_id"),
                    "mask_path": d.get("mask_path"),
                    "area_m2": d.get("area_m2"),
                }
            })
        return jsonify({"type": "FeatureCollection", "features": feats})
    except Exception as e:
        return jsonify({"type": "FeatureCollection", "features": [], "error": str(e)}), 500

# -----------------------------------------------------------------------------
# JSON errors
# -----------------------------------------------------------------------------
@app.errorhandler(404)
def err404(e):
    return jsonify({"error": "Not Found", "message": str(e), "status": 404}), 404

@app.errorhandler(500)
def err500(e):
    log.exception("Internal error: %s", e)
    return jsonify({"error": "Internal Server Error", "message": str(e), "status": 500}), 500

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
import socket

def _pick_free_port(start=5000, max_tries=50):
    """Pick a free TCP port starting from `start` or env PORT if provided."""
    port = int(os.getenv("PORT", start))
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free port found in range")

if __name__ == "__main__":
    mode = "SAFE MODE ✅ (memory)" if SAFE_MODE or SAFE_REASON else "FULL MODE 🚀"
    if SAFE_REASON:
        log.warning("Starting in %s. Reasons: %s", mode, "; ".join(SAFE_REASON))
    else:
        log.info("Starting in %s", mode)

    chosen_port = _pick_free_port(5000)
    print(f"\n🌐 Server running at: http://localhost:{chosen_port}\n")

    if socketio:
        socketio.run(
            app,
            host="0.0.0.0",
            port=chosen_port,
            debug=False,
            use_reloader=False  # prevents double-binding on Windows
        )
    else:
        app.run(
            host="0.0.0.0",
            port=chosen_port,
            debug=False,
            use_reloader=False
        )
