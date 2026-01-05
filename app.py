"""
Heater monitoring web app.

Polls heater status via Tuya Cloud API and stores historical data.
Serves a simple dashboard for visualization.
"""

import os
import asyncio
import urllib.request
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from models import Base, HeaterReading, SleepSchedule
from heater import Heater
from rates import calculate_savings_from_readings, get_tou_period, get_rate_for_period

load_dotenv()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./heater.db")
# Railway uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Polling config
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "60"))

# Global heater instance (cloud mode for remote access)
heater = None
polling_task = None

# Location for weather (10027 = NYC/Morningside Heights)
WEATHER_LAT = float(os.getenv("WEATHER_LAT", "40.81"))
WEATHER_LON = float(os.getenv("WEATHER_LON", "-73.95"))


def get_outdoor_temp() -> int | None:
    """Fetch current outdoor temperature from Open-Meteo API."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}&longitude={WEATHER_LON}&current=temperature_2m&temperature_unit=fahrenheit"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return int(round(data["current"]["temperature_2m"]))
    except Exception as e:
        print(f"Weather fetch error: {e}")
        return None


def get_db():
    db = SessionLocal()
    try:
        yield db
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
            "start_time": schedule.start_time.isoformat(),
            "wake_time": schedule.wake_time.isoformat(),
            "curve": json.loads(schedule.curve_json) if schedule.curve_json else []
        }
    finally:
        db.close()


def save_sleep_schedule(schedule):
    """Save sleep schedule to database."""
    db = SessionLocal()
    try:
        existing = db.query(SleepSchedule).filter(SleepSchedule.id == 1).first()
        if existing:
            existing.start_time = datetime.fromisoformat(schedule["start_time"])
            existing.wake_time = datetime.fromisoformat(schedule["wake_time"])
            existing.curve_json = json.dumps(schedule["curve"])
        else:
            new_schedule = SleepSchedule(
                id=1,
                start_time=datetime.fromisoformat(schedule["start_time"]),
                wake_time=datetime.fromisoformat(schedule["wake_time"]),
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

    now = datetime.now()
    start = datetime.fromisoformat(schedule['start_time'])
    wake = datetime.fromisoformat(schedule['wake_time'])

    # Check if schedule is still valid
    if now < start or now > wake:
        clear_sleep_schedule()
        return None

    # Calculate progress (0.0 to 1.0)
    total_duration = (wake - start).total_seconds()
    elapsed = (now - start).total_seconds()
    progress = elapsed / total_duration

    # Interpolate temperature from curve points
    points = schedule['curve']  # List of {progress: 0-1, temp: int}

    # Find the two points we're between
    for i in range(len(points) - 1):
        if points[i]['progress'] <= progress <= points[i + 1]['progress']:
            # Linear interpolation between these two points
            p1, p2 = points[i], points[i + 1]
            segment_progress = (progress - p1['progress']) / (p2['progress'] - p1['progress'])
            temp = p1['temp'] + (p2['temp'] - p1['temp']) * segment_progress
            return int(round(temp))

    # Fallback to last point
    return points[-1]['temp']


async def poll_heater():
    """Background task to poll heater and store readings."""
    global heater

    while True:
        try:
            if heater is None:
                heater = Heater(mode="cloud")

            # Check sleep schedule and adjust target temp
            sleep_target = get_sleep_target_temp()
            if sleep_target is not None:
                current_target = heater.get_target_temp()
                if current_target != sleep_target:
                    heater.set_target_temp(sleep_target)
                    print(f"[{datetime.now()}] Sleep mode: adjusted target to {sleep_target}°F")

            status = heater.summary()
            outdoor_temp = get_outdoor_temp()

            # Store reading
            db = SessionLocal()
            try:
                reading = HeaterReading(
                    timestamp=datetime.utcnow(),
                    power=status.get("power"),
                    outdoor_temp_f=outdoor_temp,
                    current_temp_f=status.get("current_temp_f"),
                    target_temp_f=status.get("target_temp_f"),
                    heat_mode=status.get("heat_mode"),
                    active_heat_level=status.get("active_heat_level"),
                    power_watts=status.get("power_watts"),
                    oscillation=status.get("oscillation"),
                    display=status.get("display"),
                    person_detection=status.get("person_detection"),
                    auto_on=status.get("auto_on"),
                    detection_timeout=status.get("detection_timeout"),
                    timer_remaining_sec=status.get("timer_remaining_sec"),
                    energy_kwh=status.get("energy_kwh"),
                    fault_code=status.get("fault_code"),
                )
                db.add(reading)
                db.commit()
                print(f"[{datetime.now()}] Logged: {status.get('current_temp_f')}°F inside, "
                      f"{outdoor_temp}°F outside, power={status.get('power')}")
            finally:
                db.close()

        except Exception as e:
            print(f"[{datetime.now()}] Poll error: {e}")

        await asyncio.sleep(POLL_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start polling on startup, cleanup on shutdown."""
    global polling_task

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Start polling
    polling_task = asyncio.create_task(poll_heater())
    print(f"Started polling every {POLL_INTERVAL_SEC}s")

    yield

    # Cleanup
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Heater Monitor", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Peak Shaver</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --green: #10B981; --green-light: #D1FAE5;
            --purple: #8B5CF6; --purple-dark: #6D28D9;
            --red: #EF4444; --orange: #F59E0B;
            --gray-50: #F9FAFB; --gray-100: #F3F4F6; --gray-200: #E5E7EB;
            --gray-400: #9CA3AF; --gray-500: #6B7280; --gray-600: #4B5563; --gray-900: #111827;
        }
        html { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif; font-size: 16px; -webkit-font-smoothing: antialiased; background: var(--gray-50); }
        body { max-width: 428px; margin: 0 auto; background: #fff; min-height: 100vh; overflow-x: hidden; }

        .hero { background: linear-gradient(135deg, var(--purple) 0%, var(--purple-dark) 100%); color: white; padding: 2rem 1.5rem 1.5rem; position: relative; }
        .hero-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
        .hero-label { font-size: 0.875rem; opacity: 0.9; }
        .streak-badge { display: flex; align-items: center; gap: 0.375rem; background: rgba(255,255,255,0.2); padding: 0.375rem 0.75rem; border-radius: 100px; font-size: 0.75rem; font-weight: 600; }
        .hero-amount { font-size: 4rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1; margin-bottom: 0.25rem; }
        .hero-subtitle { font-size: 1rem; opacity: 0.9; }

        .status-carousel-container { margin: -1rem 1rem 0; position: relative; z-index: 10; }
        .status-carousel { display: flex; overflow-x: auto; scroll-snap-type: x mandatory; gap: 0.75rem; padding-bottom: 0.5rem; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
        .status-carousel::-webkit-scrollbar { display: none; }
        .status-card { flex: 0 0 100%; scroll-snap-align: start; background: linear-gradient(135deg, var(--green) 0%, #059669 100%); border-radius: 16px; padding: 1rem 1.25rem; color: white; box-shadow: 0 4px 20px rgba(16, 185, 129, 0.3); }
        .status-card.heating { background: linear-gradient(135deg, var(--orange) 0%, #D97706 100%); box-shadow: 0 4px 20px rgba(245, 158, 11, 0.3); }
        .status-card.off { background: linear-gradient(135deg, var(--gray-400) 0%, var(--gray-500) 100%); box-shadow: 0 4px 20px rgba(107, 114, 128, 0.3); }
        .status-card.schedule-card { background: linear-gradient(135deg, var(--purple) 0%, var(--purple-dark) 100%); box-shadow: 0 4px 20px rgba(139, 92, 246, 0.3); }
        .status-card.battery-card { background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%); box-shadow: 0 4px 20px rgba(59, 130, 246, 0.3); }
        .carousel-dots { display: flex; justify-content: center; gap: 0.5rem; margin-top: 0.75rem; }
        .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--gray-200); transition: all 0.2s ease; }
        .dot.active { width: 18px; border-radius: 3px; background: var(--purple); }
        .schedule-timeline { display: flex; flex-direction: column; gap: 0.375rem; margin-top: 0.5rem; }
        .timeline-item { display: flex; align-items: center; gap: 0.75rem; font-size: 0.8125rem; padding: 0.375rem 0.625rem; border-radius: 6px; background: rgba(255,255,255,0.1); }
        .timeline-item.current { background: rgba(255,255,255,0.25); }
        .timeline-item.past { opacity: 0.6; }
        .timeline-item .time { font-weight: 600; min-width: 3rem; }
        .timeline-item .event { opacity: 0.9; }
        .battery-visual { display: flex; align-items: center; gap: 1rem; margin-top: 0.5rem; }
        .battery-big-percent { font-size: 2.5rem; font-weight: 700; }
        .battery-details { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.875rem; opacity: 0.9; }
        .status-top { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }
        .status-icon { width: 36px; height: 36px; background: rgba(255,255,255,0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; }
        .status-text h3 { font-size: 1rem; font-weight: 600; }
        .status-text p { font-size: 0.75rem; opacity: 0.9; }
        .rate-comparison { display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,0.15); border-radius: 8px; padding: 0.625rem 0.875rem; }
        .rate-item { text-align: center; }
        .rate-label { font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.8; }
        .rate-value { font-size: 1.25rem; font-weight: 700; }
        .rate-value.crossed { text-decoration: line-through; opacity: 0.7; }
        .rate-arrow { font-size: 1.25rem; opacity: 0.6; }

        .section { padding: 1.5rem; }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .section-title { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gray-500); }

        .home-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 1rem; }
        .home-card { background: var(--gray-50); border-radius: 16px; padding: 1.25rem; }
        .home-card.main { grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%); }
        .home-card-label { font-size: 0.75rem; color: var(--gray-500); margin-bottom: 0.25rem; }
        .home-card-value { font-size: 2rem; font-weight: 700; color: var(--gray-900); }
        .home-card-value.small { font-size: 1.5rem; }
        .home-card-sub { font-size: 0.75rem; color: var(--gray-500); margin-top: 0.25rem; }
        .temp-controls { display: flex; align-items: center; gap: 1rem; }
        .temp-btn { width: 44px; height: 44px; border-radius: 50%; border: 2px solid var(--gray-900); background: white; font-size: 1.5rem; font-weight: 300; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s ease; }
        .temp-btn:active { transform: scale(0.95); background: var(--gray-100); }
        .target-display { text-align: center; }
        .target-label { font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gray-500); }
        .target-value { font-size: 1.75rem; font-weight: 700; }

        .heater-controls { display: flex; gap: 0.5rem; margin-top: 1rem; }
        .control-btn { flex: 1; padding: 0.875rem; border-radius: 12px; border: none; background: var(--gray-100); color: var(--gray-600); font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.15s ease; display: flex; flex-direction: column; align-items: center; gap: 0.375rem; }
        .control-btn.active { background: var(--gray-900); color: white; }
        .control-btn:active { transform: scale(0.98); }
        .control-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .control-icon { font-size: 1.25rem; }

        .chart-section { background: var(--gray-50); padding: 1.5rem; margin: 0; }
        .chart-container { background: white; border-radius: 16px; padding: 1rem; margin-top: 1rem; }
        .chart-controls { display: flex; gap: 0.5rem; margin-top: 1rem; }
        .chart-btn { flex: 1; padding: 0.5rem; border-radius: 8px; border: none; background: var(--gray-100); color: var(--gray-600); font-size: 0.75rem; font-weight: 600; cursor: pointer; }
        .chart-btn.active { background: var(--purple); color: white; }
        canvas { max-height: 200px; }

        /* Sleep Mode Modal */
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 100; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
        .modal-overlay.open { opacity: 1; pointer-events: auto; }
        .modal { position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); width: 100%; max-width: 428px; background: white; border-radius: 24px 24px 0 0; z-index: 101; transform: translateX(-50%) translateY(100%); transition: transform 0.3s ease; max-height: 85vh; overflow-y: auto; }
        .modal-overlay.open .modal { transform: translateX(-50%) translateY(0); }
        .modal-header { padding: 1.5rem; border-bottom: 1px solid var(--gray-200); display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; background: white; z-index: 1; }
        .modal-title { font-size: 1.25rem; font-weight: 700; }
        .modal-close { width: 32px; height: 32px; border-radius: 50%; border: none; background: var(--gray-100); font-size: 1.25rem; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .modal-body { padding: 1.5rem; }

        /* Wake Time Wheel */
        .wake-section { margin-bottom: 2rem; }
        .wake-label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gray-500); margin-bottom: 0.75rem; }
        .scroll-wheel-container { position: relative; height: 150px; overflow: hidden; background: var(--gray-50); border-radius: 16px; }
        .scroll-wheel-highlight { position: absolute; top: 50%; left: 1rem; right: 1rem; height: 50px; transform: translateY(-50%); background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); z-index: 1; }
        .scroll-wheel { height: 100%; overflow-y: scroll; scroll-snap-type: y mandatory; -webkit-overflow-scrolling: touch; padding: 50px 1.5rem; position: relative; z-index: 2; }
        .scroll-wheel::-webkit-scrollbar { display: none; }
        .time-item { height: 50px; scroll-snap-align: center; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: 600; color: var(--gray-400); transition: all 0.2s ease; }
        .time-item.active { color: var(--gray-900); }

        /* Curve Editor */
        .curve-section { margin-bottom: 1.5rem; }
        .curve-container { background: var(--gray-50); border-radius: 16px; padding: 1rem; position: relative; }
        .curve-canvas { width: 100%; height: 200px; border-radius: 8px; touch-action: none; cursor: crosshair; }
        .curve-labels { display: flex; justify-content: space-between; margin-top: 0.5rem; font-size: 0.625rem; color: var(--gray-400); text-transform: uppercase; }
        .curve-temps { position: absolute; left: 0.5rem; top: 1rem; bottom: 2.5rem; display: flex; flex-direction: column; justify-content: space-between; font-size: 0.625rem; color: var(--gray-400); }
        .curve-info { display: flex; gap: 1rem; margin-top: 1rem; }
        .curve-stat { flex: 1; text-align: center; padding: 0.75rem; background: white; border-radius: 8px; }
        .curve-stat-value { font-size: 1.25rem; font-weight: 700; color: var(--purple); }
        .curve-stat-label { font-size: 0.625rem; color: var(--gray-500); margin-top: 0.25rem; }

        .sleep-start-btn { width: 100%; padding: 1rem; border-radius: 12px; border: none; background: var(--purple); color: white; font-size: 1rem; font-weight: 600; cursor: pointer; margin-top: 1rem; transition: background 0.2s ease; }
        .sleep-start-btn:active { transform: scale(0.98); }
        .sleep-start-btn.cancel-mode { background: var(--red); }

        .stats-row { display: flex; gap: 0.75rem; padding: 1.5rem; }
        .stat-card { flex: 1; background: var(--gray-50); border-radius: 12px; padding: 1rem; text-align: center; }
        .stat-value { font-size: 1.5rem; font-weight: 700; color: var(--green); }
        .stat-label { font-size: 0.75rem; color: var(--gray-500); margin-top: 0.25rem; }

        .bottom-nav { position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); width: 100%; max-width: 428px; background: white; border-top: 1px solid var(--gray-200); display: flex; padding: 0.75rem 1.5rem; padding-bottom: calc(0.75rem + env(safe-area-inset-bottom, 0)); }
        .nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 0.25rem; font-size: 0.625rem; color: var(--gray-400); text-decoration: none; }
        .nav-item.active { color: var(--purple); }
        .nav-icon { font-size: 1.5rem; }
        .nav-spacer { height: 80px; }
    </style>
