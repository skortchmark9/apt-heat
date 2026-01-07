# apt_heat Development Notes

## EcoFlow Battery Integration (Jan 2026)

**Status**: Scaffolded, awaiting API credentials

User got an EcoFlow Delta Pro battery for peak shaving. The goal is to automate charging based on ConEd TOU rates:
- Pause charging during peak hours (8am-midnight)
- Charge during off-peak (midnight-8am) at cheap rates
- Fallback: if SoC drops below threshold, allow charging anyway

### What's Done

1. **`ecoflow.py`** - Standalone script for EcoFlow Developer API
   - Auth with HMAC-SHA256 signatures (Access Key + Secret Key)
   - Read: SoC, watts in/out, charging state
   - Control: `set_ac_charging_power(watts)` - key for peak shaving (0 = pause, 1500 = charge)
   - CLI interface: `status`, `charge <watts>`, `ac-charge on|off`, `raw`, `devices`

2. **`.env`** - Has placeholders for EcoFlow credentials:
   ```
   ECOFLOW_ACCESS_KEY=
   ECOFLOW_SECRET_KEY=
   ECOFLOW_SERIAL_NUMBER=
   ECOFLOW_REGION=us
   ```

### What's Pending

1. **User needs API credentials** from developer.ecoflow.com (~1 week approval wait)
   - Serial number is on the device or in EcoFlow app

2. **Test the API** once credentials arrive:
   ```bash
   venv/bin/python ecoflow.py devices   # verify auth works
   venv/bin/python ecoflow.py status    # check telemetry
   venv/bin/python ecoflow.py raw       # see actual param names for Delta Pro
   ```
   The param names in `_extract()` are guesses based on docs - may need adjustment for Delta Pro (original, not Pro 3).

3. **Build automation logic** - options:
   - Cron jobs that call `ecoflow.py charge 0` and `ecoflow.py charge 1500`
   - Integrate into `app.py` polling loop (check time, adjust charge power)
   - New `battery_control_loop.py` similar to existing `control_loop.py`

4. **Dashboard integration** - the battery card in the carousel already exists in `app.py` but shows placeholder data. Wire it up to `/api/battery` endpoint.

### API Notes

- EcoFlow Developer API: https://developer.ecoflow.com
- US endpoint: `api.ecoflow.com`, EU: `api-e.ecoflow.com`
- Delta Pro is supported (confirmed in their device list)
- Key endpoint: `PUT /iot-open/sign/device/quota` with `cmdCode` for commands
- The exact `cmdCode` values (like `WN511_SET_AC_CHARGING_POWER`) may differ for Delta Pro - check raw response

### Peak Shaving Logic (Future)

```python
# Pseudocode for automation
from rates import is_peak_hour

def battery_control_loop():
    battery = EcoFlowBattery()
    status = battery.get_status()

    if is_peak_hour():
        # During peak: don't charge from grid
        if status['charging'] and status['ac_charge_watts'] > 0:
            battery.set_ac_charging_power(0)
    else:
        # Off-peak: charge at full speed
        if status['soc'] < 100:
            battery.set_ac_charging_power(1500)

    # Emergency override: low battery
    if status['soc'] < 35:
        battery.set_ac_charging_power(1500)  # charge anyway
```

---

## Pending Feature: Morning Report

When waking up, show a summary of the night:

**Sleep Summary**
- Sleep mode start/end times
- How well actual temp tracked the target curve (deviation chart?)
- Min/max temp during the night

**Energy & Savings**
- Total kWh used overnight
- Peak vs off-peak breakdown
- Savings vs grid at peak rates (from rates.py calculations)

**Heater Activity**
- Total time heater was running
- On/off cycles count
- Average power draw when on

Could be: a card in the carousel, or a tap-to-expand detail view.

---

## Braindump: React Rewrite

### Why Rewrite?

The current implementation is all inline HTML/JS/CSS in `app.py`. It's becoming spaghetti:

- ~1500+ lines of HTML/JS embedded in Python string
- Global variables everywhere (`currentTemp`, `setpoint`, `sleepCurvePoints`, etc.)
- Event handlers defined inline
- State scattered between JS variables, localStorage, and server
- Canvas drawing logic mixed with UI logic
- Hard to test, hard to refactor
- No type safety on frontend
- CSS is inline styles + a `<style>` block

