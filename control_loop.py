"""
Peak shaving heater control loop.

Time-of-use electric rate schedule:
  - Off-peak: midnight to 8am (cheap power)
  - Peak: 8am to midnight (expensive power)

Strategy:
  - During off-peak: Pre-heat to higher setpoint
  - During peak: Let temp drift to lower setpoint, use battery power
  - Heater uses ~1500W when heating (3.6kWh battery = ~2.4 hours heating)

Future: Integrate with EcoFlow DELTA Pro battery SOC.
"""

import time
import signal
import sys
from datetime import datetime
from heater import Heater

# Configuration
OFF_PEAK_TEMP_F = 72  # Pre-heat during cheap hours
PEAK_TEMP_F = 68      # Allow drift during expensive hours
POLL_INTERVAL_SEC = 60

# Time-of-use schedule (24-hour format)
OFF_PEAK_START = 0   # midnight
OFF_PEAK_END = 8     # 8am

# Global for clean shutdown
running = True


def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


def is_off_peak() -> bool:
    """Check if current time is in off-peak period."""
    hour = datetime.now().hour
    return OFF_PEAK_START <= hour < OFF_PEAK_END


def get_target_temp() -> int:
    """Get target temperature based on time-of-use period."""
    if is_off_peak():
        return OFF_PEAK_TEMP_F
    return PEAK_TEMP_F


def get_period_name() -> str:
    """Get human-readable period name."""
    return "OFF-PEAK" if is_off_peak() else "PEAK"


def main():
    signal.signal(signal.SIGINT, signal_handler)

    # Parse mode from args
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"
    heater = Heater(mode=mode)

    log(f"Starting peak-shaving control loop (mode: {heater.mode})")
    log(f"Off-peak ({OFF_PEAK_START}:00-{OFF_PEAK_END}:00): {OFF_PEAK_TEMP_F}°F")
    log(f"Peak ({OFF_PEAK_END}:00-{OFF_PEAK_START}:00): {PEAK_TEMP_F}°F")

    # Initial setup
    heater.turn_on()
    time.sleep(0.5)
    heater.set_person_detection(False)  # Disable auto-shutoff
    time.sleep(0.5)

    last_target = None

    # Main loop
    while running:
        try:
            period = get_period_name()
            target = get_target_temp()

            # Update setpoint if period changed
            if target != last_target:
                log(f"Period: {period} -> Setting target to {target}°F")
                heater.set_target_temp(target)
                last_target = target
                time.sleep(0.5)

            # Get current status
            status = heater.summary()
            current = status["current_temp_f"]
            power = status["power"]
            heat_mode = status.get("heat_mode", "?")
            active = status.get("active_heat_level", "?")
            watts = status.get("power_watts", 0)

            # Calculate delta from target
            delta = current - target
            if delta > 0:
                state = f"+{delta}°F"
            elif delta < 0:
                state = f"{delta}°F"
            else:
                state = "at target"

            log(f"[{period}] Room: {current}°F ({state}) | "
                f"Target: {target}°F | "
                f"Heater: {'ON' if power else 'OFF'} {active} ({watts}W)")

            time.sleep(POLL_INTERVAL_SEC)

        except Exception as e:
            log(f"Error: {e}")
            time.sleep(5)

    # Clean shutdown
    log("Control loop stopped")
    print(heater.summary())


if __name__ == "__main__":
    main()
