"""
EcoFlow Delta Pro Battery Control Module

Controls EcoFlow Delta Pro via the official EcoFlow Developer API.
Requires Access Key and Secret Key from developer.ecoflow.com.

Main capabilities:
- Set AC charging power (0-3000W) - use 0 to pause charging during peak
- Enable/disable AC charging
- Read: SoC, AC input/output power, charging state

Usage:
    # Check status
    venv/bin/python ecoflow.py status

    # Set charging power to 0 (pause charging during peak)
    venv/bin/python ecoflow.py charge 0

    # Resume charging at 1500W
    venv/bin/python ecoflow.py charge 1500

    # Disable AC charging entirely
    venv/bin/python ecoflow.py ac-charge off

API Documentation: https://developer.ecoflow.com/us/document/introduction
"""

import os
import sys
import time
import hmac
import hashlib
import json
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv()

# API endpoints
API_BASE_US = "https://api.ecoflow.com"
API_BASE_EU = "https://api-e.ecoflow.com"


class EcoFlowBattery:
    """
    EcoFlow Delta Pro battery controller using the official Developer API.

    Environment variables required:
        ECOFLOW_ACCESS_KEY - Developer API access key
        ECOFLOW_SECRET_KEY - Developer API secret key
        ECOFLOW_SERIAL_NUMBER - Device serial number (on device or in app)
        ECOFLOW_REGION - "us" or "eu" (default: us)
    """

    def __init__(self):
        self.access_key = os.getenv("ECOFLOW_ACCESS_KEY")
        self.secret_key = os.getenv("ECOFLOW_SECRET_KEY")
        self.serial_number = os.getenv("ECOFLOW_SERIAL_NUMBER")
        region = os.getenv("ECOFLOW_REGION", "us").lower()

        self.api_base = API_BASE_EU if region == "eu" else API_BASE_US

        # Check if credentials are configured
        self._configured = bool(
            self.access_key and self.secret_key and self.serial_number
        )

    @property
    def is_configured(self) -> bool:
        """Check if API credentials are set up."""
        return self._configured

    def _flatten_params(self, params: dict, prefix: str = "") -> dict:
        """
        Flatten nested dict for signature generation.

        {"params": {"slowChgWatts": 0}} -> {"params.slowChgWatts": 0}
        """
        result = {}
        for key, value in params.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(self._flatten_params(value, full_key))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        result.update(self._flatten_params(item, f"{full_key}[{i}]"))
                    else:
                        result[f"{full_key}[{i}]"] = item
            else:
                result[full_key] = value
        return result

    def _generate_signature(self, params: dict, timestamp: str, nonce: str) -> str:
        """
        Generate HMAC-SHA256 signature for API request.

        EcoFlow API requires: flattened sorted params + accessKey + nonce + timestamp
        """
        # Flatten nested params for signature
        flat_params = self._flatten_params(params) if params else {}

        # Sort params alphabetically by ASCII
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(flat_params.items())
        ) if flat_params else ""

        # Build sign string - params come FIRST, then accessKey/nonce/timestamp
        if sorted_params:
            sign_str = f"{sorted_params}&accessKey={self.access_key}&nonce={nonce}&timestamp={timestamp}"
        else:
            sign_str = f"accessKey={self.access_key}&nonce={nonce}&timestamp={timestamp}"

        # HMAC-SHA256
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    def _request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Make authenticated API request."""
        if not self._configured:
            return {"error": "EcoFlow API not configured - set ECOFLOW_ACCESS_KEY, ECOFLOW_SECRET_KEY, ECOFLOW_SERIAL_NUMBER in .env"}

        timestamp = str(int(time.time() * 1000))
        nonce = str(int(time.time() * 1000000) % 1000000)  # 6-digit nonce

        params = params or {}
        signature = self._generate_signature(params, timestamp, nonce)

        headers = {
            "accessKey": self.access_key,
            "timestamp": timestamp,
            "nonce": nonce,
            "sign": signature,
        }

        url = f"{self.api_base}{endpoint}"

        try:
            if method == "GET":
                if params:
                    query = "&".join(f"{k}={v}" for k, v in params.items())
                    url = f"{url}?{query}"
                req = Request(url, headers=headers, method="GET")
            else:
                headers["Content-Type"] = "application/json"
                req = Request(
                    url,
                    data=json.dumps(params).encode('utf-8'),
                    headers=headers,
                    method=method
                )

            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))

        except HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            return {"error": f"HTTP {e.code}: {error_body}"}
        except URLError as e:
            return {"error": f"Connection error: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    def get_device_list(self) -> dict:
        """Get list of devices linked to this account."""
        return self._request("GET", "/iot-open/sign/device/list")

    def get_quota_all(self) -> dict:
        """
        Get all device parameters (quota) for the Delta Pro.
        Returns raw API response with all device data points.
        """
        return self._request("GET", "/iot-open/sign/device/quota/all", {
            "sn": self.serial_number
        })

    def _extract(self, data: dict, *keys) -> Any:
        """Extract value from dict, trying multiple possible keys."""
        for key in keys:
            # First try as literal key (for flattened data like "pd.soc")
            if key in data:
                return data[key]
            # Then try nested traversal (for nested data)
            parts = key.split(".")
            value = data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
            if value is not None:
                return value
        return None

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def get_status(self) -> dict:
        """
        Get battery status - the key telemetry for peak shaving.

        Returns:
            dict with keys:
                - configured: bool - whether API credentials are set
                - error: str or None - error message if failed
                - soc: int - State of charge (0-100%)
                - watts_in: int - AC input power (W)
                - watts_out: int - AC output power (W)
                - charging: bool - True if actively charging
                - discharging: bool - True if actively discharging
                - ac_charge_watts: int - Current AC charge power setting (W)
        """
        if not self._configured:
            return {
                "configured": False,
                "error": "EcoFlow API not configured",
            }

        response = self.get_quota_all()

        if "error" in response:
            return {"configured": True, "error": response["error"]}

        if response.get("code") != "0":
            return {
                "configured": True,
                "error": response.get("message", f"API error code: {response.get('code')}")
            }

        # Parse the quota data
        data = response.get("data", {})

        # Extract key values - Delta Pro parameter names
        soc = self._extract(data, "soc", "pd.soc", "bms_bmsStatus.soc")
        watts_in = self._extract(data, "wattsInSum", "pd.wattsInSum", "inv.inputWatts") or 0
        watts_out = self._extract(data, "wattsOutSum", "pd.wattsOutSum", "inv.outputWatts") or 0
        ac_charge_watts = self._extract(data, "slowChgWatts", "inv.cfgSlowChgWatts", "inv.slowChgWatts")
        min_discharge_soc = self._extract(data, "ems.minDsgSoc", "minDsgSoc")

        # Determine actual charging/discharging state based on net power flow
        # (watts_in includes pass-through power to load, not just battery charging)
        net_power = watts_in - watts_out
        charging = net_power > 50  # Net energy going INTO battery
        discharging = net_power < -50  # Net energy coming FROM battery

        return {
            "configured": True,
            "error": None,
            "soc": soc,
            "watts_in": watts_in,
            "watts_out": watts_out,
            "charging": charging,
            "discharging": discharging,
            "ac_charge_watts": ac_charge_watts,
            "min_discharge_soc": min_discharge_soc,
            "raw": data  # Full data for debugging
        }

    # =========================================================================
    # CONTROL OPERATIONS
    # =========================================================================

    def set_ac_charging_power(self, watts: int) -> dict:
        """
        Set AC charging power limit.

        This is the key control for peak shaving:
        - Set to 0 during peak hours to pause charging
        - Set to desired wattage during off-peak to charge

        Args:
            watts: 0-2900W (200W minimum when charging, 0 to pause)

        Returns:
            dict with success status or error
        """
        # Delta Pro: min 200W when charging, max 2900W
        # Use 0 to effectively pause (will be handled by chgPauseFlag)
        if watts > 0:
            watts = max(200, min(2900, watts))

        # Delta Pro uses cmdSet:32, id:69 for slow charge power
        return self._request("PUT", "/iot-open/sign/device/quota", {
            "sn": self.serial_number,
            "params": {
                "cmdSet": 32,
                "id": 69,
                "slowChgPower": watts
            }
        })

    def set_ac_charging_enabled(self, enabled: bool) -> dict:
        """
        Enable or disable AC charging entirely.

        Args:
            enabled: True to allow AC charging, False to disable

        Returns:
            dict with success status or error
        """
        return self._request("PUT", "/iot-open/sign/device/quota", {
            "sn": self.serial_number,
            "cmdCode": "WN511_SET_AC_CHG_SWITCH",
            "params": {"enabled": 1 if enabled else 0}
        })

    def set_max_charge_level(self, percent: int) -> dict:
        """Set maximum charge level (50-100%)."""
        percent = max(50, min(100, percent))
        return self._request("PUT", "/iot-open/sign/device/quota", {
            "sn": self.serial_number,
            "cmdCode": "WN511_SET_SOC_MAX",
            "params": {"maxChgSoc": percent}
        })

    def set_min_discharge_level(self, percent: int) -> dict:
        """Set minimum discharge level / reserve (0-30%)."""
        percent = max(0, min(30, percent))
        return self._request("PUT", "/iot-open/sign/device/quota", {
            "sn": self.serial_number,
            "cmdCode": "WN511_SET_SOC_MIN",
            "params": {"minDsgSoc": percent}
        })


def print_status(battery: EcoFlowBattery):
    """Print formatted battery status."""
    status = battery.get_status()

    if not status.get("configured"):
        print("ERROR: EcoFlow API not configured")
        print("Add these to .env:")
        print("  ECOFLOW_ACCESS_KEY=your_access_key")
        print("  ECOFLOW_SECRET_KEY=your_secret_key")
        print("  ECOFLOW_SERIAL_NUMBER=your_serial_number")
        return

    if status.get("error"):
        print(f"ERROR: {status['error']}")
        return

    soc = status.get("soc")
    watts_in = status.get("watts_in", 0)
    watts_out = status.get("watts_out", 0)

    # Determine state
    if status.get("charging"):
        state = "CHARGING"
        state_icon = "+"
    elif status.get("discharging"):
        state = "DISCHARGING"
        state_icon = "-"
    else:
        state = "IDLE"
        state_icon = "="

    print(f"\n{'='*40}")
    print(f"  EcoFlow Delta Pro Status")
    print(f"{'='*40}")
    print(f"  Battery:     {soc}%")
    print(f"  State:       {state} ({state_icon})")
    print(f"  AC In:       {watts_in}W")
    print(f"  AC Out:      {watts_out}W")
    if status.get("ac_charge_watts") is not None:
        print(f"  Charge Limit: {status['ac_charge_watts']}W")
    if status.get("min_discharge_soc") is not None:
        print(f"  Min Reserve:  {status['min_discharge_soc']}%")
    print(f"{'='*40}\n")


def main():
    battery = EcoFlowBattery()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ecoflow.py status          - Show battery status")
        print("  python ecoflow.py charge <watts>  - Set AC charge power (0-3000)")
        print("  python ecoflow.py ac-charge on    - Enable AC charging")
        print("  python ecoflow.py ac-charge off   - Disable AC charging")
        print("  python ecoflow.py raw             - Show raw API response")
        print("  python ecoflow.py devices         - List linked devices")
        return

    cmd = sys.argv[1].lower()

    if cmd == "status":
        print_status(battery)

    elif cmd == "charge":
        if len(sys.argv) < 3:
            print("Usage: python ecoflow.py charge <watts>")
            print("Example: python ecoflow.py charge 0    # Pause charging")
            print("Example: python ecoflow.py charge 1500 # Charge at 1500W")
            return
        watts = int(sys.argv[2])
        result = battery.set_ac_charging_power(watts)
        if result.get("code") == "0":
            print(f"AC charging power set to {watts}W")
        else:
            print(f"Error: {result}")

    elif cmd == "ac-charge":
        if len(sys.argv) < 3:
            print("Usage: python ecoflow.py ac-charge on|off")
            return
        enabled = sys.argv[2].lower() in ("on", "true", "1", "yes")
        result = battery.set_ac_charging_enabled(enabled)
        if result.get("code") == "0":
            print(f"AC charging {'enabled' if enabled else 'disabled'}")
        else:
            print(f"Error: {result}")

    elif cmd == "raw":
        result = battery.get_quota_all()
        print(json.dumps(result, indent=2))

    elif cmd == "devices":
        result = battery.get_device_list()
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Use 'status', 'charge', 'ac-charge', 'raw', or 'devices'")


if __name__ == "__main__":
    main()
