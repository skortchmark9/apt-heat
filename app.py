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


async def poll_heater():
    """Background task to poll heater and store readings."""
    global heater

    while True:
        try:
            if heater is None:
                heater = Heater(mode="cloud")

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

        .status-card { background: linear-gradient(135deg, var(--green) 0%, #059669 100%); margin: -1rem 1rem 0; border-radius: 16px; padding: 1rem 1.25rem; color: white; position: relative; z-index: 10; box-shadow: 0 4px 20px rgba(16, 185, 129, 0.3); }
        .status-card.heating { background: linear-gradient(135deg, var(--orange) 0%, #D97706 100%); box-shadow: 0 4px 20px rgba(245, 158, 11, 0.3); }
        .status-card.off { background: linear-gradient(135deg, var(--gray-400) 0%, var(--gray-500) 100%); box-shadow: 0 4px 20px rgba(107, 114, 128, 0.3); }
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

    <div class="status-card" id="status-card">
        <div class="status-top">
            <div class="status-icon" id="status-icon">⏳</div>
            <div class="status-text">
                <h3 id="status-title">Loading...</h3>
                <p id="status-subtitle">Checking heater status</p>
            </div>
        </div>
        <div class="rate-comparison">
            <div class="rate-item"><div class="rate-label">Grid rate</div><div class="rate-value crossed">$0.35</div></div>
            <div class="rate-arrow">→</div>
            <div class="rate-item"><div class="rate-label">You pay</div><div class="rate-value">$0.08</div></div>
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
            <button class="control-btn" id="btn-display"><span class="control-icon">💡</span><span>Display</span></button>
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
        <div class="stat-card"><div class="stat-value" id="stat-events">--</div><div class="stat-label">Peak events</div></div>
    </div>

    <div class="nav-spacer"></div>
    <nav class="bottom-nav">
        <a href="#" class="nav-item active"><span class="nav-icon">🏠</span><span>Home</span></a>
        <a href="#" class="nav-item"><span class="nav-icon">📊</span><span>History</span></a>
        <a href="#" class="nav-item"><span class="nav-icon">📅</span><span>Schedule</span></a>
        <a href="#" class="nav-item"><span class="nav-icon">⚙️</span><span>Settings</span></a>
    </nav>

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
        document.getElementById('btn-display').classList.toggle('active', s.display);

        // Mock savings (TODO: calculate from actual data)
        document.getElementById('savings-today').textContent = '$2.90';
        document.getElementById('streak-count').textContent = '5';
        document.getElementById('stat-month').textContent = '$47';
        document.getElementById('stat-energy').textContent = s.energy_kwh || '--';
        document.getElementById('stat-events').textContent = '23';

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

document.getElementById('btn-display').onclick = async function() {
    this.disabled = true;
    try {
        await fetch('/api/display/toggle', { method: 'POST' });
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
