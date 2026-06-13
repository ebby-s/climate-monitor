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
            temperature REAL,
            humidity REAL,
            voc_index REAL,
            nox_index REAL,
            ambient_light REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS rollup_30m (
            bucket_timestamp TEXT PRIMARY KEY,
            temperature_avg REAL,
            humidity_avg REAL,
            voc_avg REAL,
            nox_avg REAL,
            light_avg REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trend_6h (
            bucket_timestamp TEXT PRIMARY KEY,
            temperature_trend REAL,
            humidity_trend REAL,
            voc_trend REAL,
            nox_trend REAL,
            light_trend REAL
        )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)")
    c.execute("PRAGMA journal_mode=WAL;")
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
