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

# Weather config (NYC default)
WEATHER_LAT = float(os.getenv("WEATHER_LAT", "40.81"))
WEATHER_LON = float(os.getenv("WEATHER_LON", "-73.95"))
_cached_outdoor_temp = None
_cached_outdoor_temp_time = None


def get_outdoor_temp() -> int | None:
    """Fetch outdoor temp from Open-Meteo, cached for 5 minutes."""
    global _cached_outdoor_temp, _cached_outdoor_temp_time
    import urllib.request

    now = datetime.utcnow()
    if _cached_outdoor_temp_time and (now - _cached_outdoor_temp_time).seconds < 300:
        return _cached_outdoor_temp

    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}&longitude={WEATHER_LON}&current=temperature_2m&temperature_unit=fahrenheit"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            _cached_outdoor_temp = int(round(data["current"]["temperature_2m"]))
            _cached_outdoor_temp_time = now
            return _cached_outdoor_temp
    except Exception as e:
        print(f"[WEATHER] fetch error: {e}")
        return _cached_outdoor_temp  # Return stale cache on error


def run_migrations(engine):
    """Run schema migrations for existing databases."""
    from sqlalchemy import text, inspect

    with engine.connect() as conn:
        inspector = inspect(engine)

        if 'app_settings' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('app_settings')]

            # Add new columns if missing
            if 'driver_control_enabled' not in columns:
                conn.execute(text('ALTER TABLE app_settings ADD COLUMN driver_control_enabled BOOLEAN DEFAULT TRUE'))
                conn.commit()
                print("[MIGRATION] Added driver_control_enabled column")

            if 'automation_mode' not in columns:
                conn.execute(text("ALTER TABLE app_settings ADD COLUMN automation_mode VARCHAR DEFAULT 'tou'"))
                conn.commit()
                print("[MIGRATION] Added automation_mode column")

            if 'user_targets_json' not in columns:
                conn.execute(text("ALTER TABLE app_settings ADD COLUMN user_targets_json TEXT"))
                conn.commit()
                print("[MIGRATION] Added user_targets_json column")

            # Legacy migration (keep for backwards compat)
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
driver_control_enabled = True  # Master kill switch - driver ignores targets if False
automation_mode = "tou"  # "manual" | "tou"

# Bang-bang controller state for off-peak: "heating" or "charging"
offpeak_state = "heating"

# Cache of latest channel data from driver
latest_channels = {}

# =============================================================================
# STATS CACHE (in-memory running totals for today)
# =============================================================================

# Today's running stats - reset at midnight (local time)
_today_stats = {
    "date": None,  # date object for cache invalidation
    "total_wh": 0,
    "peak_wh": 0,
    "offpeak_wh": 0,
    "peak_cost": 0,
    "offpeak_cost": 0,
    "reading_count": 0,
    "temp_sum": 0,  # for averaging
    "outdoor_temp_sum": 0,
    "min_temp": None,
    "max_temp": None,
}


def update_today_stats(power_watts: int, timestamp: datetime, indoor_temp: int = None, outdoor_temp: int = None):
    """Update today's running stats with a new reading."""
    global _today_stats

    today = datetime.now(LOCAL_TZ).date()

    # Reset cache if it's a new day
    if _today_stats["date"] != today:
        _today_stats = {
            "date": today,
            "total_wh": 0,
            "peak_wh": 0,
            "offpeak_wh": 0,
            "peak_cost": 0,
            "offpeak_cost": 0,
            "reading_count": 0,
            "temp_sum": 0,
            "outdoor_temp_sum": 0,
            "min_temp": None,
            "max_temp": None,
        }

    if power_watts and power_watts > 0:
        # Assume ~60 second intervals between readings
        poll_interval = int(os.getenv("POLL_INTERVAL_SEC", "60"))
        wh = power_watts * (poll_interval / 3600)

        _today_stats["total_wh"] += wh

        # Get period and rate
        period, rate = get_rate_for_period(timestamp)

        if period == "off_peak":
            _today_stats["offpeak_wh"] += wh
            _today_stats["offpeak_cost"] += (wh / 1000) * rate
        else:
            _today_stats["peak_wh"] += wh
            _today_stats["peak_cost"] += (wh / 1000) * rate

    # Track temps for averaging
    _today_stats["reading_count"] += 1
    if indoor_temp is not None:
        _today_stats["temp_sum"] += indoor_temp
        if _today_stats["min_temp"] is None or indoor_temp < _today_stats["min_temp"]:
            _today_stats["min_temp"] = indoor_temp
        if _today_stats["max_temp"] is None or indoor_temp > _today_stats["max_temp"]:
            _today_stats["max_temp"] = indoor_temp
    if outdoor_temp is not None:
        _today_stats["outdoor_temp_sum"] += outdoor_temp


