#!/usr/bin/env python3
"""
Local device driver for apt_heat.

Polls heater, plug, and battery at regular intervals and pushes telemetry
to the remote server. Receives target setpoints from server and applies them.

Usage:
    python driver/main.py [--period 1.0] [--server-url http://localhost:8000]
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add driver dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from heater import Heater
from tapo_plug import TapoPlug
from ecoflow import EcoFlowBattery


def now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class Channel:
    """A single telemetry channel with value and timestamp."""

    def __init__(self, value=None):
        self.value = value
        self.last_updated = now_iso() if value is not None else None

    def update(self, value):
        """Update value and timestamp."""
        self.value = value
        self.last_updated = now_iso()

    def to_dict(self) -> dict:
        return {
            'value': self.value,
            'last_updated': self.last_updated,
        }


class Slate:
    """Collection of telemetry channels."""

    def __init__(self):
        self._channels: dict[str, Channel] = {}

    def set(self, name: str, value):
        """Update a channel's value and timestamp."""
        if name not in self._channels:
            self._channels[name] = Channel()
        self._channels[name].update(value)

    def get(self, name: str):
        """Get a channel's current value."""
        if name in self._channels:
            return self._channels[name].value
        return None

    def to_dict(self) -> dict:
        """Export all channels as dict."""
        return {name: ch.to_dict() for name, ch in self._channels.items()}

    def __repr__(self):
        return f"Slate({list(self._channels.keys())})"


RECONNECT_INTERVAL = 30  # Retry failed device init every N cycles


