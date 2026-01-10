# Project Notes for Claude

## Python Environment

**Requires Python 3.13+** - Python 3.12 has a socket bug on macOS that breaks local Tuya device connections.

To recreate the venv:
```bash
rm -rf venv
python3.13 -m venv venv
venv/bin/pip install -r requirements.txt
```

Always use the project venv for Python operations:

```bash
source venv/bin/activate
```

Or invoke directly:

```bash
venv/bin/python script.py
venv/bin/pip install package
```

## Project Overview

Home energy automation - controlling a Lasko AR122 smart heater via Tuya API for peak shaving with an EcoFlow battery.

## Railway CLI

Railway CLI is installed locally in `tools/`. Use it like:

```bash
./tools/node_modules/.bin/railway logs
./tools/node_modules/.bin/railway status
```

You'll need to run `railway login` first if not authenticated.

## Timezone Handling

**IMPORTANT:** Railway servers run in UTC, but the user is in NYC (America/New_York).

- Always use `LOCAL_TZ = ZoneInfo("America/New_York")` for user-facing times
- Sleep schedules, wake times, and any time the user sees/sets should be in local time
- Use `datetime.now(LOCAL_TZ)` instead of `datetime.now()` for local time comparisons
- Store times with timezone info: `now.isoformat()` will include the offset
- Database timestamps for readings can stay UTC (they're internal)

```python
from zoneinfo import ZoneInfo
LOCAL_TZ = ZoneInfo("America/New_York")
now = datetime.now(LOCAL_TZ)  # Correct
now = datetime.now()  # WRONG - returns UTC on Railway
```

## Key Files

- `.env` - Tuya API credentials (never commit)
- `devices.json` - Tuya device cache with local keys (never commit)
- `tools/` - Local npm packages for Railway CLI (gitignored)
- `rates.py` - ConEd TOU rate constants and peak hour logic (from ratemate)
