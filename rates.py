"""
ConEd Time-of-Use rate calculations for peak shaving savings.

Based on ConEd SC1 Rate III (Time of Use) tariff.
Source: ratemate project rate_calculator module.
"""

from datetime import datetime, date
from typing import Tuple

# =============================================================================
# CONED TOU RATES ($/kWh)
# Last updated: 2024
# =============================================================================

TOU_SUMMER_PEAK_RATE = 0.3523      # Summer peak (Jun-Sep, 8AM-midnight)
TOU_SUMMER_OFFPEAK_RATE = 0.0249   # Summer off-peak
TOU_WINTER_PEAK_RATE = 0.1305      # Winter peak (Oct-May, 8AM-midnight)
TOU_WINTER_OFFPEAK_RATE = 0.0249   # Winter off-peak

# Super-peak: Summer weekday 2PM-6PM - even higher, but we use peak rate as baseline
TOU_SUMMER_SUPERPEAK_RATE = 0.3523  # Same as peak for supply component


# =============================================================================
# SEASON & PERIOD HELPERS
# =============================================================================

def is_summer(dt: datetime) -> bool:
    """Summer season is June through September."""
    return 6 <= dt.month <= 9


def is_weekday(dt: datetime) -> bool:
    """Monday=0 through Friday=4 are weekdays."""
    return dt.weekday() < 5


def get_tou_period(dt: datetime) -> str:
    """
    Determine TOU period for a given datetime.

    Peak: 8AM-midnight (hours 8-23)
    Off-Peak: midnight-8AM (hours 0-7)
    Super-Peak: Summer weekday 2PM-6PM (hours 14-17)
    """
    hour = dt.hour

    # Super-peak check (summer weekday 2-6PM)
    if is_summer(dt) and is_weekday(dt) and 14 <= hour < 18:
        return "super_peak"

    # Standard peak/off-peak
    if hour < 8:
        return "off_peak"
    return "peak"


def get_rate_for_period(dt: datetime) -> Tuple[str, float]:
    """
    Get the rate name and $/kWh for a given datetime.

    Returns:
        Tuple of (period_name, rate_per_kwh)
    """
    period = get_tou_period(dt)
    summer = is_summer(dt)

    if period == "off_peak":
        rate = TOU_SUMMER_OFFPEAK_RATE if summer else TOU_WINTER_OFFPEAK_RATE
        return ("off_peak", rate)
    elif period == "super_peak":
        return ("super_peak", TOU_SUMMER_SUPERPEAK_RATE)
    else:  # peak
        rate = TOU_SUMMER_PEAK_RATE if summer else TOU_WINTER_PEAK_RATE
        return ("peak", rate)


# =============================================================================
# SAVINGS CALCULATIONS
# =============================================================================

def calculate_savings(kwh_during_peak: float, dt: datetime = None) -> float:
    """
    Calculate savings from running on battery during peak hours.

    Savings = kWh × (peak_rate - off_peak_rate)

    Args:
        kwh_during_peak: Energy used during peak hours (kWh)
        dt: Optional datetime to determine season (defaults to now)

    Returns:
        Dollar amount saved
    """
    if dt is None:
        dt = datetime.now()

    summer = is_summer(dt)

    if summer:
        peak_rate = TOU_SUMMER_PEAK_RATE
        offpeak_rate = TOU_SUMMER_OFFPEAK_RATE
    else:
        peak_rate = TOU_WINTER_PEAK_RATE
        offpeak_rate = TOU_WINTER_OFFPEAK_RATE

    return kwh_during_peak * (peak_rate - offpeak_rate)


def calculate_savings_from_readings(readings: list, poll_interval_sec: int = 5) -> dict:
    """
    Calculate savings from a list of heater readings.

    Args:
        readings: List of HeaterReading objects with timestamp, power_watts
        poll_interval_sec: Seconds between readings (for energy calculation)

    Returns:
        Dict with savings breakdown:
        {
            'total_kwh': float,
            'peak_kwh': float,
            'offpeak_kwh': float,
            'savings': float,
            'would_have_cost': float,
            'actual_cost': float
        }
    """
    peak_wh = 0.0
    offpeak_wh = 0.0
    total_wh = 0.0

    peak_cost = 0.0
    offpeak_cost = 0.0

    for reading in readings:
        if not reading.power_watts or reading.power_watts <= 0:
            continue

        # Energy for this interval (watt-hours)
        wh = reading.power_watts * (poll_interval_sec / 3600)
        total_wh += wh

        # Get period and rate for this reading's timestamp
        period, rate = get_rate_for_period(reading.timestamp)

        if period == "off_peak":
            offpeak_wh += wh
            offpeak_cost += (wh / 1000) * rate
        else:  # peak or super_peak
            peak_wh += wh
            peak_cost += (wh / 1000) * rate

    # Convert to kWh
    total_kwh = total_wh / 1000
    peak_kwh = peak_wh / 1000
    offpeak_kwh = offpeak_wh / 1000

    # What it would have cost on grid during peak
    would_have_cost = peak_cost + offpeak_cost

    # What it actually cost (assuming battery charged during off-peak)
    # All energy effectively charged at off-peak rate
    summer = is_summer(datetime.now())
    offpeak_rate = TOU_SUMMER_OFFPEAK_RATE if summer else TOU_WINTER_OFFPEAK_RATE
    actual_cost = total_kwh * offpeak_rate

    # Savings
    savings = would_have_cost - actual_cost

    return {
        'total_kwh': round(total_kwh, 2),
        'peak_kwh': round(peak_kwh, 2),
        'offpeak_kwh': round(offpeak_kwh, 2),
        'savings': round(savings, 2),
        'would_have_cost': round(would_have_cost, 2),
        'actual_cost': round(actual_cost, 2)
    }