def get_today_stats() -> dict:
    """Get today's stats formatted for API response."""
    from rates import is_summer, TOU_SUMMER_OFFPEAK_RATE, TOU_WINTER_OFFPEAK_RATE

    today = datetime.now(LOCAL_TZ).date()

    # If cache is stale, return zeros
    if _today_stats["date"] != today:
        return {
            "date": today.isoformat(),
            "total_kwh": 0,
            "peak_kwh": 0,
            "offpeak_kwh": 0,
            "savings": 0,
            "would_have_cost": 0,
            "actual_cost": 0,
        }

    total_kwh = _today_stats["total_wh"] / 1000
    peak_kwh = _today_stats["peak_wh"] / 1000
    offpeak_kwh = _today_stats["offpeak_wh"] / 1000

    would_have_cost = _today_stats["peak_cost"] + _today_stats["offpeak_cost"]

    # Actual cost (all energy at off-peak rate)
    summer = is_summer(datetime.now(LOCAL_TZ))
    offpeak_rate = TOU_SUMMER_OFFPEAK_RATE if summer else TOU_WINTER_OFFPEAK_RATE
    actual_cost = total_kwh * offpeak_rate

    savings = would_have_cost - actual_cost

    result = {
        "date": today.isoformat(),
        "total_kwh": round(total_kwh, 2),
        "peak_kwh": round(peak_kwh, 2),
        "offpeak_kwh": round(offpeak_kwh, 2),
        "savings": round(savings, 2),
        "would_have_cost": round(would_have_cost, 2),
        "actual_cost": round(actual_cost, 2),
    }

    # Add temp stats if we have readings
    if _today_stats["reading_count"] > 0 and _today_stats["temp_sum"] > 0:
        result["avg_temp"] = round(_today_stats["temp_sum"] / _today_stats["reading_count"])
        result["min_temp"] = _today_stats["min_temp"]
        result["max_temp"] = _today_stats["max_temp"]

    return result


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
            settings = AppSettings(id=1, driver_control_enabled=True, automation_mode="tou")
            db.add(settings)
            db.commit()
            return True, "tou", {}

        # Parse user_targets_json
        saved_targets = {}
        if getattr(settings, 'user_targets_json', None):
            try:
                saved_targets = json.loads(settings.user_targets_json)
            except:
                pass

        return (
            getattr(settings, 'driver_control_enabled', True),
            getattr(settings, 'automation_mode', 'tou'),
            saved_targets
        )
    finally:
        db.close()


def save_settings(driver_enabled: bool = None, mode: str = None, targets: dict = None):
    """Save app settings to database."""
    db = SessionLocal()
    try:
        settings = db.query(AppSettings).filter(AppSettings.id == 1).first()
        if settings is None:
            settings = AppSettings(id=1)
            db.add(settings)
        if driver_enabled is not None:
            settings.driver_control_enabled = driver_enabled
        if mode is not None:
            settings.automation_mode = mode
        if targets is not None:
            settings.user_targets_json = json.dumps(targets)
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
    "battery_charge_power": 300,
}


def get_user_targets() -> dict:
    """Get current user target settings."""
    return {
        "plug_on": user_targets.get("plug_on", True),
        "heater_power": user_targets.get("heater_power", True),
        "heater_target_temp": user_targets.get("heater_target_temp", 70),
        "heater_heat_mode": user_targets.get("heater_heat_mode", "High"),
        "battery_charge_power": user_targets.get("battery_charge_power", 0),
    }


def get_automation_targets() -> dict:
    """
    Get automation overrides for TOU mode.

    Bang-bang controller during off-peak:
      HEATING state: charge=0, heat at target temp
      CHARGING state: charge=1500W, target-3 (heater off)

    Returns dict of targets to overlay on user targets.
    """
    global offpeak_state

    now = datetime.now(LOCAL_TZ)
    period = get_tou_period(now)
    auto_targets = {}

    desired_temp = user_targets.get("heater_target_temp", 70)

    # Sleep schedule override
    sleep_target = get_sleep_target_temp()
    if sleep_target is not None:
        desired_temp = sleep_target
        auto_targets["heater_sleep_mode"] = True

    if period == "off_peak":
        # Bang-bang controller: alternate between heating and charging
        current_temp = get_channel_value(latest_channels, "heater_current_temp")

        if current_temp is not None:
            # State transitions
            if offpeak_state == "heating" and current_temp >= desired_temp:
                offpeak_state = "charging"
                print(f"[AUTOMATION] Transition: HEATING -> CHARGING (temp={current_temp}°F >= desired={desired_temp}°F)")
            elif offpeak_state == "charging" and current_temp <= desired_temp - 2:
                offpeak_state = "heating"
                print(f"[AUTOMATION] Transition: CHARGING -> HEATING (temp={current_temp}°F <= {desired_temp - 2}°F)")

        if offpeak_state == "heating":
            auto_targets["battery_charge_power"] = 0
            auto_targets["heater_target_temp"] = desired_temp
            auto_targets["heater_heat_mode"] = "High"
        else:
            auto_targets["battery_charge_power"] = 1500
            auto_targets["heater_target_temp"] = desired_temp - 3
            auto_targets["heater_heat_mode"] = "High"

        auto_targets["offpeak_state"] = offpeak_state
    else:
        # Peak: no charging, normal heating
        auto_targets["battery_charge_power"] = 0
        auto_targets["heater_target_temp"] = desired_temp
        auto_targets["heater_heat_mode"] = "High"
        offpeak_state = "heating"  # Reset for next off-peak

    # SAFETY: Low battery + unplugged = turn off heater
    battery_soc = get_channel_value(latest_channels, "battery_soc")
    plug_on = user_targets.get("plug_on", True)
    if battery_soc is not None and battery_soc <= 5 and not plug_on:
        print(f"[SAFETY] Battery low ({battery_soc}%) and unplugged, disabling heater")
        auto_targets["heater_power"] = False

    return auto_targets


