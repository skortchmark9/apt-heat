import type { HeaterStatus, SleepSchedule, SavingsData } from '../../types';

interface CurrentStatusCardProps {
  status: HeaterStatus | null;
  sleepSchedule: SleepSchedule | null;
  savings: SavingsData | null;
  onClick?: () => void;
}

export function CurrentStatusCard({ status, sleepSchedule, savings, onClick }: CurrentStatusCardProps) {
  const isOff = !status?.power;
  const isHeating = status?.power && (status?.power_watts ?? 0) > 0;
  const isSleepActive = sleepSchedule?.active;

  // Check if we're at target (within 1 degree)
  const currentTemp = status?.current_temp_f ?? 0;
  const targetTemp = status?.target_temp_f ?? 0;
  const tempDiff = currentTemp - targetTemp;
  const isAtTarget = Math.abs(tempDiff) <= 1;

  // Determine card style
  let cardClasses = 'from-emerald-500 to-emerald-600 shadow-[0_4px_20px_rgba(16,185,129,0.3)]';

  if (isSleepActive) {
    cardClasses = 'from-purple-500 to-purple-700 shadow-[0_4px_20px_rgba(139,92,246,0.3)]';
  } else if (isOff) {
    cardClasses = 'from-gray-400 to-gray-500 shadow-[0_4px_20px_rgba(107,114,128,0.3)]';
  } else if (isHeating) {
    cardClasses = 'from-amber-500 to-amber-600 shadow-[0_4px_20px_rgba(245,158,11,0.3)]';
  }

  // Determine icon and text
  let icon = '✅';
  let title = 'Temperature reached';
  let subtitle = `Maintaining ${status?.target_temp_f ?? '--'}°F`;

  if (isSleepActive && sleepSchedule) {
    icon = '🌙';
    title = 'Sleep mode active';
    const wakeDate = new Date(sleepSchedule.wake_time!);
    const wakeStr = wakeDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    subtitle = `Target: ${sleepSchedule.current_target}°F · Wake: ${wakeStr}`;
  } else if (!status) {
    icon = '⏳';
    title = 'Loading...';
    subtitle = 'Checking heater status';
  } else if (isOff) {
    icon = '⏸️';
    title = 'Heater is off';
    subtitle = 'Tap Power to turn on';
  } else if (isHeating) {
    icon = '🔥';
    title = 'Heating your home';
    subtitle = `Target: ${status?.target_temp_f ?? '--'}°F`;
  } else if (!isAtTarget) {
    // Power on, not heating, but not at target yet
    icon = '🔥';
    title = tempDiff < 0 ? 'Heating to target' : 'Cooling down';
    subtitle = `${currentTemp}°F → ${targetTemp}°F`;
    cardClasses = 'from-amber-500 to-amber-600 shadow-[0_4px_20px_rgba(245,158,11,0.3)]';
  }

  const gridRate = savings?.current_rate ?? 0.35;
  const offpeakRate = 0.0249;

  return (
    <div
      id="status-card"
      onClick={onClick}
      className={`flex-[0_0_100%] snap-start bg-gradient-to-br ${cardClasses} rounded-2xl py-3.5 px-4 text-white ${onClick ? 'cursor-pointer' : ''}`}
    >
      <div className="flex items-center gap-3 mb-2">
        <div
          id="status-icon"
          className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-lg"
        >
          {icon}
        </div>
        <div>
          <h3 id="status-title" className="text-base font-semibold m-0">
            {title}
          </h3>
          <p id="status-subtitle" className="text-xs opacity-90 m-0">
            {subtitle}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between bg-white/15 rounded-lg py-2 px-3">
        <div className="text-center">
          <div className="text-[0.625rem] uppercase tracking-wider opacity-80">
            Grid rate
          </div>
          <div
            id="grid-rate"
            className="text-xl font-bold line-through opacity-70"
          >
            ${gridRate.toFixed(2)}
          </div>
        </div>
        <div className="text-xl opacity-60">→</div>
        <div className="text-center">
          <div className="text-[0.625rem] uppercase tracking-wider opacity-80">
            You pay
          </div>
          <div id="your-rate" className="text-xl font-bold">
            ${offpeakRate.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  );
}