</head>
<body>
    <div class="hero">
        <div class="hero-top">
            <div class="hero-label">Saved today</div>
            <div class="streak-badge"><span id="streak-count">--</span><span>day streak</span></div>
        </div>
        <div class="hero-amount" id="savings-today">$--</div>
        <div class="hero-subtitle">during peak hours</div>
    </div>

    <div class="status-carousel-container">
        <div class="status-carousel" id="status-carousel">
            <div class="status-card" id="status-card">
                <div class="status-top">
                    <div class="status-icon" id="status-icon">⏳</div>
                    <div class="status-text">
                        <h3 id="status-title">Loading...</h3>
                        <p id="status-subtitle">Checking heater status</p>
                    </div>
                </div>
                <div class="rate-comparison">
                    <div class="rate-item"><div class="rate-label">Grid rate</div><div class="rate-value crossed" id="grid-rate">$0.35</div></div>
                    <div class="rate-arrow">→</div>
                    <div class="rate-item"><div class="rate-label">You pay</div><div class="rate-value" id="your-rate">$0.08</div></div>
                </div>
            </div>
            <div class="status-card schedule-card">
                <div class="status-top">
                    <div class="status-icon">📅</div>
                    <div class="status-text">
                        <h3>Today's Schedule</h3>
                        <p>Swipe to see events</p>
                    </div>
                </div>
                <div class="schedule-timeline" id="schedule-timeline">
                    <div class="timeline-item past"><span class="time">12am</span><span class="event">Off-peak charging</span></div>
                    <div class="timeline-item current"><span class="time">Now</span><span class="event">Peak hours</span></div>
                    <div class="timeline-item future"><span class="time">12am</span><span class="event">Off-peak begins</span></div>
                </div>
            </div>
            <div class="status-card battery-card">
                <div class="status-top">
                    <div class="status-icon">🔋</div>
                    <div class="status-text">
                        <h3>Battery Status</h3>
                        <p>EcoFlow DELTA Pro</p>
                    </div>
                </div>
                <div class="battery-visual">
                    <div class="battery-big-percent" id="battery-percent">--%</div>
                    <div class="battery-details">
                        <span id="battery-power">-- W</span>
                        <span id="battery-status">Not connected</span>
                    </div>
                </div>
            </div>
        </div>
        <div class="carousel-dots">
            <span class="dot active"></span>
            <span class="dot"></span>
            <span class="dot"></span>
        </div>
    </div>

    <div class="section">
        <div class="section-header"><span class="section-title">Your Home</span></div>
        <div class="home-grid">
            <div class="home-card main">
                <div>
                    <div class="home-card-label">Inside</div>
                    <div class="home-card-value" id="current-temp">--°</div>
                    <div class="home-card-sub" id="temp-status">Loading...</div>
                </div>
                <div class="temp-controls">
                    <button class="temp-btn" id="temp-down">−</button>
                    <div class="target-display">
                        <div class="target-label">Target</div>
                        <div class="target-value" id="target-temp">--°</div>
                    </div>
                    <button class="temp-btn" id="temp-up">+</button>
                </div>
            </div>
            <div class="home-card">
                <div class="home-card-label">Outside</div>
                <div class="home-card-value small" id="outdoor-temp">--°</div>
                <div class="home-card-sub" id="outdoor-feels">--</div>
            </div>
            <div class="home-card">
                <div class="home-card-label">Power</div>
                <div class="home-card-value small" id="power-watts">--W</div>
                <div class="home-card-sub" id="power-status">--</div>
            </div>
        </div>
        <div class="heater-controls">
            <button class="control-btn" id="btn-power"><span class="control-icon">⚡</span><span>Power</span></button>
            <button class="control-btn" id="btn-oscillate"><span class="control-icon">🌀</span><span>Oscillate</span></button>
            <button class="control-btn" id="btn-sleep"><span class="control-icon">🌙</span><span>Sleep</span></button>
        </div>
    </div>

    <div class="chart-section">
        <div class="section-header"><span class="section-title">Temperature History</span></div>
        <div class="chart-controls">
            <button class="chart-btn" data-hours="1">1H</button>
            <button class="chart-btn" data-hours="6">6H</button>
            <button class="chart-btn active" data-hours="24">24H</button>
            <button class="chart-btn" data-hours="168">7D</button>
        </div>
        <div class="chart-container"><canvas id="tempChart"></canvas></div>
    </div>

    <div class="stats-row">
        <div class="stat-card"><div class="stat-value" id="stat-month">$--</div><div class="stat-label">This month</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-energy">--</div><div class="stat-label">kWh today</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-events">--</div><div class="stat-label">Peak kWh</div></div>
    </div>

    <div class="nav-spacer"></div>
    <nav class="bottom-nav">
        <a href="#" class="nav-item active"><span class="nav-icon">🏠</span><span>Home</span></a>
        <a href="#" class="nav-item"><span class="nav-icon">📊</span><span>History</span></a>
        <a href="#" class="nav-item"><span class="nav-icon">📅</span><span>Schedule</span></a>
        <a href="#" class="nav-item"><span class="nav-icon">⚙️</span><span>Settings</span></a>
    </nav>

    <!-- Sleep Mode Modal -->
    <div class="modal-overlay" id="sleep-modal">
        <div class="modal">
            <div class="modal-header">
                <div class="modal-title">Sleep Mode</div>
                <button class="modal-close" id="sleep-close">×</button>
            </div>
            <div class="modal-body">
                <div class="wake-section">
                    <div class="wake-label">Wake Time</div>
                    <div class="scroll-wheel-container">
                        <div class="scroll-wheel-highlight"></div>
                        <div class="scroll-wheel" id="wake-wheel"></div>
                    </div>
                </div>

                <div class="curve-section">
                    <div class="wake-label">Temperature Curve</div>
                    <div class="curve-container">
                        <div class="curve-temps" id="curve-temps"><span></span><span></span><span></span></div>
                        <canvas class="curve-canvas" id="curve-canvas"></canvas>
                        <div class="curve-labels" id="curve-labels">
                            <span>Now</span>
                            <span></span>
                            <span></span>
                            <span></span>
                            <span>Wake</span>
                        </div>
                    </div>
                    <div class="curve-info">
                        <div class="curve-stat">
                            <div class="curve-stat-value" id="curve-start">70°</div>
                            <div class="curve-stat-label">Start</div>
                        </div>
                        <div class="curve-stat">
                            <div class="curve-stat-value" id="curve-min">66°</div>
                            <div class="curve-stat-label">Lowest</div>
                        </div>
                        <div class="curve-stat">
                            <div class="curve-stat-value" id="curve-wake">72°</div>
                            <div class="curve-stat-label">Wake</div>
                        </div>
                    </div>
                </div>

                <button class="sleep-start-btn" id="sleep-start">Start Sleep Mode</button>
            </div>
        </div>
    </div>

