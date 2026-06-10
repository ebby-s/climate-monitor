import os
import sqlite3
from datetime import datetime

from src.config import DB_PATH, DB_DIR

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS avg_30m_5min (
            bucket_timestamp TEXT PRIMARY KEY,
            temperature_avg REAL NOT NULL,
            humidity_avg REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trend_6h_30min (
            bucket_timestamp TEXT PRIMARY KEY,
            temperature_trend REAL NOT NULL,
            humidity_trend REAL NOT NULL
        )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)")
    conn.commit()
    conn.close()

def parse_ts(ts):
    try:
        dt = datetime.fromisoformat(ts)

        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)

        return dt
    except Exception:
        return None

def now_iso():
    return datetime.now().isoformat()

def floor_to_5min(dt):
    return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)

def floor_to_30min(dt):
    return dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)

def is_5min_boundary(dt):
    return dt.minute % 5 == 0

def is_30min_boundary(dt):
    return dt.minute % 30 == 0
