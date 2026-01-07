import type { HeaterStatus } from '../types';

interface HomeGridProps {
  status: HeaterStatus | null;
  outdoorTemp: number | null;
  powerWatts: number;
  onTempUp: () => void;
  onTempDown: () => void;
  onPowerToggle: () => void;
  onOscillateToggle: () => void;
  onSleepClick: () => void;
  sleepActive: boolean;
}

export function HomeGrid({
  status,
  outdoorTemp,
  powerWatts,
  onTempUp,
  onTempDown,
  onPowerToggle,
  onOscillateToggle,
  onSleepClick,
  sleepActive,
}: HomeGridProps) {
  const currentTemp = status?.current_temp_f ?? null;
  const targetTemp = status?.target_temp_f ?? 72;
  const isPowerOn = status?.power ?? false;
  const isOscillating = status?.oscillation ?? false;

  // Determine temperature status
  let tempStatus = 'Loading...';
  if (currentTemp !== null) {
    const diff = currentTemp - targetTemp;
    if (diff < -1) tempStatus = 'Heating to target';
    else if (diff > 1) tempStatus = 'Above target';
    else tempStatus = 'At target';
  }

  // Power status text
  let powerStatus = '--';
  if (isPowerOn) {
    powerStatus = powerWatts > 0 ? 'Heating' : 'Idle';
  } else {
    powerStatus = 'Off';
  }

  const controlBtnBase = 'flex-1 py-2.5 rounded-xl border-none text-xs font-semibold cursor-pointer flex flex-col items-center gap-1';

  return (
    <div className="px-5 py-4">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Your Home
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-2">
        {/* Main Temperature Card */}
        <div className="col-span-2 flex justify-between items-center bg-gradient-to-br from-amber-100 to-amber-200 rounded-2xl px-5 py-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Inside</div>
            <div id="current-temp" className="text-[2rem] font-bold text-gray-900">
              {currentTemp !== null ? `${currentTemp}°` : '--°'}
            </div>
            <div id="temp-status" className="text-xs text-gray-500 mt-1">
              {tempStatus}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button
              id="temp-down"
              onClick={onTempDown}
              className="w-11 h-11 rounded-full border-2 border-gray-900 bg-white text-2xl font-light cursor-pointer flex items-center justify-center"
            >
              −
            </button>
            <div className="text-center">
              <div className="text-[0.625rem] uppercase tracking-wider text-gray-500">
                Target
              </div>
              <div id="target-temp" className="text-[1.75rem] font-bold">
                {targetTemp}°
              </div>
            </div>
            <button
              id="temp-up"
              onClick={onTempUp}
              className="w-11 h-11 rounded-full border-2 border-gray-900 bg-white text-2xl font-light cursor-pointer flex items-center justify-center"
            >
              +
            </button>
          </div>
        </div>

        {/* Outside Card */}
        <div className="bg-gray-50 rounded-2xl p-4">
          <div className="text-xs text-gray-500 mb-1">Outside</div>
          <div id="outdoor-temp" className="text-2xl font-bold text-gray-900">
            {outdoorTemp !== null ? `${outdoorTemp}°` : '--°'}
          </div>
          <div id="outdoor-feels" className="text-xs text-gray-500 mt-1">
            {outdoorTemp !== null ? 'Current' : '--'}
          </div>
        </div>

        {/* Power Card */}
        <div className="bg-gray-50 rounded-2xl p-4">
          <div className="text-xs text-gray-500 mb-1">Power</div>
          <div id="power-watts" className="text-2xl font-bold text-gray-900">
            {powerWatts}W
          </div>
          <div id="power-status" className="text-xs text-gray-500 mt-1">
            {powerStatus}
          </div>
        </div>
      </div>

      {/* Heater Controls */}
      <div className="flex gap-2 mt-2">
        <button
          id="btn-power"
          onClick={onPowerToggle}
          className={`${controlBtnBase} ${isPowerOn ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          <span className="text-lg">⚡</span>
          <span>Power</span>
        </button>
        <button
          id="btn-oscillate"
          onClick={onOscillateToggle}
          className={`${controlBtnBase} ${isOscillating ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          <span className="text-lg">🌀</span>
          <span>Oscillate</span>
        </button>
        <button
          id="btn-sleep"
          onClick={onSleepClick}
          className={`${controlBtnBase} ${sleepActive ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          <span className="text-lg">🌙</span>
          <span>Sleep</span>
        </button>
      </div>
    </div>
  );
}
