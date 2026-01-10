"""
Lasko AR122 Heater Control Module

Supports both local (LAN) and cloud (Tuya API) control modes.

DPS Mapping (confirmed):
  1   - Power (bool)
  3   - Current room temp (int, °F, read-only)
  5   - Heat mode setting ("Low" / "Medium" / "High")
        Low = 750W/low fan, Medium = 1500W/low fan, High = 1500W/high fan
  8   - Oscillation (bool) - NOTE: conflicts with person detection (101)
  10  - Display on (bool) - screen/LED display, False = night mode / dimmed
  11  - Active heat level ("Stop" / "Low" / "Medium" / "High", read-only)
        Shows actual operating mode. "Stop" when at/above setpoint.
  14  - Target temp setpoint (int, °F)
  101 - Person detection / ClimaSense (bool) - NOTE: conflicts with oscillation (8)
  102 - Auto-on (bool) - turn on automatically when person detected
  103 - Person detection timeout ("5min" / "15min" / "30min")
  105 - Timer value (int, read-only)
        Base value (~59) when no timer. When timer active: base + seconds_remaining.
        Heater auto-off when countdown reaches base value.
  106 - Energy usage (int, kWh, read-only)

DPS Mapping (confirmed):
  108 - Fault code (int, bitmask, read-only)
        0 = no fault (fully cleared)
        1 = partial clear (after physical button, before WiFi reconnect)
        16 = tip-over fault (heater knocked over)
        On fault: heater auto-powers-off, ignores remote power-on commands.
        To clear: press physical button, then press WiFi button on heater.

DPS Mapping (semi-confirmed):
  107 - Session heating flag (bool, read-only)
        True after power on. Goes False when target set above room temp.
        Stays False until power cycle. Tracks "has heated this session".

DPS Mapping (unconfirmed):
  104 - Unknown (bool)
"""

import os
from enum import Enum
from typing import Any

import tinytuya
from dotenv import load_dotenv

load_dotenv()

# DPS constants
DPS_POWER = "1"
DPS_CURRENT_TEMP = "3"
DPS_HEAT_MODE = "5"
DPS_OSCILLATION = "8"
DPS_ACTIVE_HEAT_LEVEL = "11"
DPS_TARGET_TEMP = "14"
DPS_DISPLAY = "10"
DPS_PERSON_DETECTION = "101"
DPS_AUTO_ON = "102"
DPS_DETECTION_TIMEOUT = "103"
DPS_TIMER_VALUE = "105"
DPS_ENERGY_KWH = "106"
DPS_FAULT = "108"

TIMER_BASE_VALUE = 59  # Base value when no timer active

# Fault codes (DPS 108)
FAULT_NONE = 0           # Fully cleared
FAULT_PARTIAL_CLEAR = 1  # After physical button, before WiFi reconnect
FAULT_TIP_OVER = 16      # Heater knocked over

HEAT_MODES = ["Low", "Medium", "High"]
DETECTION_TIMEOUTS = ["5min", "15min", "30min"]

# Approximate wattage by active heat level (DPS 11)
# Modes: Low = 750W/low fan, Medium = 1500W/low fan, High = 1500W/high fan
# Note: Heater may override to High when actively heating regardless of setting
WATTAGE_BY_LEVEL = {
    "Stop": 0,
    "Low": 750,
    "Medium": 1500,
    "High": 1500,
}


