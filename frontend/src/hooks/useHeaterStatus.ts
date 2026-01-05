import { useState, useEffect, useCallback } from 'react';
import type { HeaterStatus, SleepSchedule, SavingsData } from '../types';

const POLL_INTERVAL = 30000; // 30 seconds

export function useHeaterStatus() {
  const [status, setStatus] = useState<HeaterStatus | null>(null);
  const [sleepSchedule, setSleepSchedule] = useState<SleepSchedule | null>(null);
  const [savings, setSavings] = useState<SavingsData | null>(null);
  const [monthlySavings, setMonthlySavings] = useState<SavingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const [statusRes, sleepRes, savingsRes, monthlyRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/sleep'),
        fetch('/api/savings?hours=24'),
        fetch('/api/savings?hours=720'),
      ]);

      if (statusRes.ok) {
        setStatus(await statusRes.json());
      }
      if (sleepRes.ok) {
        setSleepSchedule(await sleepRes.json());
      }
      if (savingsRes.ok) {
        setSavings(await savingsRes.json());
      }
      if (monthlyRes.ok) {
        setMonthlySavings(await monthlyRes.json());
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const setTargetTemp = async (temp: number) => {
    const clampedTemp = Math.max(41, Math.min(95, temp));
    try {
      await fetch('/api/target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temp: clampedTemp }),
      });
      await fetchStatus();
    } catch (e) {
      console.error('Failed to set target temp:', e);
    }
  };

  const togglePower = async () => {
    try {
      await fetch('/api/power/toggle', { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('Failed to toggle power:', e);
    }
  };

  const toggleOscillation = async () => {
    try {
      await fetch('/api/oscillation/toggle', { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('Failed to toggle oscillation:', e);
    }
  };

  const startSleepMode = async (wakeTime: string, curve: { progress: number; temp: number }[]) => {
    try {
      const res = await fetch('/api/sleep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wakeTime, curve }),
      });
      if (res.ok) {
        await fetchStatus();
        return true;
      }
      return false;
    } catch (e) {
      console.error('Failed to start sleep mode:', e);
      return false;
    }
  };

  const cancelSleepMode = async () => {
    try {
      await fetch('/api/sleep/cancel', { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('Failed to cancel sleep mode:', e);
    }
  };

  return {
    status,
    sleepSchedule,
    savings,
    monthlySavings,
    loading,
    error,
    refresh: fetchStatus,
    setTargetTemp,
    togglePower,
    toggleOscillation,
    startSleepMode,
    cancelSleepMode,
  };
}
