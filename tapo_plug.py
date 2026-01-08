"""
Tapo Plug Control via IFTTT Webhooks

Controls TP-Link Tapo smart plug via IFTTT Maker webhooks.
Requires IFTTT Pro and two applets:
  - set_outlet_power_on -> Turn on Tapo plug
  - set_outlet_power_off -> Turn off Tapo plug

Usage:
    venv/bin/python tapo_plug.py on
    venv/bin/python tapo_plug.py off
    venv/bin/python tapo_plug.py status  # (not available via IFTTT)
"""

import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv()

# IFTTT Webhook config
IFTTT_KEY = os.getenv("IFTTT_WEBHOOK_KEY")
IFTTT_EVENT_ON = os.getenv("IFTTT_EVENT_ON", "set_outlet_power_on")
IFTTT_EVENT_OFF = os.getenv("IFTTT_EVENT_OFF", "set_outlet_power_off")


class TapoPlug:
    """
    Tapo plug controller via IFTTT webhooks.

    Environment variables:
        IFTTT_WEBHOOK_KEY - Your IFTTT Maker webhook key
        IFTTT_EVENT_ON - Event name for turning on (default: set_outlet_power_on)
        IFTTT_EVENT_OFF - Event name for turning off (default: set_outlet_power_off)
    """

    def __init__(self):
        self.key = IFTTT_KEY
        self._configured = bool(self.key)

    @property
    def is_configured(self) -> bool:
        """Check if IFTTT webhook key is set."""
        return self._configured

    def _trigger(self, event: str) -> dict:
        """Trigger an IFTTT webhook event."""
        if not self._configured:
            return {"success": False, "error": "IFTTT not configured - set IFTTT_WEBHOOK_KEY in .env"}

        url = f"https://maker.ifttt.com/trigger/{event}/with/key/{self.key}"

        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                success = "Congratulations" in body
                return {"success": success, "response": body}

        except HTTPError as e:
            return {"success": False, "error": f"HTTP {e.code}"}
        except URLError as e:
            return {"success": False, "error": f"Connection error: {e.reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def turn_on(self) -> dict:
        """Turn the plug on."""
        return self._trigger(IFTTT_EVENT_ON)

    def turn_off(self) -> dict:
        """Turn the plug off."""
        return self._trigger(IFTTT_EVENT_OFF)


def main():
    plug = TapoPlug()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tapo_plug.py on   - Turn plug on")
        print("  python tapo_plug.py off  - Turn plug off")
        return

    if not plug.is_configured:
        print("ERROR: IFTTT not configured")
        print("Add to .env:")
        print("  IFTTT_WEBHOOK_KEY=your_key_here")
        return

    cmd = sys.argv[1].lower()

    if cmd == "on":
        result = plug.turn_on()
        if result["success"]:
            print("Plug turned ON")
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")

    elif cmd == "off":
        result = plug.turn_off()
        if result["success"]:
            print("Plug turned OFF")
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")

    else:
        print(f"Unknown command: {cmd}")
        print("Use 'on' or 'off'")


if __name__ == "__main__":
    main()