def calculate_targets():
    """
    Calculate current targets based on automation mode.

    Always starts with user targets, then overlays automation if enabled.
    """
    now = datetime.now(LOCAL_TZ)
    period = get_tou_period(now)

    # Base info (always included)
    targets = {
        "tou_period": period,
        "driver_control_enabled": driver_control_enabled,
        "automation_mode": automation_mode,
    }

    # Always apply user targets
    targets.update(get_user_targets())

    # Overlay automation targets if TOU mode enabled
    if automation_mode == "tou":
        targets.update(get_automation_targets())

    return targets


# =============================================================================
# FASTAPI APP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup."""
    global driver_control_enabled, automation_mode, user_targets

    # Run migrations for existing databases
    run_migrations(engine)

    # Create tables (for new databases)
    Base.metadata.create_all(bind=engine)

    # Load settings from DB
    driver_control_enabled, automation_mode, saved_targets = load_settings()
    if saved_targets:
        user_targets.update(saved_targets)
    print(f"Driver control: {'enabled' if driver_control_enabled else 'DISABLED'}")
    print(f"Automation mode: {automation_mode}")
    print(f"User targets: {user_targets}")

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
            outdoor_temp_f=get_outdoor_temp(),
        )
        db.add(reading)
        db.commit()

        # Update today's running stats
        update_today_stats(
            power_watts=reading.power_watts,
            timestamp=reading.timestamp,
            indoor_temp=reading.current_temp_f,
            outdoor_temp=reading.outdoor_temp_f,
        )
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
    """Get current status: device state from driver + server's targets.

    Returns both so UI can show current state AND update targets immediately.
    """
    # Get current targets from server (updates immediately when user changes)
    targets = calculate_targets()

    return {
        # Current device state (from driver)
        "power": get_channel_value(latest_channels, "heater_power"),
        "current_temp_f": get_channel_value(latest_channels, "heater_current_temp"),
        "heat_mode": get_channel_value(latest_channels, "heater_heat_mode"),
        "active_heat_level": get_channel_value(latest_channels, "heater_active_heat_level"),
        "power_watts": get_channel_value(latest_channels, "battery_watts_out") or 0,
        # Server's current targets (updates immediately)
        "target_temp_f": targets.get("heater_target_temp"),
        "target_power": targets.get("heater_power"),
        "oscillation": targets.get("heater_oscillation"),
        "display": targets.get("heater_display"),
        # Mode info
        "driver_control_enabled": targets.get("driver_control_enabled"),
        "automation_mode": targets.get("automation_mode"),
        "tou_period": targets.get("tou_period"),
        "sleep_mode": targets.get("heater_sleep_mode", False),
        # Weather
        "outdoor_temp_f": get_outdoor_temp(),
    }


@app.get("/api/battery")
async def api_battery_status():
    """Get current battery status: device state from driver + server's targets."""
    targets = calculate_targets()

    soc = get_channel_value(latest_channels, "battery_soc")
    if soc is None:
        return {
            "configured": False,
            "target_charge_power": targets.get("battery_charge_power"),
            "automation_mode": targets.get("automation_mode"),
            "tou_period": targets.get("tou_period"),
        }

    return {
        "configured": True,
        # Current device state (from driver)
        "soc": soc,
        "watts_in": get_channel_value(latest_channels, "battery_watts_in") or 0,
        "watts_out": get_channel_value(latest_channels, "battery_watts_out") or 0,
        "charging": get_channel_value(latest_channels, "battery_charging") or False,
        "discharging": get_channel_value(latest_channels, "battery_discharging") or False,
        # Server's current targets (updates immediately)
        "target_charge_power": targets.get("battery_charge_power"),
        "automation_mode": targets.get("automation_mode"),
        "tou_period": targets.get("tou_period"),
        "driver_control_enabled": targets.get("driver_control_enabled"),
    }


