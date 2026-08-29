"""Build a synthetic Health Connect export for testing the importer.

The schema mirrors what was read from AOSP source (see docs/health-connect-formats.md). It is
deliberately partial: only the tables the importer reads are created, and one table the
importer looks for is left out so that the missing-table path is exercised. Values use the
stored units, so energy is in calories rather than kilocalories and glucose is in mmol/L.
"""

import math
import random
import sqlite3
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
DB = OUT / "health_connect_export.db"
ZIP = OUT / "health_connect_export.zip"

BST = 3600  # zone offset in seconds, as Health Connect stores it


def ms(dt):
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def base_cols():
    return """
        row_id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid BLOB,
        client_record_id TEXT,
        client_record_version INTEGER,
        app_info_id INTEGER,
        device_info_id INTEGER,
        last_modified_time INTEGER,
        recording_method INTEGER,
        dedupe_hash BLOB
    """


def interval_cols():
    return """
        start_time INTEGER,
        end_time INTEGER,
        start_zone_offset INTEGER,
        end_zone_offset INTEGER,
        local_date INTEGER
    """


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("PRAGMA user_version = 14")

    cur.execute(f"""CREATE TABLE exercise_session_record_table (
        {base_cols()}, {interval_cols()},
        exercise_type INTEGER, title TEXT, notes TEXT, has_route INTEGER,
        planned_exercise_session_id BLOB)""")
    cur.execute("""CREATE TABLE heart_rate_record_series_table (
        row_id INTEGER PRIMARY KEY AUTOINCREMENT, parent_key INTEGER NOT NULL,
        epoch_millis INTEGER, beats_per_minute INTEGER)""")
    cur.execute(f"""CREATE TABLE heart_rate_record_table ({base_cols()}, {interval_cols()})""")
    for name, col, typ in [
        ("steps_record_table", "count", "INTEGER"),
        ("distance_record_table", "distance", "REAL"),
        ("active_calories_burned_record_table", "energy", "REAL"),
        ("total_calories_burned_record_table", "energy", "REAL"),
        ("elevation_gained_record_table", "elevation", "REAL"),
    ]:
        cur.execute(f"CREATE TABLE {name} ({base_cols()}, {interval_cols()}, {col} {typ})")

    cur.execute(f"""CREATE TABLE resting_heart_rate_record_table (
        {base_cols()}, time INTEGER, zone_offset INTEGER, local_date INTEGER,
        beats_per_minute INTEGER)""")
    cur.execute(f"""CREATE TABLE blood_glucose_record_table (
        {base_cols()}, time INTEGER, zone_offset INTEGER, local_date INTEGER,
        level REAL, specimen_source INTEGER, relation_to_meal INTEGER, meal_type INTEGER)""")
    cur.execute(f"""CREATE TABLE nutrition_record_table (
        {base_cols()}, {interval_cols()}, total_carbohydrate REAL, protein REAL, total_fat REAL,
        energy REAL, meal_name TEXT, meal_type INTEGER)""")
    cur.execute("""CREATE TABLE exercise_laps_table (
        row_id INTEGER PRIMARY KEY AUTOINCREMENT, parent_key INTEGER NOT NULL,
        lap_start_time INTEGER, lap_end_time INTEGER, lap_length REAL)""")
    cur.execute("""CREATE TABLE application_info_table (
        row_id INTEGER PRIMARY KEY AUTOINCREMENT, app_name TEXT, package_name TEXT,
        app_icon BLOB, record_types_used TEXT)""")
    # exercise_segments_table and sleep_session_record_table are deliberately absent, so the
    # importer's missing-table path is exercised by the fixture rather than only in theory.

    cur.execute("INSERT INTO application_info_table (row_id, app_name, package_name) VALUES "
                "(1, 'Strava', 'com.strava'), (2, 'Fitbit', 'com.fitbit.FitbitMobile')")

    rng = random.Random(20260829)
    day0 = datetime(2026, 8, 1, 0, 0, 0)

    # Three sessions with contrasting shapes: a steady evening run, a morning strength session,
    # and a long weekend ride. Platform enum values, since this is the platform-written export.
    specs = [
        # (day, hour, minutes, platform type, title, mean HR, HR spread, distance m, kcal, app)
        (2, 18, 45, 33, "Evening run", 148, 9, 8200, 520, 1),
        (3, 7, 40, 45, "Push day", 112, 22, None, 240, 2),
        (5, 9, 165, 4, "Sunday club ride", 132, 14, 62000, 1450, 1),
        (7, 12, 30, 53, "Walk to town", 96, 7, 2400, 110, 2),
    ]

    for i, (day, hour, mins, xtype, title, hr_mean, hr_sd, dist, kcal, app) in enumerate(specs, 1):
        start = day0 + timedelta(days=day, hours=hour)
        end = start + timedelta(minutes=mins)
        cur.execute(
            """INSERT INTO exercise_session_record_table
               (row_id, uuid, app_info_id, start_time, end_time, start_zone_offset,
                end_zone_offset, exercise_type, title, has_route)
               VALUES (?,?,?,?,?,?,?,?,?,0)""",
            (i, bytes([i] * 16), app, ms(start), ms(end), BST, BST, xtype, title),
        )
        # Heart rate every 10 s, with a warm-up ramp so the intensity estimator has structure.
        t = start
        n = 0
        while t < end:
            frac = (t - start).total_seconds() / (mins * 60)
            ramp = min(1.0, frac / 0.12)
            drift = 6 * math.sin(frac * math.pi * 3)
            bpm = int(round(60 + (hr_mean - 60) * ramp + drift + rng.gauss(0, hr_sd * 0.3)))
            cur.execute(
                "INSERT INTO heart_rate_record_series_table (parent_key, epoch_millis, "
                "beats_per_minute) VALUES (?,?,?)", (i, ms(t), max(45, min(210, bpm))))
            t += timedelta(seconds=10)
            n += 1

        # Distance and calorie records are emitted on the writing app's own 15-minute cadence
        # and straddle the session boundaries, which is what the overlap apportioning is for.
        bucket_start = start - timedelta(minutes=7)
        while bucket_start < end:
            bucket_end = bucket_start + timedelta(minutes=15)
            share = 15 / mins
            if dist:
                cur.execute(
                    "INSERT INTO distance_record_table (start_time, end_time, "
                    "start_zone_offset, end_zone_offset, distance) VALUES (?,?,?,?,?)",
                    (ms(bucket_start), ms(bucket_end), BST, BST, dist * share))
            cur.execute(
                "INSERT INTO active_calories_burned_record_table (start_time, end_time, "
                "start_zone_offset, end_zone_offset, energy) VALUES (?,?,?,?,?)",
                # Energy is stored in calories, so a kcal figure is multiplied by 1000.
                (ms(bucket_start), ms(bucket_end), BST, BST, kcal * share * 1000))
            cur.execute(
                "INSERT INTO steps_record_table (start_time, end_time, start_zone_offset, "
                "end_zone_offset, count) VALUES (?,?,?,?,?)",
                (ms(bucket_start), ms(bucket_end), BST, BST, int(1400 * share)))
            bucket_start = bucket_end

    for d in range(0, 30):
        t = day0 + timedelta(days=d, hours=4)
        cur.execute("INSERT INTO resting_heart_rate_record_table (time, zone_offset, "
                    "beats_per_minute) VALUES (?,?,?)", (ms(t), BST, 52 + rng.randint(-3, 3)))

    for d in range(0, 10):
        t = day0 + timedelta(days=d, hours=8, minutes=30)
        cur.execute("INSERT INTO blood_glucose_record_table (time, zone_offset, level, "
                    "specimen_source, relation_to_meal) VALUES (?,?,?,2,3)",
                    (ms(t), BST, round(rng.uniform(4.5, 9.5), 1)))
        cur.execute("INSERT INTO nutrition_record_table (start_time, end_time, "
                    "start_zone_offset, end_zone_offset, total_carbohydrate, meal_name, "
                    "meal_type) VALUES (?,?,?,?,?,?,1)",
                    (ms(t), ms(t + timedelta(minutes=20)), BST, BST,
                     round(rng.uniform(30, 70), 1), "Breakfast"))

    con.commit()
    con.close()

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(DB, "health_connect_export.db")

    print(f"db  {DB} {DB.stat().st_size / 1024:.0f} KiB")
    print(f"zip {ZIP} {ZIP.stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    build()
