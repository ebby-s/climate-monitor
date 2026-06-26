import math
import statistics
from datetime import datetime, timedelta

from src.database import (
    get_conn, parse_ts, now_iso,
    floor_to_5min, floor_to_30min,
    is_5min_boundary, is_30min_boundary
)

METRIC_COLS = [
    "temperature", "humidity", "voc_index", "nox_index", "ambient_light", "wet_bulb_temperature"
]

AVG_COLS = [
    "temperature_avg", "humidity_avg", "voc_avg", "nox_avg", "light_avg", "wet_bulb_temp_avg"
]

TREND_COLS = [
    "temperature_trend", "humidity_trend", "voc_trend", "nox_trend", "light_trend", "wet_bulb_temp_trend"
]


def compute_wet_bulb(temperature, humidity):
    if temperature is None or humidity is None:
        return None
    t = temperature
    rh = humidity
    rh = max(0, min(100, rh))
    tw = (t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
          + math.atan(t + rh)
          - math.atan(rh - 1.676331)
          + 0.00391838 * (rh ** 1.5) * math.atan(0.023101 * rh)
          - 4.686035)
    return tw


def save_reading(data):
    ts = now_iso()
    wb = compute_wet_bulb(data.get("temperature"), data.get("humidity"))
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO readings
           (timestamp, temperature, humidity, voc_index, nox_index, ambient_light, wet_bulb_temperature)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ts, data["temperature"], data["humidity"],
         data["voc_index"], data["nox_index"], data["ambient_light"], wb)
    )
    conn.commit()
    conn.close()
    return ts


def _compute_window_average(bucket_dt, window_minutes):
    window_start = bucket_dt - timedelta(minutes=window_minutes)
    bucket_iso = bucket_dt.isoformat()
    start_iso = window_start.isoformat()

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT AVG(temperature), AVG(humidity),
               AVG(voc_index), AVG(nox_index), AVG(ambient_light),
               AVG(wet_bulb_temperature)
        FROM readings
        WHERE timestamp > ? AND timestamp <= ?
    """, (start_iso, bucket_iso))
    row = c.fetchone()
    conn.close()

    if row and row[0] is not None:
        return {
            "temperature_avg": row[0],
            "humidity_avg": row[1],
            "voc_avg": row[2],
            "nox_avg": row[3],
            "light_avg": row[4],
            "wet_bulb_temp_avg": row[5],
        }
    return None


def _compute_30m_average(bucket_dt):
    return _compute_window_average(bucket_dt, 30)


def _compute_6h_trend(bucket_dt):
    return _compute_window_average(bucket_dt, 360)


def _upsert_rollup(bucket_dt, avgs):
    bucket_iso = bucket_dt.isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO rollup_30m
            (bucket_timestamp, temperature_avg, humidity_avg, voc_avg, nox_avg, light_avg, wet_bulb_temp_avg)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(bucket_timestamp) DO UPDATE SET
            temperature_avg = excluded.temperature_avg,
            humidity_avg = excluded.humidity_avg,
            voc_avg = excluded.voc_avg,
            nox_avg = excluded.nox_avg,
            light_avg = excluded.light_avg,
            wet_bulb_temp_avg = excluded.wet_bulb_temp_avg
    """, (bucket_iso, avgs["temperature_avg"], avgs["humidity_avg"],
          avgs["voc_avg"], avgs["nox_avg"], avgs["light_avg"],
          avgs["wet_bulb_temp_avg"]))
    conn.commit()
    conn.close()