### What We Have Now

**UI Components** (implicitly):
- Temperature display (current temp, setpoint, feels like)
- Temperature controls (+/- buttons, slider)
- Status card carousel (3 cards: current status, schedule, battery)
- Sleep mode panel (wake time picker, temperature curve canvas)
- Temperature history chart
- Power chart
- Sleep progress overlay (when viewing active sleep)

**State**:
- `currentTemp`, `setpoint`, `humidity`, `feelsLike` - from server polling
- `sleepCurvePoints` - localStorage (relative deltas)
- `sleepWakeTime` - localStorage
- `sleepModeActive` - from server
- `activeSleepSchedule` - from server (absolute temps)
- Chart data (readings array)
- Carousel position

**API Endpoints**:
- `GET /api/status` - current heater state
- `POST /api/setpoint` - change target temp
- `GET /api/readings` - historical data
- `POST /api/sleep` - start sleep mode
- `DELETE /api/sleep` - cancel sleep mode
- `GET /api/savings` - savings calculations

### Proposed React Architecture

```
src/
├── components/
│   ├── TemperatureDisplay.tsx    # Current temp, feels like
│   ├── TemperatureControls.tsx   # +/- buttons, slider
│   ├── StatusCarousel/
│   │   ├── index.tsx
│   │   ├── CurrentStatusCard.tsx
│   │   ├── ScheduleCard.tsx
│   │   └── BatteryCard.tsx
│   ├── SleepMode/
│   │   ├── SleepPanel.tsx        # Main sleep config panel
│   │   ├── WakeTimePicker.tsx    # Scrollable time picker
│   │   ├── TemperatureCurve.tsx  # Canvas curve editor
│   │   └── SleepProgress.tsx     # Progress overlay when active
│   ├── Charts/
│   │   ├── TemperatureChart.tsx
│   │   └── PowerChart.tsx
│   └── MorningReport/
│       └── MorningReport.tsx     # New feature
├── hooks/
│   ├── useHeaterStatus.ts        # Polling /api/status
│   ├── useReadings.ts            # Fetching historical data
│   ├── useSleepCurve.ts          # localStorage curve + API
│   └── useSavings.ts             # Savings calculations
├── contexts/
│   └── HeaterContext.tsx         # Global heater state
├── types/
│   └── index.ts                  # TypeScript interfaces
├── utils/
│   ├── temperature.ts            # Conversion helpers
│   ├── time.ts                   # Time formatting
│   └── curve.ts                  # Bezier interpolation
└── App.tsx
```

### Key Decisions to Make

1. **Build tool**: Vite? Next.js? Create React App is dead.
   - Vite is probably simplest for SPA
   - Could do Next.js if we want SSR later

2. **State management**:
   - React Context + hooks is probably fine (not that complex)
   - Could use Zustand if it gets hairy

3. **Styling**:
   - Tailwind? (fast, but lots of classes)
   - CSS Modules? (cleaner JSX)
   - styled-components? (meh)

4. **Charts**:
   - Keep canvas-based custom charts?
   - Use a library like Recharts, Chart.js, or visx?

5. **Deployment**:
   - Build React app, serve static files from FastAPI
   - Or separate frontend deploy (Vercel/Netlify) + API on Railway

### Migration Path

1. Set up Vite + React + TypeScript project in `frontend/`
2. Extract types from current implementation
3. Build components one by one, testing against live API
4. Add React Router if needed (probably not - single page)
5. Once feature-complete, remove inline HTML from app.py
6. Serve built React app from FastAPI static files

### What to Keep in Python

- All API endpoints (FastAPI is great)
- Database models
- Tuya integration
- Rate calculations (rates.py)
- Background polling task

### Nice-to-Haves for React Version

- [ ] TypeScript throughout
- [ ] Better error handling / loading states
- [ ] Pull-to-refresh on mobile
- [ ] Service worker for offline support
- [ ] Push notifications (wake up report!)
- [ ] Dark mode (it's a heater app, probably used at night)
- [ ] Haptic feedback on mobile interactions
- [ ] Undo for setpoint changes
- [ ] Presets (e.g., "Movie night", "Sleeping", "Away")
