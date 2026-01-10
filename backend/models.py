"""Database models for heater monitoring."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AppSettings(Base):
    """App settings (only one row, id=1)."""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)
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
