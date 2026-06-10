from datetime import timedelta

from src.database import (
    get_conn, parse_ts, now_iso,
    floor_to_5min, floor_to_30min,
    is_5min_boundary, is_30min_boundary
)

def save_reading(temp, hum):
    ts = now_iso()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO readings (timestamp, temperature, humidity) VALUES (?, ?, ?)",
        (ts, temp, hum)
    )
    conn.commit()
    conn.close()
    return ts

def compute_window_average_at(bucket_dt, window_minutes):
    window_start = bucket_dt - timedelta(minutes=window_minutes)
    bucket_iso = bucket_dt.isoformat()
    start_iso = window_start.isoformat()

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT AVG(temperature), AVG(humidity)
        FROM readings
        WHERE timestamp > ? AND timestamp <= ?
    """, (start_iso, bucket_iso))
    row = c.fetchone()
    conn.close()

    if row and row[0] is not None and row[1] is not None:
        return row[0], row[1]
    return None, None

def compute_30m_average_at(bucket_dt):
    return compute_window_average_at(bucket_dt, 30)

def compute_6h_trend_at(bucket_dt):
    return compute_window_average_at(bucket_dt, 360)

def update_rollup_for_bucket(bucket_dt):
    bucket_iso = bucket_dt.isoformat()
    temp_avg, hum_avg = compute_30m_average_at(bucket_dt)

    if temp_avg is None or hum_avg is None:
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO avg_30m_5min (bucket_timestamp, temperature_avg, humidity_avg)
        VALUES (?, ?, ?)
        ON CONFLICT(bucket_timestamp) DO UPDATE SET
            temperature_avg = excluded.temperature_avg,
            humidity_avg = excluded.humidity_avg
    """, (bucket_iso, temp_avg, hum_avg))
    conn.commit()
    conn.close()

def update_trend_for_bucket(bucket_dt):
    bucket_iso = bucket_dt.isoformat()
    temp_trend, hum_trend = compute_6h_trend_at(bucket_dt)

    if temp_trend is None or hum_trend is None:
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO trend_6h_30min (bucket_timestamp, temperature_trend, humidity_trend)
        VALUES (?, ?, ?)
        ON CONFLICT(bucket_timestamp) DO UPDATE SET
            temperature_trend = excluded.temperature_trend,
            humidity_trend = excluded.humidity_trend
    """, (bucket_iso, temp_trend, hum_trend))
    conn.commit()
    conn.close()

def maybe_update_rollup_for_time(ts_iso):
    dt = parse_ts(ts_iso)
    if dt is None:
        return

    if is_5min_boundary(dt):
        update_rollup_for_bucket(floor_to_5min(dt))

    if is_30min_boundary(dt):
        update_trend_for_bucket(floor_to_30min(dt))

def backfill_rollups():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM readings")
    min_ts, max_ts = c.fetchone()

    if not min_ts or not max_ts:
        conn.close()
        return

    start_dt = parse_ts(min_ts)
    end_dt = parse_ts(max_ts)

    if start_dt is None or end_dt is None:
        conn.close()
        return

    start_bucket = floor_to_5min(start_dt)
    end_bucket = floor_to_5min(end_dt)

    c.execute("SELECT bucket_timestamp FROM avg_30m_5min")
    existing = {row[0] for row in c.fetchall()}
    conn.close()

    current = start_bucket
    inserts = []

    while current <= end_bucket:
        bucket_iso = current.isoformat()
        if bucket_iso not in existing:
            temp_avg, hum_avg = compute_30m_average_at(current)
            if temp_avg is not None and hum_avg is not None:
                inserts.append((bucket_iso, temp_avg, hum_avg))
        current += timedelta(minutes=5)

    if inserts:
        conn = get_conn()
        c = conn.cursor()
        c.executemany("""
            INSERT OR REPLACE INTO avg_30m_5min (bucket_timestamp, temperature_avg, humidity_avg)
            VALUES (?, ?, ?)
        """, inserts)
        conn.commit()
        conn.close()

def backfill_trends():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM readings")
    min_ts, max_ts = c.fetchone()

    if not min_ts or not max_ts:
        conn.close()
        return

    start_dt = parse_ts(min_ts)
    end_dt = parse_ts(max_ts)

    if start_dt is None or end_dt is None:
        conn.close()
        return

    start_bucket = floor_to_30min(start_dt)
    end_bucket = floor_to_30min(end_dt)

    c.execute("SELECT bucket_timestamp FROM trend_6h_30min")
    existing = {row[0] for row in c.fetchall()}
    conn.close()

    current = start_bucket
    inserts = []

    while current <= end_bucket:
        bucket_iso = current.isoformat()
        if bucket_iso not in existing:
            temp_trend, hum_trend = compute_6h_trend_at(current)
            if temp_trend is not None and hum_trend is not None:
                inserts.append((bucket_iso, temp_trend, hum_trend))
        current += timedelta(minutes=30)

    if inserts:
        conn = get_conn()
        c = conn.cursor()
        c.executemany("""
            INSERT OR REPLACE INTO trend_6h_30min (bucket_timestamp, temperature_trend, humidity_trend)
            VALUES (?, ?, ?)
        """, inserts)
        conn.commit()
        conn.close()

def get_recent_readings(limit):
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT timestamp, temperature, humidity
        FROM readings
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()

    rows.reverse()

    return [
        {"timestamp": r[0], "temperature": r[1], "humidity": r[2]}
        for r in rows
    ]

def get_rollups():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT bucket_timestamp, temperature_avg, humidity_avg
        FROM avg_30m_5min
        ORDER BY bucket_timestamp ASC
    """)
    rows = c.fetchall()
    conn.close()

    return [
        {"timestamp": r[0], "temperature_avg": r[1], "humidity_avg": r[2]}
        for r in rows
    ]

def get_trends():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT bucket_timestamp, temperature_trend, humidity_trend
        FROM trend_6h_30min
        ORDER BY bucket_timestamp ASC
    """)
    rows = c.fetchall()
    conn.close()

    return [
        {"timestamp": r[0], "temperature_trend": r[1], "humidity_trend": r[2]}
        for r in rows
    ]

def get_total_count():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM readings")
    count = c.fetchone()[0]
    conn.close()

    return count