<script>
let tempChart;
let currentTarget = 72;
let currentHours = 24;

// Load status from API
async function loadStatus() {
    try {
        const res = await fetch('/api/status');
        const s = res.ok ? await res.json() : {};

        // Update temperatures
        document.getElementById('current-temp').textContent = s.current_temp_f ? s.current_temp_f + '°' : '--°';
        currentTarget = s.target_temp_f || 72;
        document.getElementById('target-temp').textContent = currentTarget + '°';

        // Update power
        const watts = s.power_watts || 0;
        document.getElementById('power-watts').textContent = watts + 'W';
        document.getElementById('power-status').textContent = s.power ? (watts > 0 ? 'Heating' : 'Idle') : 'Off';

        // Update status card
        const card = document.getElementById('status-card');
        const icon = document.getElementById('status-icon');
        const title = document.getElementById('status-title');
        const subtitle = document.getElementById('status-subtitle');

        card.classList.remove('heating', 'off');
        if (!s.power) {
            card.classList.add('off');
            icon.textContent = '⏸️';
            title.textContent = 'Heater is off';
            subtitle.textContent = 'Tap Power to turn on';
        } else if (watts > 0) {
            card.classList.add('heating');
            icon.textContent = '🔥';
            title.textContent = 'Heating your home';
            subtitle.textContent = `Target: ${currentTarget}°F`;
        } else {
            icon.textContent = '✅';
            title.textContent = 'Temperature reached';
            subtitle.textContent = `Maintaining ${currentTarget}°F`;
        }

        // Update temp status
        const diff = (s.current_temp_f || 0) - currentTarget;
        document.getElementById('temp-status').textContent =
            diff < -1 ? 'Heating to target' : diff > 1 ? 'Above target' : 'At target';

        // Update control buttons
        document.getElementById('btn-power').classList.toggle('active', s.power);
        document.getElementById('btn-oscillate').classList.toggle('active', s.oscillation);

        // Check sleep mode status
        const sleepRes = await fetch('/api/sleep');
        const sleepStatus = sleepRes.ok ? await sleepRes.json() : {};
        document.getElementById('btn-sleep').classList.toggle('active', sleepStatus.active);
        window.sleepModeActive = sleepStatus.active;
        window.sleepProgress = sleepStatus.progress || 0;
        if (sleepStatus.active) {
            const wake = new Date(sleepStatus.wake_time);
            const wakeStr = wake.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
            icon.textContent = '🌙';
            title.textContent = 'Sleep mode active';
            subtitle.textContent = `Target: ${sleepStatus.current_target}°F · Wake: ${wakeStr}`;
            card.classList.remove('heating', 'off');
            card.style.cursor = 'pointer';
        } else {
            card.style.cursor = 'default';
        }

        // Load real savings data
        const savingsRes = await fetch('/api/savings?hours=24');
        const savings = savingsRes.ok ? await savingsRes.json() : {};
        document.getElementById('savings-today').textContent = '$' + (savings.savings || 0).toFixed(2);
        document.getElementById('stat-energy').textContent = (savings.total_kwh || 0).toFixed(1);

        // Update rate display
        const gridRate = savings.current_rate || 0.35;
        const offpeakRate = 0.0249;  // Off-peak rate (battery cost)
        document.getElementById('grid-rate').textContent = '$' + gridRate.toFixed(2);
        document.getElementById('your-rate').textContent = '$' + offpeakRate.toFixed(2);

        // Monthly savings (30 days)
        const monthRes = await fetch('/api/savings?hours=720');
        const monthSavings = monthRes.ok ? await monthRes.json() : {};
        document.getElementById('stat-month').textContent = '$' + (monthSavings.savings || 0).toFixed(0);

        // Peak kWh used today
        document.getElementById('stat-events').textContent = (savings.peak_kwh || 0).toFixed(1);
        document.getElementById('streak-count').textContent = '--';

    } catch (e) {
        console.error('Status load error:', e);
    }
}