@app.get("/api/settings")
async def get_settings():
    """Get current automation settings."""
    global driver_control_enabled, automation_mode
    return {
        "driver_control_enabled": driver_control_enabled,
        "automation_mode": automation_mode,
    }


@app.post("/api/settings/driver-control")
async def set_driver_control(data: dict):
    """Enable/disable driver control (master kill switch)."""
    global driver_control_enabled
    driver_control_enabled = data.get("enabled", True)
    save_settings(driver_enabled=driver_control_enabled)
    return {"driver_control_enabled": driver_control_enabled}


@app.post("/api/settings/mode")
async def set_automation_mode(data: dict):
    """Set automation mode: 'manual' or 'tou'."""
    global automation_mode
    mode = data.get("mode", "tou")
    if mode not in ("manual", "tou"):
        mode = "tou"
    automation_mode = mode
    save_settings(mode=automation_mode)
    return {"automation_mode": automation_mode}


@app.post("/api/target")
async def set_target(data: dict):
    """Set target temperature."""
    temp = data.get("temp", 70)
    temp = max(41, min(95, int(temp)))
    user_targets["heater_target_temp"] = temp
    save_settings(targets=user_targets)
    return {"target_temp_f": temp}


@app.post("/api/power/toggle")
async def toggle_power():
    """Toggle heater power (updates target for next driver sync)."""
    current = user_targets.get("heater_power", True)
    user_targets["heater_power"] = not current
    save_settings(targets=user_targets)
    return {"power": not current}


@app.post("/api/oscillation/toggle")
async def toggle_oscillation():
    """Toggle oscillation (updates target for next driver sync)."""
    current = user_targets.get("heater_oscillation", False)
    user_targets["heater_oscillation"] = not current
    save_settings(targets=user_targets)
    return {"oscillation": not current}


@app.post("/api/plug/toggle")
async def toggle_plug():
    """Toggle plug power (updates target for next driver sync)."""
    current = user_targets.get("plug_on", True)
    user_targets["plug_on"] = not current
    save_settings(targets=user_targets)
    return {"plug_on": not current}


@app.get("/api/plug")
async def get_plug_status():
    """Get current plug status."""
    plug_on = get_channel_value(latest_channels, "plug_on")
    target_plug_on = user_targets.get("plug_on", True)
    return {
        "on": plug_on,
        "target_on": target_plug_on,
    }


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


@app.get("/api/stats/today")
async def get_stats_today():
    """Get today's running stats (from in-memory cache)."""
    return get_today_stats()


@app.get("/api/stats/history")
async def get_stats_history(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get daily stats for the past N days plus streak count.

    Returns list of daily stats and current savings streak.
    """
    today = datetime.now(LOCAL_TZ).date()
    poll_interval = int(os.getenv("POLL_INTERVAL_SEC", "60"))

    daily_stats = []

    # Compute stats for each day
    for days_ago in range(days):
        day = today - timedelta(days=days_ago)

        # For today, use the cached stats
        if days_ago == 0:
            daily_stats.append(get_today_stats())
            continue

        # For past days, query DB
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())

        readings = db.query(HeaterReading).filter(
            HeaterReading.timestamp >= day_start,
            HeaterReading.timestamp <= day_end
        ).order_by(HeaterReading.timestamp).all()

        if not readings:
            daily_stats.append({
                "date": day.isoformat(),
                "total_kwh": 0,
                "peak_kwh": 0,
                "offpeak_kwh": 0,
                "savings": 0,
                "would_have_cost": 0,
                "actual_cost": 0,
            })
            continue

        result = calculate_savings_from_readings(readings, poll_interval)
        result["date"] = day.isoformat()

        # Add temp stats
        temps = [r.current_temp_f for r in readings if r.current_temp_f is not None]
        if temps:
            result["avg_temp"] = round(sum(temps) / len(temps))
            result["min_temp"] = min(temps)
            result["max_temp"] = max(temps)

        daily_stats.append(result)

    # Calculate streak (consecutive days with savings > 0)
    streak = 0
    for stat in daily_stats:
        if stat.get("savings", 0) > 0:
            streak += 1
        else:
            break

    # Calculate month totals
    month_start = today.replace(day=1)
    month_stats = [s for s in daily_stats if s["date"] >= month_start.isoformat()]
    month_savings = sum(s.get("savings", 0) for s in month_stats)
    month_kwh = sum(s.get("total_kwh", 0) for s in month_stats)

    return {
        "days": daily_stats,
        "streak": streak,
        "month_savings": round(month_savings, 2),
        "month_kwh": round(month_kwh, 2),
    }
