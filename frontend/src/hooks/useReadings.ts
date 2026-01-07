import { useState, useEffect, useCallback } from 'react';
import type { HeaterReading } from '../types';

const POLL_INTERVAL = 60000; // 1 minute

export function useReadings(hours: number = 24) {
  const [readings, setReadings] = useState<HeaterReading[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReadings = useCallback(async () => {
    try {
      const res = await fetch(`/api/readings?hours=${hours}`);
      if (res.ok) {
        setReadings(await res.json());
        setError(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch readings');
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => {
    fetchReadings();
    const interval = setInterval(fetchReadings, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchReadings]);

  // Get latest reading info
  const latestReading = readings.length > 0 ? readings[readings.length - 1] : null;
  const latestOutdoorTemp = latestReading?.outdoor_temp_f ?? null;
  const latestTimestamp = latestReading?.timestamp ?? null;

  // Check staleness (> 5 minutes old)
  const STALE_THRESHOLD_MS = 5 * 60 * 1000;
  const isStale = latestTimestamp
    ? Date.now() - new Date(latestTimestamp).getTime() > STALE_THRESHOLD_MS
    : false;

  return {
    readings,
    latestOutdoorTemp,
    latestTimestamp,
    isStale,
    loading,
    error,
    refresh: fetchReadings,
  };
}
