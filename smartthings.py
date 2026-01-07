"""
SmartThings Outlet Control Module

Controls smart outlets (like TP-Link Tapo) via SmartThings Cloud API.
Requires a Personal Access Token from https://account.smartthings.com/tokens

Main capabilities:
- Turn outlet on/off
- Read outlet state (on/off)
- Read power consumption (if device supports it)

Usage:
    # List all devices
    venv/bin/python smartthings.py devices

    # Show outlet status
    venv/bin/python smartthings.py status

    # Turn on
    venv/bin/python smartthings.py on

    # Turn off
    venv/bin/python smartthings.py off

API Documentation: https://developer.smartthings.com/docs/api/public
"""

import os
import sys
import json
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.smartthings.com/v1"


class SmartThingsOutlet:
    """
    SmartThings outlet controller using the official Cloud API.

    Environment variables required:
        SMARTTHINGS_TOKEN - Personal Access Token from account.smartthings.com/tokens
        SMARTTHINGS_DEVICE_ID - Device ID of the outlet (find via 'devices' command)
    """

    def __init__(self):
        self.token = os.getenv("SMARTTHINGS_TOKEN")
        self.device_id = os.getenv("SMARTTHINGS_DEVICE_ID")
        self._configured = bool(self.token)

    @property
    def is_configured(self) -> bool:
        """Check if API credentials are set up."""
        return self._configured

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make authenticated API request."""
        if not self.token:
            return {"error": "SmartThings API not configured - set SMARTTHINGS_TOKEN in .env"}

        url = f"{API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            if data:
                req = Request(
                    url,
                    data=json.dumps(data).encode("utf-8"),
                    headers=headers,
                    method=method,
                )
            else:
                req = Request(url, headers=headers, method=method)

            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))

        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            try:
                error_json = json.loads(error_body)
                return {"error": f"HTTP {e.code}: {error_json.get('message', error_body)}"}
            except json.JSONDecodeError:
                return {"error": f"HTTP {e.code}: {error_body}"}
        except URLError as e:
            return {"error": f"Connection error: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # DEVICE DISCOVERY
    # =========================================================================

    def get_devices(self) -> dict:
        """Get list of all devices linked to this SmartThings account."""
        return self._request("GET", "/devices")

    def get_device_info(self, device_id: str = None) -> dict:
        """Get detailed info about a specific device."""
        device_id = device_id or self.device_id
        if not device_id:
            return {"error": "No device ID specified - set SMARTTHINGS_DEVICE_ID in .env"}
        return self._request("GET", f"/devices/{device_id}")

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def get_status(self) -> dict:
        """
        Get outlet status including on/off state and power readings.

        Returns:
            dict with keys:
                - configured: bool - whether API credentials are set
                - error: str or None - error message if failed
                - on: bool - True if outlet is on
                - power_w: float or None - current power draw in watts
                - energy_kwh: float or None - total energy consumed in kWh
                - voltage_v: float or None - voltage reading
        """
        if not self._configured:
            return {
                "configured": False,
                "error": "SmartThings API not configured",
            }

        if not self.device_id:
            return {
                "configured": True,
                "error": "No device ID - set SMARTTHINGS_DEVICE_ID in .env or run 'devices' command",
            }

        response = self._request("GET", f"/devices/{self.device_id}/status")

        if "error" in response:
            return {"configured": True, "error": response["error"]}

        # Parse component status
        components = response.get("components", {})
        main = components.get("main", {})

        # Switch state
        switch_state = main.get("switch", {}).get("switch", {}).get("value")
        is_on = switch_state == "on"

        # Power meter (watts)
        power_w = main.get("powerMeter", {}).get("power", {}).get("value")

        # Energy meter (kWh)
        energy_kwh = main.get("energyMeter", {}).get("energy", {}).get("value")

        # Voltage
        voltage_v = main.get("voltageMeasurement", {}).get("voltage", {}).get("value")

        # Current (amps)
        current_a = main.get("currentMeasurement", {}).get("current", {}).get("value")

        return {
            "configured": True,
            "error": None,
            "on": is_on,
            "power_w": power_w,
            "energy_kwh": energy_kwh,
            "voltage_v": voltage_v,
            "current_a": current_a,
            "raw": response,
        }

    # =========================================================================
    # CONTROL OPERATIONS
    # =========================================================================

    def turn_on(self) -> dict:
        """Turn the outlet on."""
        if not self.device_id:
            return {"error": "No device ID - set SMARTTHINGS_DEVICE_ID in .env"}

        return self._request("POST", f"/devices/{self.device_id}/commands", {
            "commands": [{
                "component": "main",
                "capability": "switch",
                "command": "on",
            }]
        })

    def turn_off(self) -> dict:
        """Turn the outlet off."""
        if not self.device_id:
            return {"error": "No device ID - set SMARTTHINGS_DEVICE_ID in .env"}

        return self._request("POST", f"/devices/{self.device_id}/commands", {
            "commands": [{
                "component": "main",
                "capability": "switch",
                "command": "off",
            }]
        })


def print_devices(outlet: SmartThingsOutlet):
    """Print all devices linked to SmartThings."""
    result = outlet.get_devices()

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    items = result.get("items", [])
    if not items:
        print("No devices found.")
        return

    print(f"\n{'='*60}")
    print(f"  SmartThings Devices ({len(items)} found)")
    print(f"{'='*60}")

    for device in items:
        device_id = device.get("deviceId", "?")
        label = device.get("label", device.get("name", "Unknown"))
        device_type = device.get("deviceTypeName", "")

        # Get capabilities
        caps = []
        for component in device.get("components", []):
            for cap in component.get("capabilities", []):
                cap_id = cap.get("id", "")
                if cap_id in ("switch", "powerMeter", "energyMeter"):
                    caps.append(cap_id)

        caps_str = ", ".join(caps) if caps else "no power caps"

        print(f"\n  {label}")
        print(f"    ID:   {device_id}")
        print(f"    Type: {device_type}")
        print(f"    Caps: {caps_str}")

    print(f"\n{'='*60}")
    print("  To use a device, add to .env:")
    print("  SMARTTHINGS_DEVICE_ID=<device-id>")
    print(f"{'='*60}\n")


def print_status(outlet: SmartThingsOutlet):
    """Print formatted outlet status."""
    status = outlet.get_status()

    if not status.get("configured"):
        print("ERROR: SmartThings API not configured")
        print("Add to .env:")
        print("  SMARTTHINGS_TOKEN=your_token")
        print("\nGet token from: https://account.smartthings.com/tokens")
        return

    if status.get("error"):
        print(f"ERROR: {status['error']}")
        return

    state = "ON" if status.get("on") else "OFF"
    power = status.get("power_w")
    energy = status.get("energy_kwh")
    voltage = status.get("voltage_v")
    current = status.get("current_a")

    print(f"\n{'='*40}")
    print(f"  SmartThings Outlet Status")
    print(f"{'='*40}")
    print(f"  State:   {state}")

    if power is not None:
        print(f"  Power:   {power:.1f}W")
    if voltage is not None:
        print(f"  Voltage: {voltage:.1f}V")
    if current is not None:
        print(f"  Current: {current:.2f}A")
    if energy is not None:
        print(f"  Energy:  {energy:.2f} kWh (total)")

    print(f"{'='*40}\n")


def main():
    outlet = SmartThingsOutlet()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python smartthings.py devices  - List all devices")
        print("  python smartthings.py status   - Show outlet status")
        print("  python smartthings.py on       - Turn outlet on")
        print("  python smartthings.py off      - Turn outlet off")
        print("  python smartthings.py raw      - Show raw device status")
        return

    cmd = sys.argv[1].lower()

    if cmd == "devices":
        print_devices(outlet)

    elif cmd == "status":
        print_status(outlet)

    elif cmd == "on":
        result = outlet.turn_on()
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print("Outlet turned ON")

    elif cmd == "off":
        result = outlet.turn_off()
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print("Outlet turned OFF")

    elif cmd == "raw":
        status = outlet.get_status()
        print(json.dumps(status.get("raw", status), indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Use 'devices', 'status', 'on', 'off', or 'raw'")


if __name__ == "__main__":
    main()