// Load outdoor temp
async function loadOutdoor() {
    try {
        const res = await fetch('/api/readings?hours=1');
        const data = res.ok ? await res.json() : [];
        if (data.length > 0) {
            const latest = data[data.length - 1];
            document.getElementById('outdoor-temp').textContent = latest.outdoor_temp_f ? latest.outdoor_temp_f + '°' : '--°';
            document.getElementById('outdoor-feels').textContent = latest.outdoor_temp_f ? 'Current' : '--';
        }
    } catch (e) {}
}

// Load chart data
async function loadChart(hours) {
    currentHours = hours;
    document.querySelectorAll('.chart-btn').forEach(b => b.classList.toggle('active', b.dataset.hours == hours));

    try {
        const res = await fetch(`/api/readings?hours=${hours}`);
        const data = res.ok ? await res.json() : [];
        if (data.length === 0) return;

        const labels = data.map(r => new Date(r.timestamp));
        const indoor = data.map(r => r.current_temp_f);
        const target = data.map(r => r.target_temp_f);
        const outdoor = data.map(r => r.outdoor_temp_f);

        if (tempChart) tempChart.destroy();
        tempChart = new Chart(document.getElementById('tempChart'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Indoor', data: indoor, borderColor: '#8B5CF6', backgroundColor: 'rgba(139,92,246,0.1)', fill: true, tension: 0.3, pointRadius: 0 },
                    { label: 'Target', data: target, borderColor: '#9CA3AF', borderDash: [5,5], fill: false, tension: 0.3, pointRadius: 0 },
                    { label: 'Outdoor', data: outdoor, borderColor: '#60A5FA', fill: false, tension: 0.3, pointRadius: 0 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                scales: {
                    x: { type: 'time', time: { unit: hours > 24 ? 'day' : 'hour' }, grid: { display: false }, ticks: { color: '#9CA3AF', maxTicksLimit: 6 } },
                    y: { grid: { color: '#E5E7EB' }, ticks: { color: '#9CA3AF' } }
                },
                plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, padding: 16, color: '#6B7280' } } }
            }
        });
    } catch (e) {
        console.error('Chart load error:', e);
    }
}