class Driver:
    """Main driver that polls devices and syncs with server."""

    def __init__(self, server_url: str, period: float):
        self.server_url = server_url.rstrip('/')
        self.period = period
        self.slate = Slate()
        self.cycle = 0

        # Track last-set values to avoid redundant commands
        self._last_set = {}

        # Track consecutive failures per device for backoff
        self._failures = {'heater': 0, 'plug': 0, 'battery': 0}

        # Initialize devices (non-blocking — failures are OK)
        self.heater = None
        self.plug = None
        self.battery = None
        self._init_devices()

    def _init_devices(self):
        """Try to initialize any missing devices."""
        if self.heater is None:
            try:
                self.heater = Heater(mode='local')
                self._failures['heater'] = 0
                print(f"  Heater: OK (mode={self.heater.mode})")
            except Exception as e:
                print(f"  Heater: FAILED ({e})")

        if self.plug is None:
            try:
                self.plug = TapoPlug(mode='local')
                self._failures['plug'] = 0
                print(f"  Plug: OK (mode={self.plug.mode})")
            except Exception as e:
                print(f"  Plug: FAILED ({e})")

        if self.battery is None:
            try:
                self.battery = EcoFlowBattery()
                self._failures['battery'] = 0
                print(f"  Battery: OK")
            except Exception as e:
                print(f"  Battery: FAILED ({e})")

    def update_heater(self):
        """Read heater state into slate."""
        if not self.heater:
            return

        try:
            status = self.heater.get_status()
            if not status:
                raise ConnectionError("Empty response from heater")
            self._failures['heater'] = 0
            # Only update slate for DPS keys actually present in the response.
            # tinytuya often returns partial DPS — writing None would cause
            # apply_targets() to re-send commands every cycle.
            dps_map = {
                '1': 'heater_power',
                '3': 'heater_current_temp',
                '5': 'heater_heat_mode',
                '8': 'heater_oscillation',
                '10': 'heater_display',
                '11': 'heater_active_heat_level',
                '14': 'heater_target_temp',
                '101': 'heater_person_detection',
                '102': 'heater_auto_on',
                '103': 'heater_detection_timeout',
                '104': 'heater_dps_104',
                '105': 'heater_timer_value',
                '106': 'heater_energy_kwh',
                '107': 'heater_session_heating',
                '108': 'heater_fault_code',
            }
            for dps_id, channel_name in dps_map.items():
                if dps_id in status:
                    self.slate.set(channel_name, status[dps_id])
        except Exception as e:
            self._failures['heater'] += 1
            if self._failures['heater'] <= 3 or self._failures['heater'] % 10 == 0:
                print(f"  [heater] read error ({self._failures['heater']}x): {e}")
            if self._failures['heater'] >= 5:
                print(f"  [heater] too many failures, will reinit")
                self.heater = None

    def update_plug(self):
        """Read plug state into slate."""
        if not self.plug:
            return

        try:
            status = self.plug.get_full_status()
            if status.get('success'):
                self._failures['plug'] = 0
                # Device state
                self.slate.set('plug_on', status.get('device_on'))
                self.slate.set('plug_on_time', status.get('on_time'))
                # Network
                self.slate.set('plug_rssi', status.get('rssi'))
                self.slate.set('plug_signal_level', status.get('signal_level'))
                # Protection status
                self.slate.set('plug_overcurrent_status', status.get('overcurrent_status'))
                self.slate.set('plug_overheat_status', status.get('overheat_status'))
                self.slate.set('plug_power_protection_status', status.get('power_protection_status'))
                self.slate.set('plug_charging_status', status.get('charging_status'))
                # Energy usage
                self.slate.set('plug_today_energy_wh', status.get('today_energy'))
                self.slate.set('plug_today_runtime_min', status.get('today_runtime'))
                self.slate.set('plug_month_energy_wh', status.get('month_energy'))
                self.slate.set('plug_month_runtime_min', status.get('month_runtime'))
            else:
                raise ConnectionError(status.get('error', 'Unknown plug error'))
        except Exception as e:
            self._failures['plug'] += 1
            if self._failures['plug'] <= 3 or self._failures['plug'] % 10 == 0:
                print(f"  [plug] read error ({self._failures['plug']}x): {e}")
            if self._failures['plug'] >= 5:
                print(f"  [plug] too many failures, will reinit")
                self.plug = None

    def update_battery(self):
        """Read battery state into slate."""
        if not self.battery:
            return

        try:
            status = self.battery.get_status()
            if status:
                # Basic status
                self.slate.set('battery_soc', status.get('soc'))
                self.slate.set('battery_watts_in', status.get('watts_in'))
                self.slate.set('battery_watts_out', status.get('watts_out'))
                self.slate.set('battery_charging', status.get('charging'))
                self.slate.set('battery_discharging', status.get('discharging'))
                self.slate.set('battery_ac_charge_watts', status.get('ac_charge_watts'))
                self.slate.set('battery_min_discharge_soc', status.get('min_discharge_soc'))

                # Extract more from raw if available
                raw = status.get('raw', {})
                if raw:
                    # Temperatures
                    self.slate.set('battery_inv_out_temp', raw.get('inv.outTemp'))
                    self.slate.set('battery_dc_in_temp', raw.get('inv.dcInTemp'))
                    self.slate.set('battery_mppt_temp', raw.get('mppt.mpptTemp'))
                    self.slate.set('battery_bms_temp', raw.get('bmsMaster.temp'))
                    self.slate.set('battery_bms_max_cell_temp', raw.get('bmsMaster.maxCellTemp'))
                    self.slate.set('battery_bms_min_cell_temp', raw.get('bmsMaster.minCellTemp'))
                    # Voltages
                    self.slate.set('battery_bms_vol', raw.get('bmsMaster.vol'))
                    self.slate.set('battery_bms_max_cell_vol', raw.get('bmsMaster.maxCellVol'))
                    self.slate.set('battery_bms_min_cell_vol', raw.get('bmsMaster.minCellVol'))
                    self.slate.set('battery_inv_out_vol', raw.get('inv.invOutVol'))
                    self.slate.set('battery_inv_ac_in_vol', raw.get('inv.acInVol'))
                    # Currents/Power
                    self.slate.set('battery_bms_amp', raw.get('bmsMaster.amp'))
                    self.slate.set('battery_inv_input_watts', raw.get('inv.inputWatts'))
                    self.slate.set('battery_inv_output_watts', raw.get('inv.outputWatts'))
                    self.slate.set('battery_mppt_in_watts', raw.get('mppt.inWatts'))
                    self.slate.set('battery_mppt_out_watts', raw.get('mppt.outWatts'))
                    self.slate.set('battery_pd_chg_power_ac', raw.get('pd.chgPowerAc'))
                    self.slate.set('battery_pd_dsg_power_ac', raw.get('pd.dsgPowerAc'))
                    self.slate.set('battery_pd_chg_power_dc', raw.get('pd.chgPowerDc'))
                    self.slate.set('battery_pd_dsg_power_dc', raw.get('pd.dsgPowerDc'))
                    # Capacity/Health
                    self.slate.set('battery_bms_remain_cap', raw.get('bmsMaster.remainCap'))
                    self.slate.set('battery_bms_full_cap', raw.get('bmsMaster.fullCap'))
                    self.slate.set('battery_bms_design_cap', raw.get('bmsMaster.designCap'))
                    self.slate.set('battery_bms_cycles', raw.get('bmsMaster.cycles'))
                    self.slate.set('battery_bms_soh', raw.get('bmsMaster.soh'))
                    # Time
                    self.slate.set('battery_pd_remain_time', raw.get('pd.remainTime'))
                    self.slate.set('battery_ems_chg_remain_time', raw.get('ems.chgRemainTime'))
                    self.slate.set('battery_ems_dsg_remain_time', raw.get('ems.dsgRemainTime'))
                    # State
                    self.slate.set('battery_ems_chg_state', raw.get('ems.chgState'))
                    self.slate.set('battery_bms_chg_dsg_state', raw.get('bmsMaster.chgDsgState'))
                    self.slate.set('battery_pd_dc_out_state', raw.get('pd.dcOutState'))
                    self.slate.set('battery_inv_fan_state', raw.get('inv.fanState'))
                    # Errors
                    self.slate.set('battery_pd_err_code', raw.get('pd.errCode'))
                    self.slate.set('battery_inv_err_code', raw.get('inv.errCode'))
                    self.slate.set('battery_bms_err_code', raw.get('bmsMaster.errCode'))
                    self.slate.set('battery_mppt_fault_code', raw.get('mppt.faultCode'))
                    # Config
                    self.slate.set('battery_ems_max_charge_soc', raw.get('ems.maxChargeSoc'))
                    self.slate.set('battery_inv_cfg_ac_enabled', raw.get('inv.cfgAcEnabled'))
                    self.slate.set('battery_inv_cfg_slow_chg_watts', raw.get('inv.cfgSlowChgWatts'))
        except Exception as e:
            self._failures['battery'] += 1
            if self._failures['battery'] <= 3 or self._failures['battery'] % 10 == 0:
                print(f"  [battery] read error ({self._failures['battery']}x): {e}")
            if self._failures['battery'] >= 5:
                print(f"  [battery] too many failures, will reinit")
                self.battery = None

    def post_to_server(self) -> dict | None:
        """POST slate to server, return target setpoints."""
        import json
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError

        url = f"{self.server_url}/api/driver/sync"
        payload = json.dumps(self.slate.to_dict()).encode('utf-8')

        try:
            req = Request(url, data=payload, method='POST')
            req.add_header('Content-Type', 'application/json')
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except HTTPError as e:
            print(f"  [server] HTTP {e.code}: {e.reason}")
        except URLError as e:
            print(f"  [server] connection error: {e.reason}")
        except Exception as e:
            print(f"  [server] error: {e}")
        return None

    def _apply_heater_target(self, key: str, target, setter):
        """Apply a single heater target if it differs from current slate value."""
        current = self.slate.get(key)
        # Skip if we've never read this value — avoids blind-setting on startup
        if current is None:
            return
        if target != current:
            setter(target)
            self.slate.set(key, target)  # Update slate to prevent re-sending
            print(f"  [heater] set {key}: {target}")

    def apply_targets(self, targets: dict):
        """Apply target setpoints received from server."""
        if not targets:
            return

        # Check master kill switch
        if not targets.get('driver_control_enabled', True):
            return

        # Heater targets
        if self.heater:
            heater_targets = {
                'heater_target_temp': self.heater.set_target_temp,
                'heater_power': self.heater.set_power,
                'heater_heat_mode': self.heater.set_heat_mode,
                'heater_oscillation': self.heater.set_oscillation,
                'heater_display': self.heater.set_display,
            }
            for key, setter in heater_targets.items():
                if key in targets:
                    try:
                        self._apply_heater_target(key, targets[key], setter)
                    except Exception as e:
                        print(f"  [heater] set {key} error: {e}")

        # Plug targets
        if 'plug_on' in targets and self.plug:
            try:
                target = targets['plug_on']
                current = self.slate.get('plug_on')
                if current is not None and target != current:
                    if target:
                        self.plug.turn_on()
                    else:
                        self.plug.turn_off()
                    self.slate.set('plug_on', target)
                    print(f"  [plug] set on: {target}")
            except Exception as e:
                print(f"  [plug] set error: {e}")

        # Battery targets (charging power)
        if 'battery_charge_power' in targets and self.battery:
            try:
                target = targets['battery_charge_power']
                current = self.slate.get('battery_ac_charge_watts')
                # If we have a current reading, compare to that
                # If no reading yet, use last_set to avoid spamming on startup
                if current is not None:
                    should_set = (target != current)
                else:
                    should_set = (target != self._last_set.get('battery_charge_power'))

                if should_set:
                    result = self.battery.set_ac_charging_power(target)
                    # EcoFlow API returns {'code': '0', 'message': 'Success'} on success
                    if result.get('code') == '0':
                        print(f"  [battery] set charge_power: {target}W")
                        self._last_set['battery_charge_power'] = target
                    else:
                        print(f"  [battery] set charge_power failed: {result.get('message', result)}")
            except Exception as e:
                print(f"  [battery] set error: {e}")

    def run_cycle(self):
        """Run one polling cycle."""
        self.cycle += 1
        cycle_start = time.time()

        # Periodically retry failed device connections
        if self.cycle % RECONNECT_INTERVAL == 0:
            missing = []
            if self.heater is None:
                missing.append('heater')
            if self.plug is None:
                missing.append('plug')
            if self.battery is None:
                missing.append('battery')
            if missing:
                print(f"  [reconnect] retrying: {', '.join(missing)}")
                self._init_devices()

        # Update devices
        self.update_heater()
        self.update_plug()

        # Update battery less frequently (cloud API)
        if self.cycle % 5 == 0:
            self.update_battery()

        # Sync with server
        response = self.post_to_server()
        if response:
            targets = response.get('targets', {})
            self.apply_targets(targets)

        cycle_time = time.time() - cycle_start
        return cycle_time

    def run(self):
        """Main loop."""
        devices = [
            f"heater={'OK' if self.heater else 'MISSING'}",
            f"plug={'OK' if self.plug else 'MISSING'}",
            f"battery={'OK' if self.battery else 'MISSING'}",
        ]
        print(f"\nStarting driver loop (period={self.period}s)")
        print(f"Server: {self.server_url}")
        print(f"Devices: {', '.join(devices)}")
        print(f"Reconnect interval: {RECONNECT_INTERVAL} cycles")
        print("-" * 40)

        while True:
            try:
                cycle_time = self.run_cycle()

                # Sleep for remainder of period
                sleep_time = max(0, self.period - cycle_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                elif cycle_time > self.period:
                    print(f"  [warn] cycle {self.cycle} took {cycle_time:.2f}s (> {self.period}s period)")
                if (self.cycle % 3) == 0:
                    print(f"  [info] cycle {self.cycle} took {cycle_time:.2f}s")

            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except Exception as e:
                print(f"  [error] cycle failed: {e}")
                time.sleep(self.period)


def main():
    parser = argparse.ArgumentParser(description='Local device driver for apt_heat')
    parser.add_argument('--period', type=float, default=1.0,
                        help='Polling period in seconds (default: 1.0)')
    parser.add_argument('--server-url', type=str, default='https://apt-heat-production.up.railway.app',
                        help='Server URL (default: https://apt-heat-production.up.railway.app)')
    args = parser.parse_args()

    driver = Driver(server_url=args.server_url, period=args.period)
    driver.run()


if __name__ == '__main__':
    main()