def _upsert_trend(bucket_dt, avgs):
    bucket_iso = bucket_dt.isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO trend_6h
            (bucket_timestamp, temperature_trend, humidity_trend,
             voc_trend, nox_trend, light_trend, wet_bulb_temp_trend)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(bucket_timestamp) DO UPDATE SET
            temperature_trend = excluded.temperature_trend,
            humidity_trend = excluded.humidity_trend,
            voc_trend = excluded.voc_trend,
            nox_trend = excluded.nox_trend,
            light_trend = excluded.light_trend,
            wet_bulb_temp_trend = excluded.wet_bulb_temp_trend
    """, (bucket_iso, avgs["temperature_avg"], avgs["humidity_avg"],
          avgs["voc_avg"], avgs["nox_avg"], avgs["light_avg"],
          avgs["wet_bulb_temp_avg"]))
    conn.commit()
    conn.close()


def maybe_update_rollup(ts_iso):
    dt = parse_ts(ts_iso)
    if dt is None:
        return

    if is_5min_boundary(dt):
        bucket = floor_to_5min(dt)
        avgs = _compute_30m_average(bucket)
        if avgs:
            _upsert_rollup(bucket, avgs)

    if is_30min_boundary(dt):
        bucket = floor_to_30min(dt)
        avgs = _compute_6h_trend(bucket)
        if avgs:
            _upsert_trend(bucket, avgs)


def _backfill(table_name, bucket_fn, delta_minutes, compute_fn, upsert_fn):
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

    start_bucket = bucket_fn(start_dt)
    end_bucket = bucket_fn(end_dt)

    c.execute(f"SELECT bucket_timestamp FROM {table_name}")
    existing = {row[0] for row in c.fetchall()}
    conn.close()

    current = start_bucket
    while current <= end_bucket:
        bucket_iso = current.isoformat()
        if bucket_iso not in existing:
            avgs = compute_fn(current)
            if avgs:
                upsert_fn(current, avgs)
        current += timedelta(minutes=delta_minutes)


def backfill_rollups():
    _backfill("rollup_30m", floor_to_5min, 5, _compute_30m_average, _upsert_rollup)


def backfill_trends():
    _backfill("trend_6h", floor_to_30min, 30, _compute_6h_trend, _upsert_trend)


def get_recent_readings(limit):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT timestamp, temperature, humidity, voc_index, nox_index, ambient_light, wet_bulb_temperature
        FROM readings
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    rows.reverse()
    return [
        {
            "timestamp": r[0],
            "temperature": r[1],
            "humidity": r[2],
            "voc_index": r[3],
            "nox_index": r[4],
            "ambient_light": r[5],
            "wet_bulb_temperature": r[6],
        }
        for r in rows
    ]


def get_rollups():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT bucket_timestamp, temperature_avg, humidity_avg,
               voc_avg, nox_avg, light_avg, wet_bulb_temp_avg
        FROM rollup_30m
        ORDER BY bucket_timestamp ASC
    """)
    rows = c.fetchall()
    conn.close()
    return [
        {
            "timestamp": r[0],
            "temperature_avg": r[1],
            "humidity_avg": r[2],
            "voc_avg": r[3],
            "nox_avg": r[4],
            "light_avg": r[5],
            "wet_bulb_temp_avg": r[6],
        }
        for r in rows
    ]


