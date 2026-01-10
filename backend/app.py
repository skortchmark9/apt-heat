"""
Backend server for heater monitoring.

Receives telemetry from local driver, stores in DB, serves web UI,
and returns setpoints to the driver.
"""

import os
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from pathlib import Path
from fastapi import FastAPI, Depends, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from models import Base, HeaterReading, SleepSchedule, AppSettings
from rates import calculate_savings_from_readings, get_tou_period, get_rate_for_period

load_dotenv()


def run_migrations(engine):
    """Run schema migrations for existing databases."""
    from sqlalchemy import text, inspect

    with engine.connect() as conn:
        inspector = inspect(engine)

        # Add heater_automation_enabled column if missing
        if 'app_settings' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('app_settings')]
            if 'heater_automation_enabled' not in columns:
                conn.execute(text('ALTER TABLE app_settings ADD COLUMN heater_automation_enabled BOOLEAN DEFAULT TRUE'))
                conn.commit()
                print("[MIGRATION] Added heater_automation_enabled column")

# Timezone for sleep schedule (user's local time)
LOCAL_TZ = ZoneInfo("America/New_York")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./heater.db")
# Railway uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Global state (loaded from DB)
battery_automation_enabled = True
heater_automation_enabled = True

# Cache of latest channel data from driver
latest_channels = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_settings():
    """Load app settings from database."""
    db = SessionLocal()
    try:
        settings = db.query(AppSettings).filter(AppSettings.id == 1).first()
        if settings is None:
            settings = AppSettings(id=1, battery_automation_enabled=True, heater_automation_enabled=True)
            db.add(settings)
            db.commit()
            return True, True
        return settings.battery_automation_enabled, settings.heater_automation_enabled
    finally:
        db.close()


def save_settings(battery_enabled: bool = None, heater_enabled: bool = None):
    """Save app settings to database."""
    db = SessionLocal()
    try:
        settings = db.query(AppSettings).filter(AppSettings.id == 1).first()
        if settings is None:
            settings = AppSettings(id=1)
            db.add(settings)
        if battery_enabled is not None:
            settings.battery_automation_enabled = battery_enabled
        if heater_enabled is not None:
            settings.heater_automation_enabled = heater_enabled
        db.commit()
    finally:
        db.close()


def load_sleep_schedule():
    """Load active sleep schedule from database."""
    db = SessionLocal()
    try:
        schedule = db.query(SleepSchedule).filter(SleepSchedule.id == 1).first()
        if not schedule or not schedule.start_time:
            return None
        return {
            "start_time": schedule.start_time.isoformat() + "Z",
            "wake_time": schedule.wake_time.isoformat() + "Z",
            "curve": json.loads(schedule.curve_json) if schedule.curve_json else []
        }
    finally:
        db.close()


def save_sleep_schedule(schedule):
    """Save sleep schedule to database."""
    db = SessionLocal()
    try:
        start_dt = datetime.fromisoformat(schedule["start_time"].replace("Z", "+00:00"))
        wake_dt = datetime.fromisoformat(schedule["wake_time"].replace("Z", "+00:00"))
        start_utc = start_dt.replace(tzinfo=None)
        wake_utc = wake_dt.replace(tzinfo=None)

        existing = db.query(SleepSchedule).filter(SleepSchedule.id == 1).first()
        if existing:
            existing.start_time = start_utc
            existing.wake_time = wake_utc
            existing.curve_json = json.dumps(schedule["curve"])
        else:
            new_schedule = SleepSchedule(
                id=1,
                start_time=start_utc,
                wake_time=wake_utc,
                curve_json=json.dumps(schedule["curve"])
            )
            db.add(new_schedule)
        db.commit()
    finally:
        db.close()


def clear_sleep_schedule():
    """Clear the sleep schedule from database."""
    db = SessionLocal()
    try:
        db.query(SleepSchedule).filter(SleepSchedule.id == 1).delete()
        db.commit()
    finally:
        db.close()


