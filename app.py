"""
Heater monitoring web app.

Polls heater status via Tuya Cloud API and stores historical data.
Serves a simple dashboard for visualization.
"""

import os
import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from models import Base, HeaterReading
from heater import Heater

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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def poll_heater():
    """Background task to poll heater and store readings."""
    global heater

    while True:
        try:
            if heater is None:
                heater = Heater(mode="cloud")

            status = heater.summary()

            # Store reading
            db = SessionLocal()
            try:
                reading = HeaterReading(
                    timestamp=datetime.utcnow(),
                    power=status.get("power"),
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
                print(f"[{datetime.now()}] Logged: {status.get('current_temp_f')}°F, "
                      f"power={status.get('power')}, active={status.get('active_heat_level')}")
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
<html>
<head>
    <title>Heater Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        h1 { margin-bottom: 20px; color: #fff; }
        .stats { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
        .stat { background: #16213e; padding: 20px; border-radius: 10px; min-width: 150px; }
        .stat-value { font-size: 2em; font-weight: bold; color: #e94560; }
        .stat-label { color: #888; font-size: 0.9em; }
        .chart-container { background: #16213e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        canvas { max-height: 300px; }
        .controls { margin-bottom: 20px; }
        select, button { padding: 8px 16px; border-radius: 5px; border: none; background: #0f3460; color: #fff; cursor: pointer; margin-right: 10px; }
        select:hover, button:hover { background: #e94560; }
    </style>
</head>
<body>
    <h1>Heater Monitor</h1>

    <div class="stats" id="stats">
        <div class="stat">
            <div class="stat-value" id="current-temp">--</div>
            <div class="stat-label">Current Temp</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="target-temp">--</div>
            <div class="stat-label">Target Temp</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="power-status">--</div>
            <div class="stat-label">Power</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="heat-level">--</div>
            <div class="stat-label">Heat Level</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="watts">--</div>
            <div class="stat-label">Watts</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="energy">--</div>
            <div class="stat-label">Energy (kWh)</div>
        </div>
    </div>

    <div class="controls">
        <select id="timeRange">
            <option value="1">Last 1 hour</option>
            <option value="6">Last 6 hours</option>
            <option value="24" selected>Last 24 hours</option>
            <option value="168">Last 7 days</option>
        </select>
        <button onclick="loadData()">Refresh</button>
        <button id="oscillation-btn" onclick="toggleOscillation()">Oscillation: --</button>
    </div>

    <div class="chart-container">
        <canvas id="tempChart"></canvas>
    </div>

    <div class="chart-container">
        <canvas id="powerChart"></canvas>
    </div>

<script>
let tempChart, powerChart;

async function loadData() {
    const hours = document.getElementById('timeRange').value;
    const response = await fetch(`/api/readings?hours=${hours}`);
    const data = await response.json();

    if (data.length === 0) return;

    // Update current stats
    const latest = data[data.length - 1];
    document.getElementById('current-temp').textContent = latest.current_temp_f ? `${latest.current_temp_f}°F` : '--';
    document.getElementById('target-temp').textContent = latest.target_temp_f ? `${latest.target_temp_f}°F` : '--';
    document.getElementById('power-status').textContent = latest.power ? 'ON' : 'OFF';
    document.getElementById('heat-level').textContent = latest.active_heat_level || '--';
    document.getElementById('watts').textContent = latest.power_watts || '0';
    document.getElementById('energy').textContent = latest.energy_kwh || '--';

    // Prepare chart data
    const labels = data.map(r => new Date(r.timestamp));
    const currentTemps = data.map(r => r.current_temp_f);
    const targetTemps = data.map(r => r.target_temp_f);
    const watts = data.map(r => r.power_watts || 0);

    // Temperature chart
    if (tempChart) tempChart.destroy();
    tempChart = new Chart(document.getElementById('tempChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'Current Temp (°F)', data: currentTemps, borderColor: '#e94560', backgroundColor: 'rgba(233,69,96,0.1)', fill: true, tension: 0.3 },
                { label: 'Target Temp (°F)', data: targetTemps, borderColor: '#0f3460', borderDash: [5,5], fill: false, tension: 0.3 }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: { type: 'time', time: { unit: hours > 24 ? 'day' : 'hour' }, grid: { color: '#333' }, ticks: { color: '#888' } },
                y: { grid: { color: '#333' }, ticks: { color: '#888' } }
            },
            plugins: { legend: { labels: { color: '#eee' } } }
        }
    });

    // Power chart
    if (powerChart) powerChart.destroy();
    powerChart = new Chart(document.getElementById('powerChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'Power (W)', data: watts, borderColor: '#f9a825', backgroundColor: 'rgba(249,168,37,0.1)', fill: true, stepped: true }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: { type: 'time', time: { unit: hours > 24 ? 'day' : 'hour' }, grid: { color: '#333' }, ticks: { color: '#888' } },
                y: { min: 0, max: 1600, grid: { color: '#333' }, ticks: { color: '#888' } }
            },
            plugins: { legend: { labels: { color: '#eee' } } }
        }
    });
}

async function toggleOscillation() {
    const btn = document.getElementById('oscillation-btn');
    btn.disabled = true;
    btn.textContent = 'Oscillation: ...';
    try {
        const response = await fetch('/api/oscillation/toggle', { method: 'POST' });
        const result = await response.json();
        btn.textContent = `Oscillation: ${result.oscillation ? 'ON' : 'OFF'}`;
    } catch (e) {
        btn.textContent = 'Oscillation: ERR';
    }
    btn.disabled = false;
}

async function updateOscillationBtn() {
    const response = await fetch('/api/status');
    const status = await response.json();
    document.getElementById('oscillation-btn').textContent = `Oscillation: ${status.oscillation ? 'ON' : 'OFF'}`;
}

// Auto-refresh every 60s
loadData();
updateOscillationBtn();
setInterval(loadData, 60000);
setInterval(updateOscillationBtn, 60000);
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
            "timestamp": r.timestamp.isoformat(),
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
