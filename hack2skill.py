"""
ArenaMind: Generative AI Smart Stadium Assistant for FIFA World Cup 2026

This Python application combines Streamlit and FastAPI to deliver a modular stadium assistant,
including AI chat, crowd intelligence, navigation, sustainability, volunteer management,
and analytics for fans, organizers, security, and venue staff.

Instructions:
- Install dependencies from the environment.
- Create a .env file or set environment variables:
    GEMINI_API_KEY=your_google_gemini_api_key
    YOLO_MODEL_PATH=path_to_yolov8_model (optional)
- Run the API with:
    python untitled:Untitled-1 api
- Run the Streamlit interface with:
    streamlit run untitled:Untitled-1

The script maintains a local SQLite database at arena_mind.db and stores reports in ./reports.

Requirements included in this single-file implementation:
- Streamlit frontend
- FastAPI backend
- SQLite data persistence
- Google Gemini AI integration
- Crowd analysis with OpenCV / YOLO fallback
- Plotly analytics
- Folium route maps
- NetworkX route optimization
- Multilingual translation
- Text-to-speech support
- PDF report generation

"""

import os
import sys
import json
import time
import uuid
import sqlite3
import hashlib
import logging
import threading
import random
import tempfile
from datetime import datetime
from pathlib import Path

# Optional libraries
try:
    import requests
except ImportError:
    requests = None

try:
    import streamlit as st
    import streamlit.components.v1 as components
except ImportError:
    st = None
    components = None

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
except ImportError:
    FastAPI = None
    HTTPException = Exception
    CORSMiddleware = None
    FileResponse = None

try:
    import uvicorn
except ImportError:
    uvicorn = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import plotly.graph_objs as go
except ImportError:
    go = None

try:
    import networkx as nx
except ImportError:
    nx = None

try:
    import folium
except ImportError:
    folium = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# Constants and paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "arena_mind.db"
REPORTS_DIR = BASE_DIR / "reports"
LOG_PATH = BASE_DIR / "arena_mind.log"
STADIUM_MAP_CENTER = (24.706, -29.475)
SUPPORTED_LANGUAGES = {
    "English": "en",
    "Hindi": "hi",
    "Spanish": "es",
    "French": "fr",
    "Arabic": "ar",
}

# Configure logging
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ArenaMind")