def get_trends():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT bucket_timestamp, temperature_trend, humidity_trend,
               voc_trend, nox_trend, light_trend, wet_bulb_temp_trend
        FROM trend_6h
        ORDER BY bucket_timestamp ASC
    """)
    rows = c.fetchall()
    conn.close()
    return [
        {
            "timestamp": r[0],
            "temperature_trend": r[1],
            "humidity_trend": r[2],
            "voc_trend": r[3],
            "nox_trend": r[4],
            "light_trend": r[5],
            "wet_bulb_temp_trend": r[6],
        }
        for r in rows
    ]


def get_total_count():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM readings")
    count = c.fetchone()[0]
    conn.close()
    return count


def get_prev3day_profile():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT MAX(timestamp) FROM readings")
    max_ts = c.fetchone()[0]
    if not max_ts:
        conn.close()
        return []
    latest = parse_ts(max_ts)
    if latest is None:
        conn.close()
        return []
    end = latest - timedelta(days=1)
    start = latest - timedelta(days=4)
    c.execute("""
        SELECT substr(timestamp, 12, 5) as time_of_day,
               AVG(temperature), AVG(humidity),
               AVG(voc_index), AVG(nox_index), AVG(ambient_light),
               AVG(wet_bulb_temperature)
        FROM readings
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY time_of_day
        ORDER BY time_of_day
    """, (start.isoformat(), end.isoformat()))
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        entry = {
            "time_of_day": r[0],
            "temperature": r[1],
            "humidity": r[2],
            "voc_index": r[3],
            "nox_index": r[4],
            "ambient_light": r[5],
            "wet_bulb_temperature": r[6],
        }
        result.append(entry)
    return result


def get_daily_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT date(timestamp) as day,
               temperature, humidity, voc_index, nox_index, ambient_light, wet_bulb_temperature
        FROM readings
        ORDER BY timestamp ASC
    """)
    rows = c.fetchall()
    conn.close()

    days = {}
    for r in rows:
        day = r[0]
        if day not in days:
            days[day] = {
                "temperature": [],
                "humidity": [],
                "voc_index": [],
                "nox_index": [],
                "ambient_light": [],
                "wet_bulb_temperature": [],
            }
        for i, key in enumerate(["temperature", "humidity", "voc_index", "nox_index", "ambient_light", "wet_bulb_temperature"], 1):
            if r[i] is not None:
                days[day][key].append(r[i])

    METRICS = ["temperature", "humidity", "voc_index", "nox_index", "ambient_light", "wet_bulb_temperature"]

    result = {}
    for day in sorted(days.keys()):
        result[day] = {}
        for metric in METRICS:
            vals = days[day][metric]
            if len(vals) >= 4:
                svals = sorted(vals)
                n = len(svals)
                qs = statistics.quantiles(svals, n=4)
                result[day][metric] = {
                    "min": svals[0],
                    "q1": qs[0],
                    "median": qs[1],
                    "q3": qs[2],
                    "max": svals[-1],
                    "mean": sum(svals) / n,
                }
            elif len(vals) > 0:
                svals = sorted(vals)
                result[day][metric] = {
                    "min": svals[0],
                    "q1": svals[0],
                    "median": svals[len(svals) // 2],
                    "q3": svals[-1],
                    "max": svals[-1],
                    "mean": sum(svals) / len(svals),
                }
    return result


def backfill_wet_bulb_readings():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, temperature, humidity FROM readings WHERE wet_bulb_temperature IS NULL")
    rows = c.fetchall()
    if not rows:
        conn.close()
        return 0
    updates = []
    for row in rows:
        wb = compute_wet_bulb(row[1], row[2])
        updates.append((wb, row[0]))
    c.executemany("UPDATE readings SET wet_bulb_temperature = ? WHERE id = ?", updates)
    conn.commit()
    count = len(updates)
    conn.close()
    return count


def backfill_wet_bulb_rollups():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE rollup_30m SET wet_bulb_temp_avg = (
            SELECT AVG(wet_bulb_temperature)
            FROM readings
            WHERE timestamp > strftime('%Y-%m-%dT%H:%M:%S', rollup_30m.bucket_timestamp, '-30 minutes')
              AND timestamp <= rollup_30m.bucket_timestamp
        )
        WHERE wet_bulb_temp_avg IS NULL
    """)
    count = c.rowcount
    conn.commit()
    conn.close()
    return count


def backfill_wet_bulb_trends():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE trend_6h SET wet_bulb_temp_trend = (
            SELECT AVG(wet_bulb_temperature)
            FROM readings
            WHERE timestamp > strftime('%Y-%m-%dT%H:%M:%S', trend_6h.bucket_timestamp, '-360 minutes')
              AND timestamp <= trend_6h.bucket_timestamp
        )
        WHERE wet_bulb_temp_trend IS NULL
    """)
    count = c.rowcount
    conn.commit()
    conn.close()
    return count


def recompute_wet_bulb_rollups_trends():
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE rollup_30m SET wet_bulb_temp_avg = NULL")
    rollup_count = c.rowcount
    c.execute("UPDATE trend_6h SET wet_bulb_temp_trend = NULL")
    trend_count = c.rowcount
    conn.commit()
    conn.close()
    backfill_wet_bulb_rollups()
    backfill_wet_bulb_trends()
    return rollup_count, trend_count
