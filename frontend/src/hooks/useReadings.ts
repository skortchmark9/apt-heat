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

  // Check staleness - either no recent readings OR data hasn't changed (cached cloud data)
  const STALE_THRESHOLD_MS = 5 * 60 * 1000;
  const MIN_READINGS_FOR_STALE_CHECK = 10;

  let isStale = false;
  let lastChangedTimestamp = latestTimestamp;

  if (latestTimestamp) {
    const timeSinceLastReading = Date.now() - new Date(latestTimestamp).getTime();
    if (timeSinceLastReading > STALE_THRESHOLD_MS) {
      // No new readings for 5+ minutes
      isStale = true;
    } else if (readings.length >= MIN_READINGS_FOR_STALE_CHECK) {
      // Check if readings have been identical (cloud returning cached data)
      const recentReadings = readings.slice(-MIN_READINGS_FOR_STALE_CHECK);
      const temps = new Set(recentReadings.map(r => r.current_temp_f));
      const targets = new Set(recentReadings.map(r => r.target_temp_f));
      const powers = new Set(recentReadings.map(r => r.power));

      // If all readings are identical, data is stale/cached
      if (temps.size === 1 && targets.size === 1 && powers.size === 1) {
        // Find when data last changed
        for (let i = readings.length - 1; i > 0; i--) {
          const curr = readings[i];
          const prev = readings[i - 1];
          if (curr.current_temp_f !== prev.current_temp_f ||
              curr.target_temp_f !== prev.target_temp_f ||
              curr.power !== prev.power) {
            lastChangedTimestamp = curr.timestamp;
            break;
          }
        }
        // If data hasn't changed for 5+ minutes, it's stale
        if (lastChangedTimestamp) {
          const timeSinceChange = Date.now() - new Date(lastChangedTimestamp).getTime();
          isStale = timeSinceChange > STALE_THRESHOLD_MS;
        }
      }
    }
  }

  return {
    readings,
    latestOutdoorTemp,
    latestTimestamp: isStale ? lastChangedTimestamp : latestTimestamp,
    isStale,
    loading,
    error,
    refresh: fetchReadings,
  };
}
