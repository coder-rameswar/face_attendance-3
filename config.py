# config.py — works for local dev (.env file) and Railway (env vars)
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# ── Railway provides a single MYSQL_URL — parse it if present ──
_mysql_url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL', '')

if _mysql_url and _mysql_url.startswith('mysql'):
    _p = urlparse(_mysql_url)
    DB_CONFIG = {
        'host':       _p.hostname,
        'port':       _p.port or 3306,
        'user':       _p.username,
        'password':   _p.password,
        'database':   _p.path.lstrip('/'),
        'charset':    'utf8mb4',
        'autocommit': True,
    }
else:
    # Local / manual env vars
    DB_CONFIG = {
        'host':       os.environ.get('DB_HOST', 'localhost'),
        'port':       int(os.environ.get('DB_PORT', 3306)),
        'user':       os.environ.get('DB_USER', 'root'),
        'password':   os.environ.get('DB_PASSWORD', ''),
        'database':   os.environ.get('DB_NAME', 'face_attendance_db'),
        'charset':    'utf8mb4',
        'autocommit': True,
    }

# ── Paths ─────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
FACE_DATA_DIR  = os.path.join(BASE_DIR, 'face_data')
MODEL_DIR      = os.path.join(BASE_DIR, 'trained_model')
SECRET_KEY     = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
UPLOAD_FOLDER  = os.path.join(BASE_DIR, 'static', 'uploads')

# ── Face recognition ──────────────────────────────────────────
SAMPLE_COUNT           = int(os.environ.get('SAMPLE_COUNT', 30))
CONFIDENCE_THRESHOLD   = int(os.environ.get('CONFIDENCE_THRESHOLD', 70))
RECOGNITION_THRESHOLD  = int(os.environ.get('RECOGNITION_THRESHOLD', 85))
