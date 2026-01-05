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

## Railway CLI

Railway CLI is installed locally in `tools/`. Use it like:

```bash
./tools/node_modules/.bin/railway logs
./tools/node_modules/.bin/railway status
```

You'll need to run `railway login` first if not authenticated.

## Key Files

- `.env` - Tuya API credentials (never commit)
- `devices.json` - Tuya device cache with local keys (never commit)
- `tools/` - Local npm packages for Railway CLI (gitignored)
