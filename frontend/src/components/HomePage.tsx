import { useState } from 'react';
import { Hero } from './Hero';
import { StatusCarousel } from './StatusCarousel';
import { HomeGrid } from './HomeGrid';
import { TemperatureChart } from './TemperatureChart';
import { StatsRow } from './StatsRow';
import { SleepModal } from './SleepModal';
import { useHeaterStatus } from '../hooks/useHeaterStatus';
import { useReadings } from '../hooks/useReadings';

export function HomePage() {
  const [chartHours, setChartHours] = useState(24);
  const [showSleepModal, setShowSleepModal] = useState(false);

  // API hooks
  const {
    status,
    sleepSchedule,
    savings,
    monthlySavings,
    setTargetTemp,
    togglePower,
    toggleOscillation,
    startSleepMode,
    cancelSleepMode,
  } = useHeaterStatus();

  const { readings, latestOutdoorTemp } = useReadings(chartHours);

  // Handlers
  const handleTempUp = () => {
    const currentTarget = status?.target_temp_f ?? 72;
    setTargetTemp(Math.min(currentTarget + 1, 95));
  };

  const handleTempDown = () => {
    const currentTarget = status?.target_temp_f ?? 72;
    setTargetTemp(Math.max(currentTarget - 1, 41));
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
        streakDays={null}
      />

      <StatusCarousel
        status={status}
        sleepSchedule={sleepSchedule}
        savings={savings}
        onSleepCardClick={() => setShowSleepModal(true)}
      />

      <HomeGrid
        status={status}
        outdoorTemp={latestOutdoorTemp}
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
        currentTarget={status?.target_temp_f ?? 72}
        sleepActive={sleepSchedule?.active ?? false}
        sleepProgress={sleepSchedule?.progress}
        serverCurve={sleepSchedule?.curve}
      />
    </>
  );
}
