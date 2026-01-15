import { useState } from 'react';
import { Hero } from './Hero';
import { StatusCarousel } from './StatusCarousel';
import { HomeGrid } from './HomeGrid';
import { TemperatureChart } from './TemperatureChart';
import { StatsRow } from './StatsRow';
import { SleepModal } from './SleepModal';
import { useHeaterStatus } from '../hooks/useHeaterStatus';
import { useReadings } from '../hooks/useReadings';
import { useBatteryStatus } from '../hooks/useBatteryStatus';

export function HomePage() {
  const [chartHours, setChartHours] = useState(24);
  const [showSleepModal, setShowSleepModal] = useState(false);

  // API hooks
  const {
    status,
    sleepSchedule,
    savings,
    monthlySavings,
    pending,
    streak,
    effectiveTargetTemp,
    effectivePower,
    effectiveOscillation,
    setTargetTemp,
    togglePower,
    toggleOscillation,
    startSleepMode,
    cancelSleepMode,
  } = useHeaterStatus();

  const { readings, latestTimestamp, isStale } = useReadings(chartHours);
  const { status: batteryStatus } = useBatteryStatus();

  // Handlers - use effective values for the next increment
  const handleTempUp = () => {
    setTargetTemp(Math.min(effectiveTargetTemp + 1, 95));
  };

  const handleTempDown = () => {
    setTargetTemp(Math.max(effectiveTargetTemp - 1, 41));
  };

  const handleSleepClick = () => setShowSleepModal(true);

  const handleSleepStart = async (wakeTime: string, curve: { progress: number; temp: number }[]) => {
    await startSleepMode(wakeTime, curve);
    setShowSleepModal(false);
  };

  const handleSleepCancel = async () => {
    await cancelSleepMode();
    setShowSleepModal(false);
  };

  return (
    <>
      <Hero
        savingsToday={savings?.savings ?? 0}
        streakDays={streak}
      />

      <StatusCarousel
        status={status}
        sleepSchedule={sleepSchedule}
        savings={savings}
        isOffline={isStale}
        lastSeen={latestTimestamp}
        onSleepCardClick={() => setShowSleepModal(true)}
      />

      <HomeGrid
        status={status}
        outdoorTemp={status?.outdoor_temp_f ?? null}
        powerWatts={batteryStatus?.watts_out ?? 0}
        effectiveTargetTemp={effectiveTargetTemp}
        effectivePower={effectivePower}
        effectiveOscillation={effectiveOscillation}
        pendingTemp={pending.temp !== undefined}
        onTempUp={handleTempUp}
        onTempDown={handleTempDown}
        onPowerToggle={togglePower}
        onOscillateToggle={toggleOscillation}
        onSleepClick={handleSleepClick}
        sleepActive={sleepSchedule?.active ?? false}
      />

      <TemperatureChart
        readings={readings}
        hours={chartHours}
        onHoursChange={setChartHours}
      />

      <StatsRow
        monthlySavings={monthlySavings?.savings ?? 0}
        dailyKwh={savings?.total_kwh ?? 0}
        peakKwh={savings?.peak_kwh ?? 0}
      />

      <SleepModal
        isOpen={showSleepModal}
        onClose={() => setShowSleepModal(false)}
        onStart={handleSleepStart}
        onCancel={handleSleepCancel}
        currentTarget={effectiveTargetTemp}
        sleepActive={sleepSchedule?.active ?? false}
        sleepProgress={sleepSchedule?.progress}
        serverCurve={sleepSchedule?.curve}
      />
    </>
  );
}