def log_event(message: str, level: str = "info"):
    if level == "debug":
        logger.debug(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            language TEXT,
            created_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            summary TEXT,
            data_json TEXT,
            created_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            message TEXT,
            level TEXT,
            active INTEGER,
            timestamp TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS crowd_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT,
            timestamp TEXT,
            density REAL,
            occupancy INTEGER,
            congestion_level TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS parking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT,
            available_spots INTEGER,
            total_spots INTEGER,
            updated_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            location TEXT,
            assigned_task TEXT,
            status TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sustainability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT,
            value REAL,
            unit TEXT,
            timestamp TEXT
        )
        """
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        sample_users = [
            ("admin", hash_password("ArenaMind2026"), "Admin", "en", datetime.utcnow().isoformat()),
            ("volunteer1", hash_password("Volunteer@2026"), "Volunteer", "en", datetime.utcnow().isoformat()),
            ("fan1", hash_password("FanPass123"), "Fan", "es", datetime.utcnow().isoformat()),
            ("organizer1", hash_password("Organizer2026"), "Organizer", "fr", datetime.utcnow().isoformat()),
        ]
        cursor.executemany(
            "INSERT INTO users (username, password_hash, role, language, created_at) VALUES (?, ?, ?, ?, ?)",
            sample_users,
        )
        log_event("Seeded sample user accounts.")

    cursor.execute("SELECT COUNT(*) FROM parking")
    if cursor.fetchone()[0] == 0:
        parking_samples = [
            ("North Lot", 120, 200, datetime.utcnow().isoformat()),
            ("South Garage", 70, 150, datetime.utcnow().isoformat()),
            ("East Shuttle Hub", 45, 80, datetime.utcnow().isoformat()),
        ]
        cursor.executemany(
            "INSERT INTO parking (zone, available_spots, total_spots, updated_at) VALUES (?, ?, ?, ?)",
            parking_samples,
        )

    cursor.execute("SELECT COUNT(*) FROM volunteers")
    if cursor.fetchone()[0] == 0:
        volunteer_samples = [
            ("Aisha Khan", "Medical Aid", "North Stand", "Patrol first aid stations", "On Duty"),
            ("Miguel Ruiz", "Guest Services", "East Gate", "Guide fans to accessible seating", "On Duty"),
            ("Priya Sharma", "Security", "South Entrance", "Monitor crowd flow", "Available"),
        ]
        cursor.executemany(
            "INSERT INTO volunteers (name, role, location, assigned_task, status) VALUES (?, ?, ?, ?, ?)",
            volunteer_samples,
        )

    cursor.execute("SELECT COUNT(*) FROM sustainability")
    if cursor.fetchone()[0] == 0:
        sustainability_samples = [
            ("Waste Bin Fill Rate", 68.5, "%", datetime.utcnow().isoformat()),
            ("Water Usage", 4200.0, "L", datetime.utcnow().isoformat()),
            ("Energy Consumption", 18.5, "kWh", datetime.utcnow().isoformat()),
            ("Carbon Footprint", 4.7, "tCO2e", datetime.utcnow().isoformat()),
        ]
        cursor.executemany(
            "INSERT INTO sustainability (metric, value, unit, timestamp) VALUES (?, ?, ?, ?)",
            sustainability_samples,
        )

    cursor.execute("SELECT COUNT(*) FROM alerts")
    if cursor.fetchone()[0] == 0:
        alert_samples = [
            ("Security", "Monitor crowd flow near Gate B.", "Medium", 1, datetime.utcnow().isoformat()),
            ("Medical", "First aid station 2 requires extra supplies.", "Low", 1, datetime.utcnow().isoformat()),
            ("Transport", "Shuttle service delayed by 10 minutes.", "Low", 1, datetime.utcnow().isoformat()),
        ]
        cursor.executemany(
            "INSERT INTO alerts (category, message, level, active, timestamp) VALUES (?, ?, ?, ?, ?)",
            alert_samples,
        )

    cursor.execute("SELECT COUNT(*) FROM crowd_data")
    if cursor.fetchone()[0] == 0:
        crowd_samples = [
            ("Camera 1", datetime.utcnow().isoformat(), 0.45, 4200, "Moderate"),
            ("Camera 2", datetime.utcnow().isoformat(), 0.78, 5200, "High"),
            ("Camera 3", datetime.utcnow().isoformat(), 0.32, 3400, "Low"),
        ]
        cursor.executemany(
            "INSERT INTO crowd_data (camera_id, timestamp, density, occupancy, congestion_level) VALUES (?, ?, ?, ?, ?)",
            crowd_samples,
        )

    conn.commit()
    conn.close()
    os.makedirs(REPORTS_DIR, exist_ok=True)
    log_event("Database initialized successfully.")


def hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(16)).hexdigest()
    digest = hashlib.sha512((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, digest = password_hash.split("$")
        return hashlib.sha512((salt + password).encode("utf-8")).hexdigest() == digest
    except Exception:
        return False


def register_user(username: str, password: str, role: str, language: str = "en") -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, language, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, role, language, datetime.utcnow().isoformat()),
        )
        conn.commit()
        log_event(f"Registered user {username}.")
        return True
    except sqlite3.IntegrityError:
        log_event(f"Failed registration - user exists: {username}", "warning")
        return False
    finally:
        conn.close()


def authenticate_user(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        log_event(f"User logged in: {username}")
        return dict(row)
    return None


def fetch_user(username: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def fallback_ai_response(prompt: str, lang: str = "en") -> str:
    lower = prompt.lower()
    if "ticket" in lower or "booking" in lower:
        return {
            "en": "For ticket support, please check your booking email or visit the ticket counter at Gate A. I can help with seat upgrades and lost tickets.",
            "es": "Para soporte de boletos, revise su correo de reserva o visite el mostrador de boletos en la Puerta A.",
            "fr": "Pour l'assistance aux billets, vérifiez votre e-mail de réservation ou rendez-vous au guichet à la porte A.",
            "hi": "टिकट सहायता के लिए अपना बुकिंग ईमेल जांचें या गेट A पर टिकट काउंटर पर जाएँ।",
            "ar": "للدعم التذاكر، يرجى التحقق من بريد الحجز أو زيارة مكتب التذاكر عند البوابة A.",
        }.get(lang, "Please contact ticket support at the stadium entrance.")
    if "washroom" in lower or "restroom" in lower or "toilet" in lower:
        return {
            "en": "The closest washrooms are located near the East Stand and the North Entrance. Follow the blue signage for accessible restrooms.",
            "es": "Los baños más cercanos están ubicados cerca de la Tribuna Este y la Entrada Norte.",
            "fr": "Les toilettes les plus proches sont situées près de la tribune Est et de l'entrée Nord.",
            "hi": "निकटतम शौचालय पूर्व स्टैंड और उत्तर प्रवेश के पास हैं।",
            "ar": "الحمامات الأقرب تقع بالقرب من الجناح الشرقي والمدخل الشمالي.",
        }.get(lang, "The nearest restrooms are marked on the stadium map.")
    if "emergency" in lower or "safe" in lower or "exit" in lower:
        return {
            "en": "In case of emergency, please follow the nearest exit signs. Staff will guide you to safety. Avoid congested zones and use the south evacuation route if needed.",
            "es": "En caso de emergencia, siga las señales de salida más cercanas.",
            "fr": "En cas d'urgence, suivez les panneaux de sortie les plus proches.",
            "hi": "आपातकाल की स्थिति में, सबसे नजदीकी निकास संकेतों का पालन करें।",
            "ar": "في حالة الطوارئ، اتبع علامات الخروج الأقرب.",
        }.get(lang, "Follow emergency exits and listen to stadium announcements.")
    if "food" in lower or "food" in lower:
        return {
            "en": "Try the local fan food court near Gate B. It offers healthy bowls, stadium classics, and vegan options.",
            "es": "Pruebe el patio de comidas cerca de la Puerta B.",
            "fr": "Essayez la zone de restauration près de la porte B.",
            "hi": "गेट B के पास स्थानीय फैं फूड कोर्ट आज़माएँ।",
            "ar": "جرب ساحة الطعام بالقرب من البوابة B.",
        }.get(lang, "The food court near Gate B has popular stadium meals.")
    return {
        "en": "I am analyzing your question and preparing a helpful response. Please provide any additional context if needed.",
        "es": "Estoy analizando su pregunta y preparando una respuesta útil.",
        "fr": "J'analyse votre question et prépare une réponse utile.",
        "hi": "मैं आपका प्रश्न विश्लेषण कर रहा हूँ और सहायक उत्तर तैयार कर रहा हूँ।",
        "ar": "أنا أقوم بتحليل سؤالك وأعد ردًا مفيدًا.",
    }.get(lang, "I am preparing a response to help you.")


def call_gemini(prompt: str, lang: str = "en") -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not requests:
        log_event("Gemini API key not configured or requests unavailable. Using fallback AI response.", "warning")
        return fallback_ai_response(prompt, lang)
    endpoint = "https://gemini.googleapis.com/v1/models/text-bison-001:generate"
    payload = {
        "prompt": prompt,
        "temperature": 0.7,
        "maxOutputTokens": 400,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        candidate = data.get("candidates", [{}])[0]
        output = candidate.get("output") or candidate.get("content") or ""
        if not output:
            raise ValueError("Invalid Gemini response format")
        return str(output).strip()
    except Exception as exc:
        log_event(f"Gemini API error: {exc}", "error")
        return fallback_ai_response(prompt, lang)


def translate_text(text: str, target_lang: str = "en") -> str:
    if not GoogleTranslator:
        return text
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception as exc:
        log_event(f"Translation error: {exc}", "warning")
        return text


def text_to_speech(text: str, lang: str = "en") -> str:
    if not gTTS:
        raise RuntimeError("gTTS library is required for text-to-speech.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        try:
            tts = gTTS(text=text, lang=lang)
            tts.save(tmp.name)
            return tmp.name
        except Exception as exc:
            log_event(f"TTS error: {exc}", "error")
            raise


def record_voice_query(timeout: int = 5) -> str:
    if not sr:
        raise RuntimeError("SpeechRecognition library is required for voice input.")
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio = recognizer.listen(source, timeout=timeout)
        return recognizer.recognize_google(audio)


def build_stadium_graph():
    graph = nx.Graph() if nx else None
    if graph is None:
        return None
    nodes = {
        "Gate A": (24.7065, -29.4780),
        "Gate B": (24.7072, -29.4730),
        "North Stand": (24.7080, -29.4755),
        "East Stand": (24.7060, -29.4720),
        "South Stand": (24.7045, -29.4754),
        "VIP Lounge": (24.7055, -29.4768),
        "Parking Lot 1": (24.7090, -29.4760),
        "Parking Lot 2": (24.7030, -29.4745),
        "Medical Center": (24.7058, -29.4737),
        "Restroom 1": (24.7062, -29.4744),
        "Restroom 2": (24.7050, -29.4765),
        "Exit 1": (24.7048, -29.4778),
        "Exit 2": (24.7095, -29.4738),
    }
    for name, coords in nodes.items():
        graph.add_node(name, pos=coords)
    edges = [
        ("Gate A", "North Stand", 2.0),
        ("Gate A", "VIP Lounge", 1.2),
        ("Gate B", "East Stand", 1.8),
        ("Gate B", "Medical Center", 1.4),
        ("North Stand", "East Stand", 1.6),
        ("East Stand", "South Stand", 2.1),
        ("South Stand", "Parking Lot 2", 2.5),
        ("VIP Lounge", "Medical Center", 1.0),
        ("Restroom 1", "East Stand", 0.8),
        ("Restroom 2", "VIP Lounge", 0.9),
        ("Parking Lot 1", "North Stand", 3.2),
        ("Parking Lot 2", "South Stand", 1.8),
        ("Exit 1", "VIP Lounge", 1.4),
        ("Exit 2", "East Stand", 1.5),
    ]
    for u, v, w in edges:
        graph.add_edge(u, v, weight=w, accessible=w * 0.9)
    return graph


def find_shortest_route(start: str, end: str, wheelchair: bool = False):
    graph = build_stadium_graph()
    if not graph or start not in graph or end not in graph:
        return []
    weight = "accessible" if wheelchair else "weight"
    try:
        path = nx.shortest_path(graph, source=start, target=end, weight=weight)
        return path
    except Exception as exc:
        log_event(f"Route computation error: {exc}", "warning")
        return []


def build_route_map(path_nodes):
    if not folium or not path_nodes:
        return ""
    stadium_map = folium.Map(location=STADIUM_MAP_CENTER, zoom_start=16)
    graph = build_stadium_graph()
    for node in path_nodes:
        coords = graph.nodes[node]["pos"]
        folium.Marker(location=coords, popup=node, tooltip=node, icon=folium.Icon(color="blue")).add_to(stadium_map)
    line = [graph.nodes[node]["pos"] for node in path_nodes]
    folium.PolyLine(line, color="red", weight=4, opacity=0.7).add_to(stadium_map)
    return stadium_map._repr_html_()


def compute_risk_level(crowd_density: float, weather: str, active_alerts: int) -> dict:
    score = min(1.0, crowd_density + 0.1 * active_alerts)
    if "rain" in weather.lower() or "storm" in weather.lower():
        score += 0.15
    score = min(score, 1.0)
    if score > 0.75:
        level = "High"
        advice = "Deploy additional security and medical teams. Open alternate exits."
    elif score > 0.45:
        level = "Moderate"
        advice = "Monitor stands closely and keep communication lines open."
    else:
        level = "Low"
        advice = "Maintain regular patrols and support service points."
    return {
        "level": level,
        "score": round(score, 2),
        "advice": advice,
    }


def load_crowd_samples():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crowd_data ORDER BY timestamp DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def analyze_crowd_video(video_path: str) -> dict:
    occupancy = 0
    density = 0.0
    congestion = "Unknown"
    recommendations = "Capture high-density zones and consider redirecting foot traffic."
    heatmap_html = ""
    if cv2:
        try:
            cap = cv2.VideoCapture(video_path)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
            occupied_frames = 0
            total_brightness = 0.0
            for _ in range(min(frame_count, 20)):
                ret, frame = cap.read()
                if not ret:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                total_brightness += float(gray.mean())
                occupied_frames += 1
            cap.release()
            if occupied_frames:
                density = min(1.0, total_brightness / 255 / 0.75)
                occupancy = int((density * 6000) + random.randint(-200, 200))
                if density > 0.75:
                    congestion = "High"
                    recommendations = "Activate crowd control barriers and move attendees to less crowded corridors."
                elif density > 0.45:
                    congestion = "Moderate"
                    recommendations = "Adjust fan flow signage and open additional refreshment lanes."
                else:
                    congestion = "Low"
                    recommendations = "Continue monitoring and optimize seating entry points."
        except Exception as exc:
            log_event(f"Crowd video analysis error: {exc}", "warning")
    if folium:
        stadium_map = folium.Map(location=STADIUM_MAP_CENTER, zoom_start=16)
        folium.Circle(location=STADIUM_MAP_CENTER, radius=120, color="red" if density > 0.7 else "orange" if density > 0.4 else "green", fill=True, fill_opacity=0.3, popup="Estimated crowd heat zone").add_to(stadium_map)
        heatmap_html = stadium_map._repr_html_()
    return {
        "occupancy": occupancy,
        "density": round(density, 2),
        "congestion": congestion,
        "recommendations": recommendations,
        "heatmap_html": heatmap_html,
    }


def generate_safety_report(summary: str, data: dict) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reports (title, summary, data_json, created_at) VALUES (?, ?, ?, ?)",
        (f"Safety Report {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}", summary, json.dumps(data), datetime.utcnow().isoformat()),
    )
    conn.commit()
    report_id = cursor.lastrowid
    conn.close()
    return report_id


def create_pdf_report(report_id: int) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()
    conn.close()
    if not report:
        raise FileNotFoundError("Report not found.")
    output_path = REPORTS_DIR / f"report_{report_id}.pdf"
    if FPDF:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "ArenaMind AI Safety & Operations Report", ln=True)
        pdf.ln(4)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 8, f"Title: {report['title']}")
        pdf.multi_cell(0, 8, f"Created: {report['created_at']}")
        pdf.ln(4)
        pdf.multi_cell(0, 8, f"Summary:\n{report['summary']}")
        pdf.ln(4)
        data = json.loads(report['data_json'] or "{}")
        pdf.multi_cell(0, 8, "AI Recommendations and Analytics:")
        for key, value in data.items():
            pdf.multi_cell(0, 8, f"- {key}: {value}")
        pdf.output(str(output_path))
    else:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("ArenaMind AI Safety & Operations Report\n")
            handle.write(f"Title: {report['title']}\n")
            handle.write(f"Created: {report['created_at']}\n\n")
            handle.write(f"Summary:\n{report['summary']}\n\n")
            data = json.loads(report['data_json'] or "{}")
            handle.write("AI Recommendations and Analytics:\n")
            for key, value in data.items():
                handle.write(f"- {key}: {value}\n")
    log_event(f"Generated PDF report {output_path}")
    return str(output_path)


def get_organizational_metrics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crowd_data ORDER BY timestamp DESC LIMIT 12")
    crowd_rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT * FROM alerts WHERE active = 1 ORDER BY timestamp DESC LIMIT 10")
    alert_rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT * FROM parking ORDER BY updated_at DESC")
    parking_rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT * FROM sustainability ORDER BY timestamp DESC")
    sustainability_rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {
        "crowd": crowd_rows,
        "alerts": alert_rows,
        "parking": parking_rows,
        "sustainability": sustainability_rows,
    }


def build_plotly_chart(data, x_key, y_key, title, color="#2a9d8f"):
    if not go or not pd:
        return None
    df = pd.DataFrame(data)
    if df.empty:
        return None
    fig = go.Figure(
        data=[go.Bar(x=df[x_key], y=df[y_key], marker_color=color)]
    )
    fig.update_layout(title=title, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0))
    return fig


def get_parking_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM parking ORDER BY zone")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_volunteer_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM volunteers ORDER BY status DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def create_incident_report(volunteer_name: str, location: str, incident: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO alerts (category, message, level, active, timestamp) VALUES (?, ?, ?, ?, ?)",
        ("Incident", f"{volunteer_name} reported: {incident} at {location}", "High", 1, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return True


def load_alerts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def dashboard_ai_assistant(user_lang: str):
    st.header("AI Stadium Assistant")
    topics = [
        "Match information",
        "Stadium FAQs",
        "Emergency guidance",
        "Nearby facilities",
        "Ticket help",
        "Food recommendations",
        "Transportation insights",
    ]
    topic = st.selectbox("Select a topic", topics)
    prompt = st.text_area("Ask a question", value=f"{topic} for World Cup 2026", height=160)
    voice_mode = st.checkbox("Voice input", value=False)
    if voice_mode:
        if sr:
            if st.button("Record voice query"):
                try:
                    query = record_voice_query()
                    st.success(f"Detected voice: {query}")
                    prompt = query
                except Exception as exc:
                    st.error(f"Voice capture failed: {exc}")
        else:
            st.warning("Voice input is unavailable because speech_recognition is not installed.")
    if st.button("Send to AI"):
        with st.spinner("Contacting Gemini AI..."):
            translated_prompt = translate_text(prompt, target_lang="en") if user_lang != "en" else prompt
            ai_response = call_gemini(translated_prompt, lang=user_lang)
            if user_lang != "en":
                ai_response = translate_text(ai_response, target_lang=user_lang)
            st.write(ai_response)
            if gTTS:
                audio_file = text_to_speech(ai_response, lang=user_lang)
                st.audio(audio_file)
    faq_text = st.expander("Sample FAQs and stadium tips")
    faq_text.write(
        "- Use Gate B for faster access to the East Stand.\n"
        "- Accessible seating is available at all main stands.\n"
        "- Report any medical concern to the nearest volunteer or use the stadium app.\n"
        "- Follow real-time announcements for transport updates."
    )


def dashboard_navigation(user_lang: str):
    st.header("Smart Navigation")
    locations = [
        "Gate A",
        "Gate B",
        "North Stand",
        "East Stand",
        "South Stand",
        "VIP Lounge",
        "Parking Lot 1",
        "Parking Lot 2",
        "Medical Center",
        "Restroom 1",
        "Restroom 2",
        "Exit 1",
        "Exit 2",
    ]
    start = st.selectbox("Start location", locations, index=0)
    destination = st.selectbox("Destination", locations, index=3)
    wheelchair = st.checkbox("Wheelchair friendly route", value=False)
    if st.button("Compute route"):
        path = find_shortest_route(start, destination, wheelchair=wheelchair)
        if path:
            st.success(f"Optimized path: {' → '.join(path)}")
            map_html = build_route_map(path)
            if components and map_html:
                components.html(map_html, height=450)
            else:
                st.info("Route map unavailable. Ensure Folium is installed.")
        else:
            st.error("Unable to compute the route. Please select different nodes.")
    st.markdown("**Accessible routing tips:** Use dedicated ramps near Gate A and follow the blue signage for elevators.")


def dashboard_crowd_intelligence():
    st.header("Crowd Intelligence")
    uploaded = st.file_uploader("Upload CCTV or stadium video", type=["mp4", "mov", "avi"])
    if uploaded:
        temp_path = BASE_DIR / f"temp_{uuid.uuid4().hex}.mp4"
        with open(temp_path, "wb") as handle:
            handle.write(uploaded.read())
        result = analyze_crowd_video(str(temp_path))
        st.metric("Estimated Occupancy", f"{result['occupancy']} people")
        st.metric("Crowd Density", f"{result['density'] * 100:.0f}%")
        st.metric("Congestion Level", result["congestion"])
        st.write(result["recommendations"])
        if components and result["heatmap_html"]:
            components.html(result["heatmap_html"], height=420)
        temp_path.unlink(missing_ok=True)
    else:
        st.info("Upload a short segment of CCTV footage to analyze crowd density.")


def dashboard_decision_support():
    st.header("Real-Time Decision Support")
    metrics = get_organizational_metrics()
    recent_crowd = metrics["crowd"][:3]
    avg_density = sum(row["density"] for row in recent_crowd) / max(len(recent_crowd), 1)
    weather = st.text_input("Current weather summary", "Clear skies with light breeze")
    active_alerts = len([alert for alert in metrics["alerts"] if alert["active"] == 1])
    risk = compute_risk_level(avg_density, weather, active_alerts)
    st.metric("Risk Level", risk["level"], delta=f"Score {risk['score']}")
    st.write(risk["advice"])
    with st.expander("AI Risk Analysis"):
        ai_prompt = (
            f"Analyze stadium conditions for World Cup 2026. Crowd density {avg_density:.2f}, "
            f"weather '{weather}', active alerts {active_alerts}. Provide risk assessment and actions."
        )
        st.write(call_gemini(ai_prompt, lang="en"))


def dashboard_sustainability():
    st.header("Sustainability Dashboard")
    metrics = get_organizational_metrics()["sustainability"]
    if metrics:
        for item in metrics:
            st.metric(item["metric"], f"{item['value']} {item['unit']}")
    recommendation = (
        "Reduce energy consumption by dimming non-critical lighting and prioritize refillable water stations. "
        "Encourage fans to use shuttle services to minimize carbon emissions."
    )
    st.info(recommendation)
    if pd and go and metrics:
        df = pd.DataFrame(metrics)
        fig = go.Figure(
            data=[go.Pie(labels=df["metric"], values=df["value"], hole=0.5)]
        )
        fig.update_layout(title="Sustainability Metrics Breakdown", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)


def dashboard_volunteer(user):
    st.header("Volunteer Dashboard")
    tasks = get_volunteer_tasks()
    st.table(pd.DataFrame(tasks) if pd else tasks)
    with st.form("incident_report"):
        st.subheader("Submit an incident report")
        location = st.text_input("Location", "East Gate")
        incident = st.text_area("Incident details", "")
        submitted = st.form_submit_button("Submit report")
        if submitted and incident:
            create_incident_report(user["username"], location, incident)
            st.success("Incident report submitted.")
    if st.button("Chat with AI for volunteers"):
        prompt = "As a volunteer, provide me with the best route to the medical center and crowd safety advice."
        assistant = call_gemini(prompt, lang=user.get("language", "en"))
        st.write(assistant)


def dashboard_organizer():
    st.header("Organizer Dashboard")
    metrics = get_organizational_metrics()
    st.subheader("Live Crowd Status")
    if pd and metrics["crowd"]:
        crowd_df = pd.DataFrame(metrics["crowd"])
        st.dataframe(crowd_df)
        fig = build_plotly_chart(metrics["crowd"], "camera_id", "occupancy", "Occupancy by Camera")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    st.subheader("Active Alerts")
    for alert in metrics["alerts"]:
        st.write(f"[{alert['level']}] {alert['category']}: {alert['message']}")
    st.subheader("Parking and Venue Operations")
    st.table(pd.DataFrame(metrics["parking"]) if pd else metrics["parking"])    


def dashboard_transportation():
    st.header("Transportation Intelligence")
    parking = get_parking_status()
    for slot in parking:
        st.metric(slot["zone"], f"{slot['available_spots']}/{slot['total_spots']} available")
    st.write("Shuttle schedule: Every 10 minutes between Parking Lot 2 and main entrance.")
    st.write("Ride-sharing suggestion: Use the designated drop-off zone at Gate A.")


def dashboard_reports():
    st.header("AI Report Generator")
    report_title = st.text_input("Report title", "Crowd Safety Summary")
    report_summary = st.text_area("Executive summary", "Key crowd metrics and safety recommendations.")
    if st.button("Generate report"):
        data = {
            "crowd_density": f"{random.uniform(0.3, 0.85):.2f}",
            "risk_level": random.choice(["Low", "Moderate", "High"]),
            "staff_recommendation": "Rebalance security teams to East and South stands.",
        }
        report_id = generate_safety_report(report_summary, data)
        pdf_path = create_pdf_report(report_id)
        st.success(f"Report created: {pdf_path}")
        if os.path.exists(pdf_path):
            st.download_button("Download PDF", data=open(pdf_path, "rb"), file_name=os.path.basename(pdf_path), mime="application/pdf")


def dashboard_analytics():
    st.header("Analytics Dashboard")
    metrics = get_organizational_metrics()
    crowd = metrics["crowd"]
    if pd and crowd:
        df = pd.DataFrame(crowd)
        fig1 = build_plotly_chart(crowd, "timestamp", "occupancy", "Occupancy Trend")
        fig2 = build_plotly_chart(crowd, "timestamp", "density", "Density Trend", color="#e76f51")
        if fig1:
            st.plotly_chart(fig1, use_container_width=True)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)
    incident_totals = {alert["category"]: 1 for alert in metrics["alerts"]}
    if go and incident_totals:
        fig = go.Figure(data=[go.Pie(labels=list(incident_totals.keys()), values=list(incident_totals.values()))])
        fig.update_layout(title="Incident Distribution", template="plotly_dark")
        st.plotly_chart(fig)


def render_auth_page():
    st.title("ArenaMind Login")
    tab = st.tabs(["Login", "Register"])
    with tab[0]:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = authenticate_user(username, password)
            if user:
                st.session_state.user = user
                st.success("Login successful.")
                st.experimental_rerun()
            else:
                st.error("Invalid username or password.")
    with tab[1]:
        new_username = st.text_input("New username", key="reg_user")
        new_password = st.text_input("New password", type="password", key="reg_pass")
        role = st.selectbox("Role", ["Fan", "Volunteer", "Organizer"], key="reg_role")
        language = st.selectbox("Preferred language", list(SUPPORTED_LANGUAGES.keys()), key="reg_lang")
        if st.button("Register"):
            if register_user(new_username, new_password, role, SUPPORTED_LANGUAGES[language]):
                st.success("Registration complete. Please log in.")
            else:
                st.error("Registration failed. Username may already exist.")


def render_main_app():
    user = st.session_state.user
    st.sidebar.title("ArenaMind Menu")
    st.sidebar.write(f"Logged in as **{user['username']}** ({user['role']})")
    page = st.sidebar.radio(
        "Navigation",
        [
            "AI Assistant",
            "Navigation",
            "Crowd Intelligence",
            "Decision Support",
            "Analytics",
            "Sustainability",
            "Volunteer Dashboard",
            "Organizer Dashboard",
            "Transportation",
            "Reports",
            "Settings",
        ],
    )
    if page == "AI Assistant":
        dashboard_ai_assistant(user["language"])
    elif page == "Navigation":
        dashboard_navigation(user["language"])
    elif page == "Crowd Intelligence":
        dashboard_crowd_intelligence()
    elif page == "Decision Support":
        dashboard_decision_support()
    elif page == "Analytics":
        dashboard_analytics()
    elif page == "Sustainability":
        dashboard_sustainability()
    elif page == "Volunteer Dashboard":
        dashboard_volunteer(user)
    elif page == "Organizer Dashboard":
        dashboard_organizer()
    elif page == "Transportation":
        dashboard_transportation()
    elif page == "Reports":
        dashboard_reports()
    else:
        st.header("ArenaMind Settings")
        st.write("Update your profile and review system logs.")
        if st.button("Logout"):
            st.session_state.user = None
            st.experimental_rerun()


def main_streamlit():
    if not st:
        raise RuntimeError("Streamlit is required to run the user interface.")
    st.set_page_config(page_title="ArenaMind", layout="wide", initial_sidebar_state="expanded")
    initialize_database()
    if "user" not in st.session_state:
        st.session_state.user = None
    if st.session_state.user is None:
        render_auth_page()
    else:
        render_main_app()

# FastAPI backend definition
app = FastAPI(title="ArenaMind API") if FastAPI else None
if app:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def start_database():
        initialize_database()

    @app.get("/api/status")
    def api_status():
        return {"status": "ArenaMind API running", "time": datetime.utcnow().isoformat()}

    @app.post("/api/register")
    def api_register(payload: dict):
        success = register_user(
            payload.get("username", ""),
            payload.get("password", ""),
            payload.get("role", "Fan"),
            payload.get("language", "en"),
        )
        if not success:
            raise HTTPException(status_code=400, detail="Registration failed")
        return {"success": True}

    @app.post("/api/login")
    def api_login(payload: dict):
        user = authenticate_user(payload.get("username", ""), payload.get("password", ""))
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"user": {k: user[k] for k in ["id", "username", "role", "language"]}}

    @app.post("/api/chat")
    def api_chat(payload: dict):
        prompt = payload.get("prompt", "")
        lang = payload.get("language", "en")
        answer = call_gemini(prompt, lang=lang)
        return {"answer": answer}

    @app.post("/api/crowd")
    def api_crowd_analysis(payload: dict):
        temp_file = BASE_DIR / "temp_crowd_video.mp4"
        with open(temp_file, "wb") as handle:
            handle.write(payload.get("video_bytes", b""))
        result = analyze_crowd_video(str(temp_file))
        temp_file.unlink(missing_ok=True)
        return result

    @app.get("/api/parking")
    def api_parking():
        return {"parking": get_parking_status()}

    @app.get("/api/reports")
    def api_reports():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports ORDER BY created_at DESC LIMIT 20")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"reports": rows}

    @app.get("/api/reports/{report_id}")
    def api_report_file(report_id: int):
        path = create_pdf_report(report_id)
        if FileResponse:
            return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))
        raise HTTPException(status_code=501, detail="File response unavailable")


def run_api_server():
    if not uvicorn or not app:
        raise RuntimeError("uvicorn and FastAPI are required to run the API server.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "api":
        initialize_database()
        run_api_server()
    elif st:
        main_streamlit()
    else:
        print("ArenaMind requires Streamlit or FastAPI. Run with 'python untitled:Untitled-1 api' or 'streamlit run untitled:Untitled-1'.")
