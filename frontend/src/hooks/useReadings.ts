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

  // Get latest outdoor temp from readings
  const latestOutdoorTemp = readings.length > 0
    ? readings[readings.length - 1].outdoor_temp_f
    : null;

  return {
    readings,
    latestOutdoorTemp,
    loading,
    error,
    refresh: fetchReadings,
  };
}
