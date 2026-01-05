#!/usr/bin/env python3
"""
Sync production database readings to local SQLite via railway connect.

Usage:
    python sync_prod_db.py
"""

import subprocess
import csv
import io
import os
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, HeaterReading

LOCAL_DB = "sqlite:///./heater.db"
RAILWAY_CLI = "./tools/node_modules/.bin/railway"


def export_from_prod(limit: int = 10000) -> list[dict]:
    """Export readings from production via railway connect."""
    query = f"COPY (SELECT * FROM heater_readings ORDER BY timestamp DESC LIMIT {limit}) TO STDOUT WITH CSV HEADER;"

    result = subprocess.run(
        [RAILWAY_CLI, "connect", "postgres"],
        input=query,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)) or "."
    )

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return []

    reader = csv.DictReader(io.StringIO(result.stdout))
    return list(reader)


def import_to_local(readings: list[dict]):
    """Import readings to local SQLite database."""
    engine = create_engine(LOCAL_DB)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Clear existing readings
    db.query(HeaterReading).delete()

    count = 0
    for r in readings:
        reading = HeaterReading(
            timestamp=datetime.fromisoformat(r['timestamp']),
            power=r['power'] == 't',
            outdoor_temp_f=int(r['outdoor_temp_f']) if r['outdoor_temp_f'] else None,
            current_temp_f=int(r['current_temp_f']) if r['current_temp_f'] else None,
            target_temp_f=int(r['target_temp_f']) if r['target_temp_f'] else None,
            heat_mode=r['heat_mode'] or None,
            active_heat_level=int(r['active_heat_level']) if r['active_heat_level'] else None,
            power_watts=int(r['power_watts']) if r['power_watts'] else None,
            oscillation=r['oscillation'] == 't',
            display=r['display'] == 't',
            person_detection=r['person_detection'] == 't',
            auto_on=r['auto_on'] == 't',
            detection_timeout=int(r['detection_timeout']) if r['detection_timeout'] else None,
            timer_remaining_sec=int(r['timer_remaining_sec']) if r['timer_remaining_sec'] else None,
            energy_kwh=float(r['energy_kwh']) if r['energy_kwh'] else None,
            fault_code=int(r['fault_code']) if r['fault_code'] else None,
        )
        db.add(reading)
        count += 1

    db.commit()
    db.close()
    return count


if __name__ == "__main__":
    print("Exporting from production database...")
    readings = export_from_prod(limit=10000)
    print(f"Got {len(readings)} readings")

    if readings:
        print("Importing to local database...")
        count = import_to_local(readings)
        print(f"Synced {count} readings to local database")
    else:
        print("No readings to sync")