class ControlMode(Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class Heater:
    """
    Lasko AR122 heater controller supporting both local and cloud modes.

    Usage:
        # Local mode (default) - direct LAN connection
        heater = Heater(mode="local")

        # Cloud mode - via Tuya cloud API
        heater = Heater(mode="cloud")

        # Auto mode - tries local first, falls back to cloud
        heater = Heater(mode="auto")

    Cloud Mode Limitations:
        The Tuya Cloud API only exposes a subset of device properties:
        - Supported: power, current_temp, target_temp, oscillation, display
        - NOT available: heat_mode, active_heat_level, person_detection,
          auto_on, detection_timeout, timer, energy_kwh, fault codes

        For full DPS access, use local mode.
    """

    def __init__(self, mode: str = "local"):
        """
        Initialize heater controller.

        Args:
            mode: "local" (LAN), "cloud" (Tuya API), or "auto" (try local, fallback to cloud)
        """
        self.device_id = os.getenv("HEATER_DEVICE_ID")
        self._local_device = None
        self._cloud = None
        self._mode = None

        if mode == "auto":
            # Try local first
            try:
                self._init_local()
                # Test connection
                self._local_device.status()
                self._mode = ControlMode.LOCAL
            except Exception:
                self._init_cloud()
                self._mode = ControlMode.CLOUD
        elif mode == "local":
            self._init_local()
            self._mode = ControlMode.LOCAL
        elif mode == "cloud":
            self._init_cloud()
            self._mode = ControlMode.CLOUD
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'local', 'cloud', or 'auto'")

    def _init_local(self):
        """Initialize local LAN connection."""
        self._local_device = tinytuya.Device(
            dev_id=self.device_id,
            address=os.getenv("HEATER_IP"),
            local_key=os.getenv("HEATER_LOCAL_KEY"),
            version=float(os.getenv("HEATER_VERSION", "3.3"))
        )

    def _init_cloud(self):
        """Initialize cloud API connection."""
        self._cloud = tinytuya.Cloud(
            apiRegion=os.getenv("TUYA_REGION", "us"),
            apiKey=os.getenv("TUYA_ACCESS_ID"),
            apiSecret=os.getenv("TUYA_ACCESS_SECRET")
        )

    @property
    def mode(self) -> str:
        """Get current control mode."""
        return self._mode.value

    def _get_value(self, dps_id: str) -> Any:
        """Get a single DPS value."""
        dps = self.get_status()
        return dps.get(dps_id)

    def _set_value(self, dps_id: str, value: Any) -> dict:
        """Set a single DPS value."""
        if self._mode == ControlMode.LOCAL:
            return self._local_device.set_value(dps_id, value)
        else:
            # Cloud mode - translate DPS ID to code name
            code = self._dps_to_code(dps_id)
            if not code:
                raise ValueError(f"DPS {dps_id} not supported in cloud mode")
            commands = {"commands": [{"code": code, "value": value}]}
            return self._cloud.sendcommand(self.device_id, commands)

    def get_status(self) -> dict:
        """Get raw DPS status from device."""
        if self._mode == ControlMode.LOCAL:
            result = self._local_device.status()
            return result.get("dps", {})
        else:
            # Cloud mode - get device status
            result = self._cloud.getstatus(self.device_id)
            # Convert cloud format to local DPS format
            dps = {}
            if result and "result" in result:
                for item in result["result"]:
                    # Cloud returns code names, we need to map to DPS IDs
                    code = item.get("code")
                    value = item.get("value")
                    dps_id = self._code_to_dps(code)
                    if dps_id:
                        dps[dps_id] = value
            return dps

    def _code_to_dps(self, code: str) -> str | None:
        """Map Tuya cloud code names to DPS IDs."""
        mapping = {
            "switch": DPS_POWER,
            "temp_current": DPS_CURRENT_TEMP,
            "shake": DPS_OSCILLATION,
            "light": DPS_DISPLAY,
            "temp_set_f": DPS_TARGET_TEMP,
        }
        return mapping.get(code)

    def _dps_to_code(self, dps_id: str) -> str | None:
        """Map DPS IDs to Tuya cloud code names."""
        mapping = {
            DPS_POWER: "switch",
            DPS_CURRENT_TEMP: "temp_current",
            DPS_OSCILLATION: "shake",
            DPS_DISPLAY: "light",
            DPS_TARGET_TEMP: "temp_set_f",
        }
        return mapping.get(dps_id)

    def get_current_temp(self) -> int:
        """Get current room temperature in °F."""
        return self._get_value(DPS_CURRENT_TEMP)

    def get_target_temp(self) -> int:
        """Get target temperature setpoint in °F."""
        return self._get_value(DPS_TARGET_TEMP)

    def set_target_temp(self, temp_f: int) -> dict:
        """Set target temperature in °F (typical range: 41-95)."""
        return self._set_value(DPS_TARGET_TEMP, temp_f)

    def is_on(self) -> bool:
        """Check if heater is powered on."""
        return self._get_value(DPS_POWER) or False

    def set_power(self, on: bool) -> dict:
        """Turn heater on or off."""
        return self._set_value(DPS_POWER, on)

    def turn_on(self) -> dict:
        """Turn heater on."""
        return self.set_power(True)

    def turn_off(self) -> dict:
        """Turn heater off."""
        return self.set_power(False)

    def get_heat_mode(self) -> str:
        """Get current heat mode (Low/Medium/High)."""
        return self._get_value(DPS_HEAT_MODE)

    def set_heat_mode(self, mode: str) -> dict:
        """Set heat mode: 'Low', 'Medium', or 'High'."""
        if mode not in HEAT_MODES:
            raise ValueError(f"Invalid mode. Must be one of: {HEAT_MODES}")
        return self._set_value(DPS_HEAT_MODE, mode)

    def get_oscillation(self) -> bool:
        """Check if oscillation is enabled."""
        return self._get_value(DPS_OSCILLATION) or False

    def set_oscillation(self, on: bool) -> dict:
        """Enable or disable oscillation."""
        return self._set_value(DPS_OSCILLATION, on)

    def get_display(self) -> bool:
        """Check if display/LED is on (False = night mode)."""
        return self._get_value(DPS_DISPLAY) or True

    def set_display(self, on: bool) -> dict:
        """Enable or disable display/LED (False = night mode)."""
        return self._set_value(DPS_DISPLAY, on)

    def get_person_detection(self) -> bool:
        """Check if person detection (ClimaSense) is enabled.

        Note: Conflicts with oscillation - enabling one disables the other.
        """
        return self._get_value(DPS_PERSON_DETECTION) or False

    def set_person_detection(self, on: bool) -> dict:
        """Enable or disable person detection (ClimaSense).

        Note: Conflicts with oscillation - enabling this will disable oscillation.
        """
        return self._set_value(DPS_PERSON_DETECTION, on)

    def get_auto_on(self) -> bool:
        """Check if auto-on is enabled (turn on when person detected)."""
        return self._get_value(DPS_AUTO_ON) or False

    def set_auto_on(self, on: bool) -> dict:
        """Enable or disable auto-on (turn on when person detected)."""
        return self._set_value(DPS_AUTO_ON, on)

    def get_detection_timeout(self) -> str:
        """Get person detection timeout setting (5min/15min/30min)."""
        return self._get_value(DPS_DETECTION_TIMEOUT)

    def set_detection_timeout(self, timeout: str) -> dict:
        """Set person detection timeout: '5min', '15min', or '30min'."""
        if timeout not in DETECTION_TIMEOUTS:
            raise ValueError(f"Invalid timeout. Must be one of: {DETECTION_TIMEOUTS}")
        return self._set_value(DPS_DETECTION_TIMEOUT, timeout)

    def get_energy_kwh(self) -> int:
        """Get cumulative energy usage in kWh."""
        return self._get_value(DPS_ENERGY_KWH)

    def get_timer_remaining(self) -> int | None:
        """Get seconds remaining on timer, or None if no timer active.

        The raw DPS 105 value is: base_value + seconds_remaining.
        Returns None when at base value (no timer).
        """
        raw = self._get_value(DPS_TIMER_VALUE) or TIMER_BASE_VALUE
        remaining = raw - TIMER_BASE_VALUE
        return remaining if remaining > 0 else None

    def is_timer_active(self) -> bool:
        """Check if a timer is currently running."""
        return self.get_timer_remaining() is not None

    def get_fault_code(self) -> int:
        """Get fault code (0 = no fault, 16 = tip-over)."""
        return self._get_value(DPS_FAULT) or 0

    def is_tipped_over(self) -> bool:
        """Check if tip-over fault is active (heater knocked over)."""
        return (self.get_fault_code() & FAULT_TIP_OVER) != 0

    def has_fault(self) -> bool:
        """Check if any fault is active that requires physical intervention."""
        return self.get_fault_code() != FAULT_NONE

    def needs_wifi_reset(self) -> bool:
        """Check if heater needs WiFi button pressed to fully clear fault."""
        return self.get_fault_code() == FAULT_PARTIAL_CLEAR

    def get_active_heat_level(self) -> str:
        """Get actual operating heat level (may differ from setting when at temp)."""
        return self._get_value(DPS_ACTIVE_HEAT_LEVEL)

    def get_power_watts(self) -> int:
        """Get estimated current power draw in watts based on active heat level."""
        level = self.get_active_heat_level()
        return WATTAGE_BY_LEVEL.get(level, 0)

    def summary(self) -> dict:
        """Get a human-readable summary of heater state."""
        dps = self.get_status()
        active_level = dps.get(DPS_ACTIVE_HEAT_LEVEL)
        timer_raw = dps.get(DPS_TIMER_VALUE) or TIMER_BASE_VALUE
        timer_remaining = timer_raw - TIMER_BASE_VALUE
        return {
            "mode": self.mode,
            "power": dps.get(DPS_POWER),
            "current_temp_f": dps.get(DPS_CURRENT_TEMP),
            "target_temp_f": dps.get(DPS_TARGET_TEMP),
            "heat_mode": dps.get(DPS_HEAT_MODE),
            "active_heat_level": active_level,
            "power_watts": WATTAGE_BY_LEVEL.get(active_level, 0),
            "oscillation": dps.get(DPS_OSCILLATION),
            "display": dps.get(DPS_DISPLAY),
            "person_detection": dps.get(DPS_PERSON_DETECTION),
            "auto_on": dps.get(DPS_AUTO_ON),
            "detection_timeout": dps.get(DPS_DETECTION_TIMEOUT),
            "timer_remaining_sec": timer_remaining if timer_remaining > 0 else None,
            "energy_kwh": dps.get(DPS_ENERGY_KWH),
            "fault_code": dps.get(DPS_FAULT),
            "raw_dps": dps
        }


if __name__ == "__main__":
    import json
    import sys

    # Allow mode to be passed as argument
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"

    heater = Heater(mode=mode)
    print(f"Heater Status (mode: {heater.mode}):")
    print(json.dumps(heater.summary(), indent=2))
