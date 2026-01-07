// API Response Types

export interface HeaterStatus {
  power: boolean;
  current_temp_f: number | null;
  target_temp_f: number | null;
  heat_mode: string | null;
  active_heat_level: number | null;
  power_watts: number | null;
  oscillation: boolean;
  display: boolean;
  person_detection: boolean;
  auto_on: boolean;
  detection_timeout: number | null;
  timer_remaining_sec: number | null;
  energy_kwh: number | null;
  fault_code: number | null;
}

export interface HeaterReading {
  timestamp: string;
  power: boolean;
  current_temp_f: number | null;
  target_temp_f: number | null;
  heat_mode: string | null;
  active_heat_level: number | null;
  power_watts: number | null;
  oscillation: boolean;
  display: boolean;
  person_detection: boolean;
  auto_on: boolean;
  detection_timeout: number | null;
  timer_remaining_sec: number | null;
  energy_kwh: number | null;
  fault_code: number | null;
  outdoor_temp_f: number | null;
}

export interface SleepCurvePoint {
  progress: number;
  temp: number;
}

export interface SleepSchedule {
  active: boolean;
  wake_time?: string;
  start_time?: string;
  current_target?: number;
  progress?: number;
  curve?: SleepCurvePoint[];
}

export interface SavingsData {
  hours: number;
  total_kwh: number;
  peak_kwh: number;
  offpeak_kwh: number;
  savings: number;
  would_have_cost: number;
  actual_cost: number;
  current_period: string;
  current_rate: number;
}

// UI State Types

export interface CurvePoint {
  x: number;
  y: number;
}

export interface StoredCurvePoint {
  progress: number;
  delta: number;
}

export type HeaterState = 'heating' | 'idle' | 'off';

export interface BatteryStatus {
  configured: boolean;
  error?: string;
  soc?: number;
  watts_in?: number;
  watts_out?: number;
  charging?: boolean;
  discharging?: boolean;
  charge_limit?: number;
  tou_period?: string;
  charge_state?: string;
  automation_enabled?: boolean;
}
