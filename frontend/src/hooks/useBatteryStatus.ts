import { useState, useEffect, useCallback } from 'react';
import type { BatteryStatus } from '../types';

const POLL_INTERVAL = 30000; // 30 seconds

export function useBatteryStatus() {
  const [status, setStatus] = useState<BatteryStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/battery');
      if (res.ok) {
        setStatus(await res.json());
        setError(null);
      } else {
        setError('Failed to fetch battery status');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch battery status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return {
    status,
    loading,
    error,
    refresh: fetchStatus,
  };
}
