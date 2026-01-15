import { useState, useEffect, useCallback, useRef } from 'react';
import type { HeaterStatus, SleepSchedule, SavingsData } from '../types';

const POLL_INTERVAL = 30000; // 30 seconds

// Pending targets for optimistic UI updates
interface PendingTargets {
  temp?: number;
  power?: boolean;
  oscillation?: boolean;
}

export function useHeaterStatus() {
  const [status, setStatus] = useState<HeaterStatus | null>(null);
  const [sleepSchedule, setSleepSchedule] = useState<SleepSchedule | null>(null);
  const [savings, setSavings] = useState<SavingsData | null>(null);
  const [monthlySavings, setMonthlySavings] = useState<SavingsData | null>(null);
  const [streak, setStreak] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingTargets>({});
  const pendingRef = useRef<PendingTargets>({});

  // Clear pending when server confirms the value matches
  const clearPendingIfMatched = (serverStatus: HeaterStatus) => {
    const newPending = { ...pendingRef.current };
    if (newPending.temp !== undefined && serverStatus.target_temp_f === newPending.temp) {
      delete newPending.temp;
    }
    if (newPending.power !== undefined && serverStatus.target_power === newPending.power) {
      delete newPending.power;
    }
    if (newPending.oscillation !== undefined && serverStatus.oscillation === newPending.oscillation) {
      delete newPending.oscillation;
    }
    pendingRef.current = newPending;
    setPending(newPending);
  };

  const fetchStatus = useCallback(async () => {
    try {
      const [statusRes, sleepRes, savingsRes, monthlyRes, historyRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/sleep'),
        fetch('/api/savings?hours=24'),
        fetch('/api/savings?hours=720'),
        fetch('/api/stats/history?days=30'),
      ]);

      if (statusRes.ok) {
        const newStatus = await statusRes.json();
        setStatus(newStatus);
        clearPendingIfMatched(newStatus);
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
      if (historyRes.ok) {
        const history = await historyRes.json();
        setStreak(history.streak ?? 0);
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

  const setTargetTemp = (temp: number) => {
    const clampedTemp = Math.max(41, Math.min(95, temp));
    // Optimistic update
    pendingRef.current = { ...pendingRef.current, temp: clampedTemp };
    setPending({ ...pendingRef.current });
    // Fire and forget
    fetch('/api/target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ temp: clampedTemp }),
    }).catch(e => console.error('Failed to set target temp:', e));
  };

  const togglePower = () => {
    const newPower = !(pending.power ?? status?.power ?? false);
    // Optimistic update
    pendingRef.current = { ...pendingRef.current, power: newPower };
    setPending({ ...pendingRef.current });
    // Fire and forget
    fetch('/api/power/toggle', { method: 'POST' })
      .catch(e => console.error('Failed to toggle power:', e));
  };

  const toggleOscillation = () => {
    const newOsc = !(pending.oscillation ?? status?.oscillation ?? false);
    // Optimistic update
    pendingRef.current = { ...pendingRef.current, oscillation: newOsc };
    setPending({ ...pendingRef.current });
    // Fire and forget
    fetch('/api/oscillation/toggle', { method: 'POST' })
      .catch(e => console.error('Failed to toggle oscillation:', e));
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

  // Effective values (pending overrides server values)
  const effectiveTargetTemp = pending.temp ?? status?.target_temp_f ?? 72;
  const effectivePower = pending.power ?? status?.power ?? false;
  const effectiveOscillation = pending.oscillation ?? status?.oscillation ?? false;

  return {
    status,
    sleepSchedule,
    savings,
    monthlySavings,
    streak,
    loading,
    error,
    pending,
    effectiveTargetTemp,
    effectivePower,
    effectiveOscillation,
    refresh: fetchStatus,
    setTargetTemp,
    togglePower,
    toggleOscillation,
    startSleepMode,
    cancelSleepMode,
  };
}
