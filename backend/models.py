"""Database models for heater monitoring."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AppSettings(Base):
    """App settings (only one row, id=1)."""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)
    driver_control_enabled = Column(Boolean, default=True)  # Master kill switch
    automation_mode = Column(String, default="tou")  # "manual" | "tou"
    user_targets_json = Column(Text)  # JSON blob of user setpoints
    # Legacy columns (kept for migration compatibility)
    battery_automation_enabled = Column(Boolean, default=True)
    heater_automation_enabled = Column(Boolean, default=True)


class SleepSchedule(Base):
    """Active sleep schedule (only one row, id=1)."""

    __tablename__ = "sleep_schedule"

    id = Column(Integer, primary_key=True, default=1)
    start_time = Column(DateTime)
    wake_time = Column(DateTime)
    curve_json = Column(Text)  # JSON array of {progress, temp}


class HeaterReading(Base):
    """Historical heater status readings."""

    __tablename__ = "heater_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Core status
    power = Column(Boolean)
    current_temp_f = Column(Integer)
    target_temp_f = Column(Integer)

    # Heat settings
    heat_mode = Column(String)  # Low/Medium/High
    active_heat_level = Column(String)  # Stop/Low/Medium/High
    power_watts = Column(Integer)

    # Features
    oscillation = Column(Boolean)
    display = Column(Boolean)
    person_detection = Column(Boolean)
    auto_on = Column(Boolean)
    detection_timeout = Column(String)

    # Timer/Energy
    timer_remaining_sec = Column(Integer)
    energy_kwh = Column(Integer)

    # Faults
    fault_code = Column(Integer)

    # Weather
    outdoor_temp_f = Column(Integer)

    # Battery
    battery_soc = Column(Integer)


class DailyStats(Base):
    """Pre-aggregated daily statistics for fast history queries."""

    __tablename__ = "daily_stats"

    date = Column(String, primary_key=True)  # YYYY-MM-DD
    total_wh = Column(Integer, default=0)
    peak_wh = Column(Integer, default=0)
    offpeak_wh = Column(Integer, default=0)
    peak_cost_cents = Column(Integer, default=0)  # Store as cents to avoid float
    offpeak_cost_cents = Column(Integer, default=0)
    reading_count = Column(Integer, default=0)
    temp_sum = Column(Integer, default=0)
    min_temp = Column(Integer)
    max_temp = Column(Integer)
