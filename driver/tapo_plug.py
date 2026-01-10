"""
Tapo Plug Control Module

Controls TP-Link Tapo P115 smart plug via local API or IFTTT webhooks.

Local mode (preferred):
    Requires: TPLINK_EMAIL, TPLINK_PASSWORD, TAPO_IP in .env
    Supports: on, off, status, energy monitoring

IFTTT mode (fallback):
    Requires: IFTTT_WEBHOOK_KEY in .env
    Supports: on, off only (no status)

Usage:
    venv/bin/python tapo_plug.py on
    venv/bin/python tapo_plug.py off
    venv/bin/python tapo_plug.py status
"""

import asyncio
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv()

# Local mode config
TPLINK_EMAIL = os.getenv("TPLINK_EMAIL")
TPLINK_PASSWORD = os.getenv("TPLINK_PASSWORD")
TAPO_IP = os.getenv("TAPO_IP")

# IFTTT fallback config
IFTTT_KEY = os.getenv("IFTTT_WEBHOOK_KEY")
IFTTT_EVENT_ON = os.getenv("IFTTT_EVENT_ON", "set_outlet_power_on")
IFTTT_EVENT_OFF = os.getenv("IFTTT_EVENT_OFF", "set_outlet_power_off")


class TapoPlug:
    """
    Tapo plug controller supporting local and IFTTT modes.

    Local mode environment variables:
        TPLINK_EMAIL - TP-Link account email
        TPLINK_PASSWORD - TP-Link account password
        TAPO_IP - Plug IP address (e.g., 192.168.0.65)

    IFTTT mode environment variables:
        IFTTT_WEBHOOK_KEY - Your IFTTT Maker webhook key
        IFTTT_EVENT_ON - Event name for turning on (default: set_outlet_power_on)
        IFTTT_EVENT_OFF - Event name for turning off (default: set_outlet_power_off)
    """

    def __init__(self, mode: str = "auto"):
        """
        Initialize plug controller.

        Args:
            mode: "local", "ifttt", or "auto" (tries local first)
        """
        self._local_available = all([TPLINK_EMAIL, TPLINK_PASSWORD, TAPO_IP])
        self._ifttt_available = bool(IFTTT_KEY)
        self._mode = None
        self._client = None
        self._device = None

        if mode == "auto":
            if self._local_available:
                self._mode = "local"
            elif self._ifttt_available:
                self._mode = "ifttt"
        elif mode == "local" and self._local_available:
            self._mode = "local"
        elif mode == "ifttt" and self._ifttt_available:
            self._mode = "ifttt"

    @property
    def mode(self) -> str | None:
        """Get current control mode."""
        return self._mode

    @property
    def is_configured(self) -> bool:
        """Check if any control method is configured."""
        return self._mode is not None

    async def _get_device(self):
        """Get or create the tapo device connection."""
        if self._device is None:
            from tapo import ApiClient
            self._client = ApiClient(TPLINK_EMAIL, TPLINK_PASSWORD)
            self._device = await self._client.p115(TAPO_IP)
        return self._device

    async def _local_turn_on(self) -> dict:
        """Turn on via local API."""
        try:
            device = await self._get_device()
            await device.on()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _local_turn_off(self) -> dict:
        """Turn off via local API."""
        try:
            device = await self._get_device()
            await device.off()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _local_status(self) -> dict:
        """Get status via local API."""
        try:
            device = await self._get_device()
            info = await device.get_device_info()
            energy = await device.get_energy_usage()
            return {
                "success": True,
                "on": info.device_on,
                "nickname": info.nickname,
                "today_energy_wh": energy.today_energy,
                "today_runtime_min": energy.today_runtime,
                "month_energy_wh": energy.month_energy,
                "month_runtime_min": energy.month_runtime,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _local_full_status(self) -> dict:
        """Get full status with all available fields via local API."""
        try:
            device = await self._get_device()
            info = await device.get_device_info()
            energy = await device.get_energy_usage()
            info_dict = info.to_dict()
            energy_dict = energy.to_dict()
            return {
                "success": True,
                # Device info
                "device_on": info_dict.get("device_on"),
                "nickname": info_dict.get("nickname"),
                "on_time": info_dict.get("on_time"),
                "rssi": info_dict.get("rssi"),
                "signal_level": info_dict.get("signal_level"),
                "overcurrent_status": info_dict.get("overcurrent_status"),
                "overheat_status": info_dict.get("overheat_status"),
                "power_protection_status": info_dict.get("power_protection_status"),
                "charging_status": info_dict.get("charging_status"),
                "model": info_dict.get("model"),
                "fw_ver": info_dict.get("fw_ver"),
                "hw_ver": info_dict.get("hw_ver"),
                "mac": info_dict.get("mac"),
                "ip": info_dict.get("ip"),
                # Energy usage
                "today_energy": energy_dict.get("today_energy"),
                "today_runtime": energy_dict.get("today_runtime"),
                "month_energy": energy_dict.get("month_energy"),
                "month_runtime": energy_dict.get("month_runtime"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ifttt_trigger(self, event: str) -> dict:
        """Trigger an IFTTT webhook event."""
        url = f"https://maker.ifttt.com/trigger/{event}/with/key/{IFTTT_KEY}"
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
        if self._mode == "local":
            return asyncio.run(self._local_turn_on())
        elif self._mode == "ifttt":
            return self._ifttt_trigger(IFTTT_EVENT_ON)
        else:
            return {"success": False, "error": "Not configured"}

    def turn_off(self) -> dict:
        """Turn the plug off."""
        if self._mode == "local":
            return asyncio.run(self._local_turn_off())
        elif self._mode == "ifttt":
            return self._ifttt_trigger(IFTTT_EVENT_OFF)
        else:
            return {"success": False, "error": "Not configured"}

    def get_status(self) -> dict:
        """Get plug status (local mode only)."""
        if self._mode == "local":
            return asyncio.run(self._local_status())
        elif self._mode == "ifttt":
            return {"success": False, "error": "Status not available via IFTTT"}
        else:
            return {"success": False, "error": "Not configured"}

    def get_full_status(self) -> dict:
        """Get full plug status with all available fields (local mode only)."""
        if self._mode == "local":
            return asyncio.run(self._local_full_status())
        elif self._mode == "ifttt":
            return {"success": False, "error": "Status not available via IFTTT"}
        else:
            return {"success": False, "error": "Not configured"}

    def is_on(self) -> bool | None:
        """Check if plug is on (local mode only)."""
        status = self.get_status()
        if status.get("success"):
            return status.get("on")
        return None


def main():
    plug = TapoPlug()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tapo_plug.py on     - Turn plug on")
        print("  python tapo_plug.py off    - Turn plug off")
        print("  python tapo_plug.py status - Get plug status (local mode only)")
        return

    if not plug.is_configured:
        print("ERROR: Not configured")
        print("Add to .env for local mode:")
        print("  TPLINK_EMAIL=your@email.com")
        print("  TPLINK_PASSWORD=yourpassword")
        print("  TAPO_IP=192.168.0.65")
        print("Or for IFTTT mode:")
        print("  IFTTT_WEBHOOK_KEY=your_key_here")
        return

    cmd = sys.argv[1].lower()

    if cmd == "on":
        result = plug.turn_on()
        if result["success"]:
            print(f"Plug turned ON (via {plug.mode})")
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")

    elif cmd == "off":
        result = plug.turn_off()
        if result["success"]:
            print(f"Plug turned OFF (via {plug.mode})")
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")

    elif cmd == "status":
        result = plug.get_status()
        if result["success"]:
            print(f"Plug Status (via {plug.mode}):")
            print(f"  Name: {result['nickname']}")
            print(f"  On: {result['on']}")
            print(f"  Today: {result['today_energy_wh']}Wh, {result['today_runtime_min']}min")
            print(f"  Month: {result['month_energy_wh']}Wh, {result['month_runtime_min']}min")
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")

    else:
        print(f"Unknown command: {cmd}")
        print("Use 'on', 'off', or 'status'")


if __name__ == "__main__":
    main()
