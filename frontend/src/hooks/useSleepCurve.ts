import { useState, useCallback } from 'react';
import type { CurvePoint, StoredCurvePoint } from '../types';

const STORAGE_KEY_CURVE = 'sleepCurve';
const STORAGE_KEY_WAKE_TIME = 'sleepWakeTime';
const DEFAULT_WAKE_TIME = '7:00 AM';

// Generate wake time options (5:00 AM - 11:30 AM)
export const WAKE_TIME_OPTIONS: string[] = [];
for (let h = 5; h <= 11; h++) {
  WAKE_TIME_OPTIONS.push(`${h}:00 AM`);
  WAKE_TIME_OPTIONS.push(`${h}:30 AM`);
}

export function useSleepCurve(currentSetpoint: number) {
  const [selectedWakeTime, setSelectedWakeTime] = useState<string>(() => {
    return localStorage.getItem(STORAGE_KEY_WAKE_TIME) || DEFAULT_WAKE_TIME;
  });

  const [curvePoints, setCurvePoints] = useState<CurvePoint[]>([]);

  // Convert delta to Y position (for canvas)
  const deltaToY = useCallback((delta: number, canvasHeight: number) => {
    return ((5 - delta) / 10) * canvasHeight;
  }, []);

  // Convert Y position to delta
  const yToDelta = useCallback((y: number, canvasHeight: number) => {
    return 5 - (y / canvasHeight) * 10;
  }, []);

  // Initialize curve from localStorage or defaults
  const initializeCurve = useCallback((canvasWidth: number, canvasHeight: number) => {
    const saved = localStorage.getItem(STORAGE_KEY_CURVE);

    if (saved) {
      try {
        const normalized: StoredCurvePoint[] = JSON.parse(saved);
        if (normalized[0]?.delta !== undefined) {
          setCurvePoints(normalized.map(p => ({
            x: p.progress * canvasWidth,
            y: deltaToY(p.delta, canvasHeight),
          })));
          return;
        }
      } catch {
        // Fall through to defaults
      }
    }

    // Default bathtub curve
    setCurvePoints([
      { x: 0, y: deltaToY(0, canvasHeight) },
      { x: canvasWidth * 0.12, y: deltaToY(-2.5, canvasHeight) },
      { x: canvasWidth * 0.25, y: deltaToY(-5, canvasHeight) },
      { x: canvasWidth * 0.5, y: deltaToY(-5, canvasHeight) },
      { x: canvasWidth * 0.75, y: deltaToY(-5, canvasHeight) },
      { x: canvasWidth * 0.88, y: deltaToY(-2.5, canvasHeight) },
      { x: canvasWidth, y: deltaToY(0, canvasHeight) },
    ]);
  }, [deltaToY]);

  // Save settings to localStorage
  const saveSettings = useCallback((points: CurvePoint[], canvasWidth: number, canvasHeight: number) => {
    const normalized: StoredCurvePoint[] = points.map(p => ({
      progress: p.x / canvasWidth,
      delta: yToDelta(p.y, canvasHeight),
    }));
    localStorage.setItem(STORAGE_KEY_CURVE, JSON.stringify(normalized));
    localStorage.setItem(STORAGE_KEY_WAKE_TIME, selectedWakeTime);
  }, [selectedWakeTime, yToDelta]);

  // Update wake time
  const updateWakeTime = useCallback((time: string) => {
    setSelectedWakeTime(time);
    localStorage.setItem(STORAGE_KEY_WAKE_TIME, time);
  }, []);

  // Update a curve point
  const updatePoint = useCallback((index: number, y: number, canvasHeight: number) => {
    setCurvePoints(prev => {
      const newPoints = [...prev];
      newPoints[index] = { ...newPoints[index], y: Math.max(10, Math.min(canvasHeight - 10, y)) };
      return newPoints;
    });
  }, []);

  // Get curve stats
  const getCurveStats = useCallback((canvasHeight: number) => {
    if (curvePoints.length === 0) return { start: 0, min: 0, wake: 0 };

    const deltas = curvePoints.map(p => yToDelta(p.y, canvasHeight));
    const temps = deltas.map(d => Math.round(currentSetpoint + d));

    return {
      start: temps[0],
      min: Math.min(...temps),
      wake: temps[temps.length - 1],
    };
  }, [curvePoints, currentSetpoint, yToDelta]);

  // Convert to API format
  const toApiCurve = useCallback((canvasWidth: number, canvasHeight: number) => {
    return curvePoints.map(p => ({
      progress: p.x / canvasWidth,
      temp: Math.round(currentSetpoint + yToDelta(p.y, canvasHeight)),
    }));
  }, [curvePoints, currentSetpoint, yToDelta]);

  // Parse wake time to Date
  const getWakeDate = useCallback(() => {
    const now = new Date();
    const [timePart, ampm] = selectedWakeTime.split(' ');
    const [hours, mins] = timePart.split(':').map(Number);
    let wakeHour = hours;
    if (ampm === 'PM' && hours !== 12) wakeHour += 12;
    if (ampm === 'AM' && hours === 12) wakeHour = 0;

    const wake = new Date(now);
    wake.setHours(wakeHour, mins, 0, 0);
    if (wake <= now) wake.setDate(wake.getDate() + 1);
    return wake;
  }, [selectedWakeTime]);

  return {
    selectedWakeTime,
    curvePoints,
    setCurvePoints,
    initializeCurve,
    saveSettings,
    updateWakeTime,
    updatePoint,
    getCurveStats,
    toApiCurve,
    getWakeDate,
    deltaToY,
    yToDelta,
  };
}