// Control handlers
document.getElementById('btn-power').onclick = async function() {
    this.disabled = true;
    try {
        await fetch('/api/power/toggle', { method: 'POST' });
        await loadStatus();
    } finally { this.disabled = false; }
};

document.getElementById('btn-oscillate').onclick = async function() {
    this.disabled = true;
    try {
        await fetch('/api/oscillation/toggle', { method: 'POST' });
        await loadStatus();
    } finally { this.disabled = false; }
};


document.getElementById('temp-up').onclick = async function() {
    currentTarget = Math.min(95, currentTarget + 1);
    document.getElementById('target-temp').textContent = currentTarget + '°';
    await fetch('/api/target', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({temp: currentTarget}) });
};

document.getElementById('temp-down').onclick = async function() {
    currentTarget = Math.max(41, currentTarget - 1);
    document.getElementById('target-temp').textContent = currentTarget + '°';
    await fetch('/api/target', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({temp: currentTarget}) });
};

document.querySelectorAll('.chart-btn').forEach(btn => {
    btn.onclick = () => loadChart(parseInt(btn.dataset.hours));
});

// Initial load
loadStatus();
loadOutdoor();
loadChart(24);

// Auto-refresh
setInterval(loadStatus, 30000);
setInterval(loadOutdoor, 60000);
setInterval(() => loadChart(currentHours), 60000);

// Carousel dots
const carousel = document.getElementById('status-carousel');
const dots = document.querySelectorAll('.carousel-dots .dot');
carousel.addEventListener('scroll', () => {
    const scrollLeft = carousel.scrollLeft;
    const cardWidth = carousel.offsetWidth;
    const activeIndex = Math.round(scrollLeft / cardWidth);
    dots.forEach((dot, i) => dot.classList.toggle('active', i === activeIndex));
});

// Click status card to view sleep progress
document.getElementById('status-card').onclick = async () => {
    if (!window.sleepModeActive) return;

    // Fetch latest sleep data
    const res = await fetch('/api/sleep');
    const data = res.ok ? await res.json() : {};
    if (!data.active) return;

    // Store curve from server and progress for drawing
    window.serverCurve = data.curve;
    window.sleepProgress = data.progress;
    window.viewingProgress = true;

    sleepModal.classList.add('open');
    initCurve();
    updateTimeLabels();

    // Update button to show cancel option
    document.getElementById('sleep-start').textContent = 'Cancel Sleep Mode';
    document.getElementById('sleep-start').classList.add('cancel-mode');
};