def get_sleep_target_temp():
    """Get target temp based on current sleep schedule, or None if not in sleep mode."""
    schedule = load_sleep_schedule()
    if not schedule:
        return None

    now = datetime.utcnow()
    start = datetime.fromisoformat(schedule['start_time'].replace("Z", ""))
    wake = datetime.fromisoformat(schedule['wake_time'].replace("Z", ""))

    if now < start or now > wake:
        clear_sleep_schedule()
        return None

    total_duration = (wake - start).total_seconds()
    elapsed = (now - start).total_seconds()
    progress = elapsed / total_duration

    points = schedule['curve']
    for i in range(len(points) - 1):
        if points[i]['progress'] <= progress <= points[i + 1]['progress']:
            p1, p2 = points[i], points[i + 1]
            segment_progress = (progress - p1['progress']) / (p2['progress'] - p1['progress'])
            temp = p1['temp'] + (p2['temp'] - p1['temp']) * segment_progress
            return int(round(temp))

    return points[-1]['temp'] if points else None


# =============================================================================
# TARGET CALCULATION
# =============================================================================

# User-adjustable targets (persisted separately from automation)
user_targets = {
    "heater_target_temp": 70,
    "heater_power": True,
    "heater_oscillation": False,
    "heater_display": True,
    "plug_on": True,
}


def calculate_targets():
    """
    Calculate current targets based on schedules and automation settings.

    Returns a flat dict of targets for the driver to apply.
    """
    global battery_automation_enabled, heater_automation_enabled

    targets = {
        # Heater targets
        "heater_power": user_targets.get("heater_power", True),
        "heater_target_temp": user_targets.get("heater_target_temp", 70),
        "heater_oscillation": user_targets.get("heater_oscillation", False),
        "heater_display": user_targets.get("heater_display", True),
        # Plug targets
        "plug_on": user_targets.get("plug_on", True),
        # Battery targets
        "battery_charge_power": 300,  # Default off-peak charging rate
    }

    # Sleep schedule override for heater target
    sleep_target = get_sleep_target_temp()
    if sleep_target is not None:
        targets["heater_target_temp"] = sleep_target
        targets["heater_sleep_mode"] = True

    # Battery automation based on TOU period
    if battery_automation_enabled:
        now = datetime.now(LOCAL_TZ)
        period = get_tou_period(now)
        if period == "off_peak":
            targets["battery_charge_power"] = 300  # Charge during off-peak
        else:
            targets["battery_charge_power"] = 0  # Stop charging during peak
        targets["battery_tou_period"] = period

    targets["battery_automation_enabled"] = battery_automation_enabled
    targets["heater_automation_enabled"] = heater_automation_enabled

    return targets


# =============================================================================
# FASTAPI APP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup."""
    global battery_automation_enabled, heater_automation_enabled

    # Run migrations for existing databases
    run_migrations(engine)

    # Create tables (for new databases)
    Base.metadata.create_all(bind=engine)

    # Load settings from DB
    battery_automation_enabled, heater_automation_enabled = load_settings()
    print(f"Battery automation: {'enabled' if battery_automation_enabled else 'DISABLED'}")
    print(f"Heater automation: {'enabled' if heater_automation_enabled else 'DISABLED'}")

    yield


app = FastAPI(title="Heater Monitor", lifespan=lifespan)

# Frontend build directory (one level up from backend/)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

# Mount static assets if frontend is built
if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")


# =============================================================================
# DRIVER SYNC ENDPOINT
# =============================================================================

def get_channel_value(channels: dict, key: str):
    """Extract value from flat channel format: {key: {value: X, last_updated: Y}}"""
    ch = channels.get(key, {})
    if isinstance(ch, dict):
        return ch.get("value")
    return ch


