# Project Notes for Claude

## Python Environment

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

## Key Files

- `.env` - Tuya API credentials (never commit)
- `devices.json` - Tuya device cache with local keys (never commit)