// ===== SLEEP MODE =====
const sleepModal = document.getElementById('sleep-modal');
const wakeWheel = document.getElementById('wake-wheel');
const curveCanvas = document.getElementById('curve-canvas');
let curveCtx, curvePoints = [];
let selectedWakeTime = localStorage.getItem('sleepWakeTime') || '7:00 AM';

function saveSleepSettings() {
    const rect = curveCanvas.getBoundingClientRect();
    const h = rect.height;
    // Save curve as relative deltas from setpoint (not absolute temps)
    // Y position to delta: y=0 means +5° above setpoint, y=h means -5° below
    const yToDelta = (y) => 5 - (y / h) * 10;  // Returns delta from setpoint
    const normalized = curvePoints.map(p => ({
        progress: p.x / rect.width,
        delta: yToDelta(p.y)  // e.g., -4 means "4 degrees below setpoint"
    }));
    localStorage.setItem('sleepCurve', JSON.stringify(normalized));
    localStorage.setItem('sleepWakeTime', selectedWakeTime);
}

// Generate wake times
const wakeTimes = [];
for (let h = 5; h <= 11; h++) {
    wakeTimes.push(`${h}:00 AM`);
    wakeTimes.push(`${h}:30 AM`);
}
wakeTimes.forEach((t, i) => {
    const div = document.createElement('div');
    div.className = 'time-item' + (t === selectedWakeTime ? ' active' : '');
    div.textContent = t;
    div.dataset.time = t;
    wakeWheel.appendChild(div);
});

// Scroll wheel behavior
wakeWheel.addEventListener('scroll', () => {
    const items = wakeWheel.querySelectorAll('.time-item');
    const wheelRect = wakeWheel.getBoundingClientRect();
    const centerY = wheelRect.top + wheelRect.height / 2;
    let closest = null, closestDist = Infinity;
    items.forEach(item => {
        const rect = item.getBoundingClientRect();
        const dist = Math.abs(centerY - (rect.top + rect.height / 2));
        if (dist < closestDist) { closestDist = dist; closest = item; }
    });
    items.forEach(i => i.classList.remove('active'));
    if (closest) {
        closest.classList.add('active');
        selectedWakeTime = closest.dataset.time;
        saveSleepSettings();
        updateTimeLabels();
    }
});

// Update time labels on the curve
function updateTimeLabels() {
    const labels = document.querySelectorAll('#curve-labels span');
    const now = new Date();

    // Parse wake time (e.g., "7:30 AM")
    const [timePart, ampm] = selectedWakeTime.split(' ');
    const [hours, mins] = timePart.split(':').map(Number);
    let wakeHour = hours;
    if (ampm === 'PM' && hours !== 12) wakeHour += 12;
    if (ampm === 'AM' && hours === 12) wakeHour = 0;

    // Create wake time date (tomorrow if wake time is before current time)
    const wake = new Date(now);
    wake.setHours(wakeHour, mins, 0, 0);
    if (wake <= now) wake.setDate(wake.getDate() + 1);

    // Calculate duration in ms
    const duration = wake - now;

    // Format time helper (rounds to nearest 30 min)
    const formatTime = (date) => {
        let h = date.getHours();
        let m = date.getMinutes();
        // Round to nearest 30 min
        if (m < 15) m = 0;
        else if (m < 45) m = 30;
        else { m = 0; h = (h + 1) % 24; }
        const suffix = h >= 12 ? 'pm' : 'am';
        h = h % 12 || 12;
        return m === 0 ? `${h}${suffix}` : `${h}:30${suffix}`;
    };

    // Set labels at 0%, 25%, 50%, 75%, 100%
    labels[0].textContent = formatTime(now);
    labels[1].textContent = formatTime(new Date(now.getTime() + duration * 0.25));
    labels[2].textContent = formatTime(new Date(now.getTime() + duration * 0.5));
    labels[3].textContent = formatTime(new Date(now.getTime() + duration * 0.75));
    labels[4].textContent = formatTime(wake);
}

// Open/close modal
document.getElementById('btn-sleep').onclick = () => {
    sleepModal.classList.add('open');
    initCurve();
    updateTimeLabels();
    setTimeout(() => {
        // Scroll to saved wake time
        const items = wakeWheel.querySelectorAll('.time-item');
        items.forEach(i => i.classList.remove('active'));
        const target = Array.from(items).find(i => i.dataset.time === selectedWakeTime);
        if (target) {
            target.classList.add('active');
            target.scrollIntoView({ block: 'center', behavior: 'instant' });
        }
    }, 100);
};
function closeSleepModal() {
    sleepModal.classList.remove('open');
    window.viewingProgress = false;
    window.serverCurve = null;
    document.getElementById('sleep-start').textContent = 'Start Sleep Mode';
    document.getElementById('sleep-start').classList.remove('cancel-mode');
}
document.getElementById('sleep-close').onclick = closeSleepModal;
sleepModal.onclick = (e) => { if (e.target === sleepModal) closeSleepModal(); };