@app.post("/api/driver/sync")
async def driver_sync(request: Request):
    """
    Receive channel data from driver, store reading, return targets.

    Driver POSTs flat channels like:
      {"heater_power": {"value": true, "last_updated": "..."}, ...}

    Server responds with flat targets:
      {"targets": {"heater_target_temp": 70, "heater_power": true, ...}}
    """
    global latest_channels

    channels = await request.json()
    latest_channels = channels

    # Extract values from flat channel format for DB storage
    db = SessionLocal()
    try:
        reading = HeaterReading(
            timestamp=datetime.utcnow(),
            power=get_channel_value(channels, "heater_power"),
            current_temp_f=get_channel_value(channels, "heater_current_temp"),
            target_temp_f=get_channel_value(channels, "heater_target_temp"),
            heat_mode=get_channel_value(channels, "heater_heat_mode"),
            active_heat_level=get_channel_value(channels, "heater_active_heat_level"),
            power_watts=get_channel_value(channels, "battery_watts_out") or 0,
            oscillation=get_channel_value(channels, "heater_oscillation"),
            display=get_channel_value(channels, "heater_display"),
            person_detection=get_channel_value(channels, "heater_person_detection"),
            auto_on=get_channel_value(channels, "heater_auto_on"),
            detection_timeout=get_channel_value(channels, "heater_detection_timeout"),
            timer_remaining_sec=get_channel_value(channels, "heater_timer_value"),
            energy_kwh=get_channel_value(channels, "heater_energy_kwh"),
            fault_code=get_channel_value(channels, "heater_fault_code"),
            outdoor_temp_f=get_channel_value(channels, "weather_outdoor_temp"),
        )
        db.add(reading)
        db.commit()
    finally:
        db.close()

    # Calculate and return flat targets
    targets = calculate_targets()

    return {"targets": targets}


