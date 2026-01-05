# Apartment Heat Management System

## Goal
Peak shaving with a Lasko AR122 smart heater and EcoFlow DELTA Pro battery (3.6 kWh). Use cheap off-peak electricity (midnight-8am) for heating and battery charging, minimize grid usage during expensive peak hours (8am-midnight).

## Hardware
- **Heater**: Lasko Aria AR122 smart ceramic heater (~1500W when heating)
- **Battery**: EcoFlow DELTA Pro (3.6 kWh) - can run heater for ~2.4 hours
- **Location**: NYC apartment, ~10x10 ft bedroom with old PTHP

## Completed Work

### 1. Tuya API Integration
- Heater uses Tuya WiFi module, paired with Smart Life app
- Created Tuya IoT developer account (Western America data center)
- Credentials stored in `.env`

### 2. DPS (Data Point Schema) Mapping
Reverse-engineered heater controls via local API:

| DPS | Function | Type |
|-----|----------|------|
| 1 | Power on/off | bool |
| 3 | Current temp (°F) | int, read-only |
| 5 | Heat mode | Low/Medium/High |
| 8 | Oscillation | bool |
| 10 | Display on/off | bool |
| 11 | Active heat level | Stop/Low/Medium/High, read-only |
| 14 | Target temp (°F) | int |
| 101 | Person detection | bool |
| 102 | Auto-on | bool |
| 103 | Detection timeout | 5min/15min/30min |
| 105 | Timer value | int (base 59 + seconds) |
| 106 | Energy usage (kWh) | int, read-only |
| 108 | Fault code | 0=none, 16=tip-over |

### 3. Heater Control Module (`heater.py`)
- Supports both **local** (LAN) and **cloud** (Tuya API) modes
- Cloud mode limitations: only exposes power, temp, oscillation, display
- Local mode: full DPS access (currently having connection issues)

### 4. Web Monitoring App (`app.py`)
Deployed on Railway with PostgreSQL database.

**Features:**
- Real-time dashboard showing indoor/outdoor temp, target, power status
- Temperature chart (indoor vs target vs outdoor)
- Power consumption chart
- Oscillation toggle button
- Polls heater every 5 seconds via cloud API
- Outdoor temperature from Open-Meteo API (NYC coordinates)

**URL**: Deployed on Railway (user's account)

### 5. Peak Shaving Control Loop (`control_loop.py`)
Local script for automated temp management:
- Off-peak (midnight-8am): Pre-heat to 72°F
- Peak (8am-midnight): Allow drift to 68°F
- Not yet integrated with battery

## Files Structure
```
apt_heat/
├── .env                 # Credentials (gitignored)
├── .gitignore
├── CLAUDE.md            # Dev notes
├── heater.py            # Heater control module
├── control_loop.py      # Peak shaving automation
├── app.py               # FastAPI web app
├── models.py            # SQLAlchemy models
├── requirements.txt     # Python dependencies
├── railway.json         # Railway deployment config
├── Procfile             # Railway start command
└── tools/               # Railway CLI (gitignored)
```

## Pending Work

### 1. EcoFlow Battery Integration
- Connect to EcoFlow API to get:
  - State of Charge (SOC) percentage
  - Current power draw (watts)
  - Charging/discharging status
- Display battery stats on dashboard
- Use battery power data instead of heater's limited cloud data

### 2. Sleep Mode
User-triggered mode for overnight comfort:
- Press "Sleep" button when going to bed
- Start at comfortable temp (e.g., 70°F)
- Gradually ramp down to 67°F during deep sleep
- Ramp back up before wake time
- Could use motion detection if local connection is restored

### 3. Smart Peak Shaving Logic
Integrate heater + battery for intelligent decisions:
- If battery SOC > 50% during peak: use battery for heating
- If battery SOC < 20%: reduce heating to preserve battery
- During off-peak: prioritize charging battery, then heating
- Weather-aware: pre-heat more aggressively if cold night expected

### 4. Local Connection Debugging
- Local LAN connection to heater failing (port open, ping works)
- Needed for: full DPS data, motion detection timestamps
- May need to refresh local key or check firmware

## Environment Variables (Railway)
```
TUYA_ACCESS_ID=57a3nrnpt9nhaqnyenpt
TUYA_ACCESS_SECRET=6ae8d610c665490b968e44ac32a277a0
TUYA_REGION=us
HEATER_DEVICE_ID=ebd9ca5886f6d470f2g77m
DATABASE_URL=${{Postgres.DATABASE_URL}}
POLL_INTERVAL_SEC=5
WEATHER_LAT=40.81
WEATHER_LON=-73.95
```

## UI/UX Design Direction

**Chosen direction**: Design E v2 (Playful/Emotional) - `mockups/design-e-v2.html`

### Key Elements to Keep
- **"Battery is handling it"** - Fun, reassuring status message during peak hours
- **Streak counter** - "5-day peak-shaving streak!" with fire emoji
  - Needs refinement: what counts as a "successful" day?
  - Ideas: days where battery covered >80% of peak usage? Days with $X+ saved?
- **Rate comparison bar** - ConEd wants $0.35 → You're paying $0.08
- **"Saving $X every kWh right now"** - Live savings ticker
- **Purple gradient hero** - Stands out, feels premium

### "Your Day" Timeline (Scroll Wheel) ✓ Implemented
iOS picker-style scroll wheel showing daily schedule:
- Scroll up/down to see schedule for different times
- Current time highlighted in white card, others faded
- Shows: time, icon, action, rate
- Future: could be editable (drag to change peak hours?)

### Home Controls ✓ Implemented
- Current temp display with +/- buttons for target
- Outside temp with "feels like"
- Humidity reading
- Heater controls: Heat On, Oscillate, Sleep Mode, Timer

### Design Principles (from RateMate inspiration)
- Savings is THE hero number
- Light background, green for money saved
- Tell a story: Grid costs X → You pay Y → Here's why
- Progressive disclosure (details below the fold)

## Notes
- Heater uses ~1500W when actively heating regardless of Low/Medium/High setting
- Cloud API doesn't expose active heat level, so can't track actual power draw
- Battery integration will solve this by reporting actual outlet power
- Time-of-use rates: cheap overnight, expensive 8am-midnight