// Curve drawing
function initCurve() {
    const canvas = curveCanvas;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    curveCtx = canvas.getContext('2d');
    curveCtx.scale(2, 2);

    const w = rect.width, h = rect.height;

    // If viewing active sleep mode, use server curve
    if (window.viewingProgress && window.serverCurve) {
        const tempToY = (temp) => ((75 - temp) / 10) * h;
        curvePoints = window.serverCurve.map(p => ({
            x: p.progress * w,
            y: tempToY(p.temp)
        }));
        drawCurve();
        return;
    }

    // Convert delta (relative to setpoint) to Y position
    // delta=0 means at setpoint, delta=-4 means 4° below setpoint
    const deltaToY = (delta) => ((5 - delta) / 10) * h;

    // Try to load saved curve from localStorage (stored as deltas)
    const saved = localStorage.getItem('sleepCurve');
    if (saved) {
        try {
            const normalized = JSON.parse(saved);
            // Check if it's the new format (has delta) or old format (has y)
            if (normalized[0] && normalized[0].delta !== undefined) {
                curvePoints = normalized.map(p => ({
                    x: p.progress * w,
                    y: deltaToY(p.delta)
                }));
            } else {
                // Old format - clear it
                curvePoints = null;
            }
        } catch (e) {
            curvePoints = null;
        }
    }

    // Default curve: bathtub shape (in deltas: 0, -2.5, -5, -5, -5, -2.5, 0)
    if (!curvePoints || curvePoints.length !== 7) {
        curvePoints = [
            { x: 0, y: deltaToY(0) },           // Start: at setpoint
            { x: w * 0.12, y: deltaToY(-2.5) }, // Quick drop
            { x: w * 0.25, y: deltaToY(-5) },   // Bottom left
            { x: w * 0.5, y: deltaToY(-5) },    // Bottom middle (flat)
            { x: w * 0.75, y: deltaToY(-5) },   // Bottom right
            { x: w * 0.88, y: deltaToY(-2.5) }, // Quick rise
            { x: w, y: deltaToY(0) }            // Wake: back to setpoint
        ];
    }

    // Update Y-axis labels based on current setpoint
    const tempLabels = document.querySelectorAll('#curve-temps span');
    tempLabels[0].textContent = (currentTarget + 5) + '°';
    tempLabels[1].textContent = currentTarget + '°';
    tempLabels[2].textContent = (currentTarget - 5) + '°';

    drawCurve();
}

function drawCurve() {
    const canvas = curveCanvas;
    const rect = canvas.getBoundingClientRect();
    const w = rect.width, h = rect.height;
    const ctx = curveCtx;

    ctx.clearRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
        ctx.beginPath();
        ctx.moveTo(0, h * i / 4);
        ctx.lineTo(w, h * i / 4);
        ctx.stroke();
    }

    // Gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, 'rgba(139, 92, 246, 0.3)');
    gradient.addColorStop(1, 'rgba(139, 92, 246, 0.05)');

    // Draw smooth curve
    ctx.beginPath();
    ctx.moveTo(curvePoints[0].x, curvePoints[0].y);
    for (let i = 1; i < curvePoints.length; i++) {
        const prev = curvePoints[i - 1];
        const curr = curvePoints[i];
        const cpx = (prev.x + curr.x) / 2;
        ctx.quadraticCurveTo(prev.x, prev.y, cpx, (prev.y + curr.y) / 2);
    }
    ctx.quadraticCurveTo(curvePoints[curvePoints.length - 2].x, curvePoints[curvePoints.length - 2].y, curvePoints[curvePoints.length - 1].x, curvePoints[curvePoints.length - 1].y);
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.moveTo(curvePoints[0].x, curvePoints[0].y);
    for (let i = 1; i < curvePoints.length; i++) {
        const prev = curvePoints[i - 1];
        const curr = curvePoints[i];
        const cpx = (prev.x + curr.x) / 2;
        ctx.quadraticCurveTo(prev.x, prev.y, cpx, (prev.y + curr.y) / 2);
    }
    ctx.quadraticCurveTo(curvePoints[curvePoints.length - 2].x, curvePoints[curvePoints.length - 2].y, curvePoints[curvePoints.length - 1].x, curvePoints[curvePoints.length - 1].y);
    ctx.strokeStyle = '#8B5CF6';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Draw control points (only if not viewing progress)
    if (!window.viewingProgress) {
        curvePoints.forEach((p, i) => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
            // Endpoints get different color
            ctx.fillStyle = (i === 0 || i === curvePoints.length - 1) ? '#10B981' : '#8B5CF6';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
            ctx.fillStyle = 'white';
            ctx.fill();
        });
    }

    // Draw progress indicator if viewing active sleep
    if (window.viewingProgress && window.sleepProgress !== undefined) {
        const progress = window.sleepProgress;
        const progressX = progress * w;

        // Find Y position by interpolating between curve points
        let progressY = curvePoints[0].y;
        for (let i = 0; i < curvePoints.length - 1; i++) {
            const p1 = curvePoints[i], p2 = curvePoints[i + 1];
            if (progressX >= p1.x && progressX <= p2.x) {
                const t = (progressX - p1.x) / (p2.x - p1.x);
                progressY = p1.y + (p2.y - p1.y) * t;
                break;
            }
        }

        // Draw vertical line at progress
        ctx.beginPath();
        ctx.moveTo(progressX, 0);
        ctx.lineTo(progressX, h);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw "you are here" dot
        ctx.beginPath();
        ctx.arc(progressX, progressY, 12, 0, Math.PI * 2);
        ctx.fillStyle = '#F59E0B';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(progressX, progressY, 6, 0, Math.PI * 2);
        ctx.fillStyle = 'white';
        ctx.fill();

        // Draw "NOW" label
        ctx.fillStyle = '#F59E0B';
        ctx.font = 'bold 10px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('NOW', progressX, progressY - 20);
    }

    updateCurveStats();
}

function updateCurveStats() {
    const rect = curveCanvas.getBoundingClientRect();
    const h = rect.height;
    // Y to delta, then delta to absolute temp
    const yToDelta = (y) => 5 - (y / h) * 10;
    const deltas = curvePoints.map(p => yToDelta(p.y));
    const temps = deltas.map(d => Math.round(currentTarget + d));
    document.getElementById('curve-start').textContent = temps[0] + '°';
    document.getElementById('curve-min').textContent = Math.min(...temps) + '°';
    document.getElementById('curve-wake').textContent = temps[temps.length - 1] + '°';
}

// Drag points
let draggingPoint = null;
curveCanvas.addEventListener('pointerdown', (e) => {
    const rect = curveCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    // Check all points including endpoints
    for (let i = 0; i < curvePoints.length; i++) {
        const p = curvePoints[i];
        if (Math.hypot(p.x - x, p.y - y) < 20) {
            draggingPoint = i;
            curveCanvas.setPointerCapture(e.pointerId);
            return;
        }
    }
    // If not on a point, move nearest middle point
    let nearestDist = Infinity, nearestIdx = -1;
    for (let i = 1; i < curvePoints.length - 1; i++) {
        const dist = Math.abs(curvePoints[i].x - x);
        if (dist < nearestDist) { nearestDist = dist; nearestIdx = i; }
    }
    if (nearestIdx >= 0) {
        curvePoints[nearestIdx].y = Math.max(10, Math.min(rect.height - 10, y));
        drawCurve();
    }
});

