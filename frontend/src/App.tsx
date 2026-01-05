import { useState } from 'react';
import { Hero } from './components/Hero';
import { StatusCarousel } from './components/StatusCarousel';
import { HomeGrid } from './components/HomeGrid';
import { TemperatureChart } from './components/TemperatureChart';
import { StatsRow } from './components/StatsRow';
import { BottomNav } from './components/BottomNav';
// import { SleepModal } from './components/SleepMode/SleepModal';
// import { useHeaterStatus } from './hooks/useHeaterStatus';
// import { useReadings } from './hooks/useReadings';

export default function App() {
  // TODO: Connect to actual API
  // const { status, sleepSchedule, savings, setTargetTemp, togglePower, toggleOscillation } = useHeaterStatus();
  // const { readings } = useReadings();

  // Placeholder state for demo
  const [chartHours, setChartHours] = useState(24);
  const [showSleepModal, setShowSleepModal] = useState(false);

  // Mock data - replace with actual hooks
  const status = {
    power: false,
    current_temp_f: 64,
    target_temp_f: 70,
    heat_mode: null,
    active_heat_level: null,
    power_watts: 0,
    oscillation: true,
    display: true,
    person_detection: false,
    auto_on: false,
    detection_timeout: null,
    timer_remaining_sec: null,
    energy_kwh: null,
    fault_code: null,
  };

  const sleepSchedule = {
    active: false,
  };

  const savings = {
    hours: 24,
    total_kwh: 0,
    peak_kwh: 0,
    offpeak_kwh: 0,
    savings: 0,
    would_have_cost: 0,
    actual_cost: 0,
    current_period: 'offpeak',
    current_rate: 0.13,
  };

  const readings: never[] = [];

  // Handlers - replace with actual API calls
  const handleTempUp = () => console.log('Temp up');
  const handleTempDown = () => console.log('Temp down');
  const handlePowerToggle = () => console.log('Power toggle');
  const handleOscillateToggle = () => console.log('Oscillate toggle');
  const handleSleepClick = () => setShowSleepModal(true);

  return (
    <>
      <Hero
        savingsToday={savings.savings}
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
        outdoorTemp={34}
        onTempUp={handleTempUp}
        onTempDown={handleTempDown}
        onPowerToggle={handlePowerToggle}
        onOscillateToggle={handleOscillateToggle}
        onSleepClick={handleSleepClick}
        sleepActive={sleepSchedule.active}
      />

      <TemperatureChart
        readings={readings}
        hours={chartHours}
        onHoursChange={setChartHours}
      />

      <StatsRow
        monthlySavings={0}
        dailyKwh={0}
        peakKwh={0}
      />

      <BottomNav />

      {/* TODO: Re-enable sleep modal
      {showSleepModal && (
        <SleepModal
          onClose={() => setShowSleepModal(false)}
          // ... other props
        />
      )}
      */}
    </>
  );
}
