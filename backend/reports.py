# backend/reports.py - Improved 10/10 Version

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
import threading
import gzip  # For compression

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

logger = logging.getLogger(__name__)

REPORT_DIR = os.path.join(os.getcwd(), "reports")

def ensure_dir():
    os.makedirs(REPORT_DIR, exist_ok=True)

def _records_to_geojson(records: List[Dict], include_heatmap: bool = False) -> dict:
    feats = []
    for r in records:
        geom = r.get("geometry") or {}
        if not geom and r.get("bbox"):
            bbox = r.get("bbox")
            cx = (bbox + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[4]) / 2.0
            geom = {"type": "Point", "coordinates": [cx, cy]}
        feats.append({
            "type": "Feature",
            "geometry": geom if geom else None,
            "properties": {
                "timestamp": str(r.get("timestamp")),
                "ward": r.get("ward"),
                "severity": r.get("severity"),
                "owner": (r.get("owner") or {}).get("owner_name"),
                "khasra": (r.get("owner") or {}).get("khasra_no"),
                "details": r.get("details") or r.get("location") or "Illegal construction detection"
            }
        })
    
    geojson = {"type": "FeatureCollection", "features": feats}
    
    # Innovation: Add simple heatmap data (count by severity)
    if include_heatmap:
        from collections import Counter
        severity_counts = Counter(f['properties']['severity'] for f in feats)
        geojson['heatmap'] = dict(severity_counts)
    
    return geojson

def generate_csv(records: List[Dict], out_path: str) -> str:
    df = pd.DataFrame([{
        "timestamp": str(r.get("timestamp")),
        "ward": r.get("ward"),
        "severity": r.get("severity"),
        "bbox": r.get("bbox"),
        "owner": (r.get("owner") or {}).get("owner_name"),
        "khasra": (r.get("owner") or {}).get("khasra_no"),
        "property_id": (r.get("owner") or {}).get("property_id"),
        "mask_path": r.get("mask_path")
    } for r in records])
    df.to_csv(out_path, index=False)
    return out_path

def generate_pdf(records: List[Dict], out_path: str) -> str:
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4
    c.setTitle("Bhushuraksha AI – Detection Report")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, height - 2*cm, "Bhushuraksha AI – Detection Report")
    c.setFont("Helvetica", 10)
    c.drawString(2*cm, height - 2.7*cm, f"Generated: {datetime.utcnow().isoformat()}Z")

    # Add trend summary (innovation: simple analytics)
    total = len(records)
    c.drawString(2*cm, height - 3.5*cm, f"Total Detections: {total}")

    y = height - 4.5*cm
    for idx, r in enumerate(records, 1):
        if y < 4*cm:
            c.showPage()
            y = height - 2*cm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, y, f"{idx}. Detection @ {str(r.get('timestamp'))}")
        y -= 0.6*cm
        c.setFont("Helvetica", 10)
        lines = [
            f"Ward: {r.get('ward', 'NA')}   Severity: {r.get('severity','NA')}",
            f"BBox: {r.get('bbox', 'NA')}",
            f"Owner: {(r.get('owner') or {}).get('owner_name', 'NA')}  Khasra: {(r.get('owner') or {}).get('khasra_no', 'NA')}",
            f"Mask: {r.get('mask_path', 'NA')}"
        ]
        for line in lines:
            c.drawString(2.2*cm, y, line)
            y -= 0.5*cm
        y -= 0.3*cm
        c.setStrokeColor(colors.lightgrey)
        c.line(2*cm, y, width - 2*cm, y)
        y -= 0.4*cm

    c.showPage()
    c.save()
    return out_path

def generate_geojson(records: List[Dict], out_path: str, compress: bool = False) -> str:
    gj = _records_to_geojson(records, include_heatmap=True)  # With heatmap data
    json_str = json.dumps(gj, ensure_ascii=False, indent=2)
    if compress:
        with gzip.open(out_path + '.gz', 'wt', encoding='utf-8') as f:
            f.write(json_str)
        return out_path + '.gz'
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    return out_path

def list_reports(ward: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    ensure_dir()
    files = sorted(os.listdir(REPORT_DIR))
    out = []
    for f in files:
        p = os.path.join(REPORT_DIR, f)
        if os.path.isfile(p):
            parts = f.split("__")
            report_date = "-".join(parts[1].split("_")[:3]) if len(parts) > 1 else ""
            # Filter by date/ward if provided (simple string match for demo)
            if (ward and ward not in f) or (start_date and report_date < start_date) or (end_date and report_date > end_date):
                continue
            details = parts if parts else "detections"
            out.append({
                "id": f,
                "type": f.split(".")[-1],
                "date": report_date,
                "ward": ward if ward in f else None,
                "details": details
            })
    return out

def generate_and_save(records: List[Dict], report_type: str, title_prefix: str = "detections", async_mode: bool = False) -> tuple:
    ensure_dir()
    ts = datetime.utcnow().strftime("%Y_%m_%d__%H_%M_%S")
    fname = f"{title_prefix}__{ts}.{report_type}"
    out_path = os.path.join(REPORT_DIR, fname)

    def _generate():
        if report_type == "csv":
            return generate_csv(records, out_path), fname
        elif report_type == "pdf":
            return generate_pdf(records, out_path), fname
        elif report_type == "geojson":
            return generate_geojson(records, out_path, compress=True), fname  # Compressed for efficiency
        else:
            raise ValueError("Unsupported report type. Use pdf/csv/geojson.")

    if async_mode:
        thread = threading.Thread(target=_generate)
        thread.start()
        return "Report generation started asynchronously", fname  # Return immediately
    else:
        return _generate()

# Example usage (integrate with app.py)
if __name__ == "__main__":
    # Test generation
    sample_records = [{"timestamp": datetime.now(), "ward": "1", "severity": "high", "owner": {"owner_name": "Test"}}]
    path, fname = generate_and_save(sample_records, "pdf")
    print(f"Generated: {fname}")