curveCanvas.addEventListener('pointermove', (e) => {
    if (draggingPoint === null) return;
    const rect = curveCanvas.getBoundingClientRect();
    const y = e.clientY - rect.top;
    // Only move Y (keep X fixed for all points)
    curvePoints[draggingPoint].y = Math.max(10, Math.min(rect.height - 10, y));
    drawCurve();
});

curveCanvas.addEventListener('pointerup', () => { draggingPoint = null; saveSleepSettings(); });
curveCanvas.addEventListener('pointercancel', () => { draggingPoint = null; });

// Start/cancel sleep mode
document.getElementById('sleep-start').onclick = async () => {
    // If viewing progress, this is a cancel button
    if (window.viewingProgress) {
        try {
            await fetch('/api/sleep/cancel', { method: 'POST' });
            closeSleepModal();
            document.getElementById('btn-sleep').classList.remove('active');
            loadStatus();
        } catch (e) {
            console.error('Failed to cancel sleep mode:', e);
        }
        return;
    }

    const rect = curveCanvas.getBoundingClientRect();
    const h = rect.height;
    // Convert Y to delta, then to absolute temp using current setpoint
    const yToDelta = (y) => 5 - (y / h) * 10;
    const curve = curvePoints.map((p, i) => ({
        progress: p.x / rect.width,
        temp: Math.round(currentTarget + yToDelta(p.y))
    }));

    try {
        const res = await fetch('/api/sleep', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ wakeTime: selectedWakeTime, curve })
        });
        if (res.ok) {
            closeSleepModal();
            document.getElementById('btn-sleep').classList.add('active');
            // Update status to show sleep mode
            document.getElementById('status-icon').textContent = '🌙';
            document.getElementById('status-title').textContent = 'Sleep mode active';
            document.getElementById('status-subtitle').textContent = `Wake: ${selectedWakeTime}`;
        }
    } catch (e) {
        console.error('Failed to start sleep mode:', e);
    }
};
</script>
</body>
</html>"""


@app.get("/api/readings")
async def get_readings(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """Get historical readings."""
    since = datetime.utcnow() - timedelta(hours=hours)
    readings = db.query(HeaterReading).filter(
        HeaterReading.timestamp >= since
    ).order_by(HeaterReading.timestamp).all()

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
            "display": r.display,
            "person_detection": r.person_detection,
            "auto_on": r.auto_on,
            "detection_timeout": r.detection_timeout,
            "timer_remaining_sec": r.timer_remaining_sec,
            "energy_kwh": r.energy_kwh,
            "fault_code": r.fault_code,
            "outdoor_temp_f": r.outdoor_temp_f,
        }
        for r in readings
    ]


@app.get("/api/status")
async def get_status():
    """Get current heater status (live from device)."""
    global heater
    if heater is None:
        heater = Heater(mode="cloud")
    return heater.summary()


@app.post("/api/oscillation/toggle")
async def toggle_oscillation():
    """Toggle oscillation on/off."""
    global heater
    if heater is None:
        heater = Heater(mode="cloud")
    current = heater.get_oscillation()
    heater.set_oscillation(not current)
    return {"oscillation": not current}


@app.post("/api/power/toggle")
async def toggle_power():
    """Toggle heater power on/off."""
    global heater
    if heater is None:
        heater = Heater(mode="cloud")
    current = heater.is_on()
    heater.set_power(not current)
    return {"power": not current}


@app.post("/api/display/toggle")
async def toggle_display():
    """Toggle display on/off."""
    global heater
    if heater is None:
        heater = Heater(mode="cloud")
    current = heater.get_display()
    heater.set_display(not current)
    return {"display": not current}


@app.post("/api/target")
async def set_target(data: dict):
    """Set target temperature."""
    global heater
    if heater is None:
        heater = Heater(mode="cloud")
    temp = data.get("temp", 72)
    temp = max(41, min(95, int(temp)))  # Clamp to valid range
    heater.set_target_temp(temp)
    return {"target_temp_f": temp}


@app.post("/api/sleep")
async def start_sleep_mode(data: dict):
    """Start sleep mode with a temperature curve."""
    # data: { wakeTime: "7:00 AM", curve: [{progress: 0-1, temp: int}, ...] }
    wake_time_str = data.get("wakeTime", "7:00 AM")
    curve = data.get("curve", [])

    # Parse wake time
    time_part, ampm = wake_time_str.split(' ')
    hours, mins = map(int, time_part.split(':'))
    if ampm == 'PM' and hours != 12:
        hours += 12
    if ampm == 'AM' and hours == 12:
        hours = 0

    now = datetime.now()
    wake = now.replace(hour=hours, minute=mins, second=0, microsecond=0)
    if wake <= now:
        wake += timedelta(days=1)

    schedule = {
        "start_time": now.isoformat(),
        "wake_time": wake.isoformat(),
        "curve": curve
    }
    save_sleep_schedule(schedule)

    return {"status": "ok", "wake_time": wake.isoformat()}


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

    # Calculate progress
    now = datetime.now()
    start = datetime.fromisoformat(schedule['start_time'])
    wake = datetime.fromisoformat(schedule['wake_time'])
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
    """
    Calculate peak shaving savings for the given time period.

    Returns savings breakdown based on ConEd TOU rates.
    """
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
            "would_have_cost": 0,
            "actual_cost": 0,
            "current_period": get_tou_period(datetime.now()),
            "current_rate": get_rate_for_period(datetime.now())[1]
        }

    # Calculate with poll interval (get from env or default 5s)
    poll_interval = int(os.getenv("POLL_INTERVAL_SEC", "5"))
    result = calculate_savings_from_readings(readings, poll_interval)

    # Add current rate info
    result["hours"] = hours
    result["current_period"] = get_tou_period(datetime.now())
    result["current_rate"] = get_rate_for_period(datetime.now())[1]

    return result