# =============================================================================
# FRONTEND ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/battery", response_class=HTMLResponse)
async def dashboard():
    """Serve the React dashboard."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Frontend not built</h1><p>Run npm build in frontend/</p>")


# =============================================================================
# API ENDPOINTS (for frontend)
# =============================================================================

@app.get("/api/readings")
async def get_readings(
    hours: int = Query(default=24, ge=1, le=168),
    max_points: int = Query(default=200, ge=10, le=1000),
    db: Session = Depends(get_db)
):
    """Get historical readings, downsampled for charting."""
    since = datetime.utcnow() - timedelta(hours=hours)
    readings = db.query(HeaterReading).filter(
        HeaterReading.timestamp >= since
    ).order_by(HeaterReading.timestamp).all()

    if len(readings) > max_points:
        step = len(readings) / max_points
        sampled = [readings[int(i * step)] for i in range(max_points)]
        sampled[-1] = readings[-1]
        readings = sampled

    return [
        {
            "timestamp": r.timestamp.isoformat() + "Z",
            "power": r.power,
            "current_temp_f": r.current_temp_f,
            "target_temp_f": r.target_temp_f,
            "heat_mode": r.heat_mode,
            "active_heat_level": r.active_heat_level,
            "power_watts": r.power_watts,
            "oscillation": r.oscillation,
            "outdoor_temp_f": r.outdoor_temp_f,
        }
        for r in readings
    ]


@app.get("/api/status")
async def get_status():
    """Get current status from latest driver sync."""
    return {
        "power": get_channel_value(latest_channels, "heater_power"),
        "current_temp_f": get_channel_value(latest_channels, "heater_current_temp"),
        "target_temp_f": get_channel_value(latest_channels, "heater_target_temp"),
        "heat_mode": get_channel_value(latest_channels, "heater_heat_mode"),
        "active_heat_level": get_channel_value(latest_channels, "heater_active_heat_level"),
        "power_watts": get_channel_value(latest_channels, "battery_watts_out") or 0,
        "oscillation": get_channel_value(latest_channels, "heater_oscillation"),
        "display": get_channel_value(latest_channels, "heater_display"),
    }


@app.get("/api/battery")
async def api_battery_status():
    """Get current battery status from latest driver sync."""
    global battery_automation_enabled

    soc = get_channel_value(latest_channels, "battery_soc")
    if soc is None:
        return {"configured": False, "automation_enabled": battery_automation_enabled}

    now = datetime.now(LOCAL_TZ)
    period = get_tou_period(now)

    return {
        "configured": True,
        "soc": soc,
        "watts_in": get_channel_value(latest_channels, "battery_watts_in") or 0,
        "watts_out": get_channel_value(latest_channels, "battery_watts_out") or 0,
        "charging": get_channel_value(latest_channels, "battery_charging") or False,
        "discharging": get_channel_value(latest_channels, "battery_discharging") or False,
        "tou_period": period,
        "automation_enabled": battery_automation_enabled,
    }


@app.post("/api/battery/automation/toggle")
async def toggle_battery_automation():
    """Toggle battery automation on/off."""
    global battery_automation_enabled
    battery_automation_enabled = not battery_automation_enabled
    save_settings(battery_enabled=battery_automation_enabled)
    return {"automation_enabled": battery_automation_enabled}


@app.post("/api/target")
async def set_target(data: dict):
    """Set target temperature."""
    temp = data.get("temp", 70)
    temp = max(41, min(95, int(temp)))
    user_targets["heater_target_temp"] = temp
    return {"target_temp_f": temp}


@app.post("/api/power/toggle")
async def toggle_power():
    """Toggle heater power (updates target for next driver sync)."""
    current = user_targets.get("heater_power", True)
    user_targets["heater_power"] = not current
    return {"power": not current}


@app.post("/api/oscillation/toggle")
async def toggle_oscillation():
    """Toggle oscillation (updates target for next driver sync)."""
    current = user_targets.get("heater_oscillation", False)
    user_targets["heater_oscillation"] = not current
    return {"oscillation": not current}


@app.post("/api/sleep")
async def start_sleep_mode(data: dict):
    """Start sleep mode with a temperature curve."""
    wake_time_str = data.get("wakeTime", "7:00 AM")
    curve = data.get("curve", [])

    time_part, ampm = wake_time_str.split(' ')
    hours, mins = map(int, time_part.split(':'))
    if ampm == 'PM' and hours != 12:
        hours += 12
    if ampm == 'AM' and hours == 12:
        hours = 0

    now_local = datetime.now(LOCAL_TZ)
    wake_local = now_local.replace(hour=hours, minute=mins, second=0, microsecond=0)
    if wake_local <= now_local:
        wake_local += timedelta(days=1)

    UTC = ZoneInfo("UTC")
    now_utc = now_local.astimezone(UTC)
    wake_utc = wake_local.astimezone(UTC)

    schedule = {
        "start_time": now_utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "wake_time": wake_utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "curve": curve
    }
    save_sleep_schedule(schedule)

    return {"status": "ok", "wake_time": schedule["wake_time"]}


@app.post("/api/sleep/cancel")
async def cancel_sleep_mode():
    """Cancel active sleep mode."""
    clear_sleep_schedule()
    return {"status": "ok"}


@app.get("/api/sleep")
async def get_sleep_status():
    """Get current sleep mode status."""
    schedule = load_sleep_schedule()
    if not schedule:
        return {"active": False}

    target = get_sleep_target_temp()
    if target is None:
        return {"active": False}

    now = datetime.utcnow()
    start = datetime.fromisoformat(schedule['start_time'].replace("Z", ""))
    wake = datetime.fromisoformat(schedule['wake_time'].replace("Z", ""))

    total_duration = (wake - start).total_seconds()
    elapsed = (now - start).total_seconds()
    progress = min(1.0, max(0.0, elapsed / total_duration))

    return {
        "active": True,
        "wake_time": schedule["wake_time"],
        "start_time": schedule["start_time"],
        "current_target": target,
        "progress": progress,
        "curve": schedule["curve"]
    }


@app.get("/api/savings")
async def get_savings(
    hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db)
):
    """Calculate peak shaving savings for the given time period."""
    since = datetime.utcnow() - timedelta(hours=hours)
    readings = db.query(HeaterReading).filter(
        HeaterReading.timestamp >= since
    ).order_by(HeaterReading.timestamp).all()

    if not readings:
        return {
            "hours": hours,
            "total_kwh": 0,
            "peak_kwh": 0,
            "offpeak_kwh": 0,
            "savings": 0,
            "current_period": get_tou_period(datetime.now()),
            "current_rate": get_rate_for_period(datetime.now())[1]
        }

    poll_interval = int(os.getenv("POLL_INTERVAL_SEC", "60"))
    result = calculate_savings_from_readings(readings, poll_interval)
    result["hours"] = hours
    result["current_period"] = get_tou_period(datetime.now())
    result["current_rate"] = get_rate_for_period(datetime.now())[1]

    return result
