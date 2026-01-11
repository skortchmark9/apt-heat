import { useBatteryStatus } from '../../hooks/useBatteryStatus';

export function BatteryCard() {
  const { status, loading } = useBatteryStatus();

  const soc = status?.soc;
  const wattsIn = status?.watts_in ?? 0;
  const wattsOut = status?.watts_out ?? 0;
  const netFlow = wattsIn - wattsOut;

  const batteryPercent = soc != null ? soc : '--';

  let power = '-- W';
  let statusText = 'Not connected';

  if (status?.configured && !loading) {
    if (netFlow > 50) {
      power = `+${netFlow} W`;
      statusText = 'Charging';
    } else if (netFlow < -50) {
      power = `${netFlow} W`;
      statusText = 'Discharging';
    } else if (wattsIn > 0 && wattsOut > 0) {
      power = `${wattsOut} W`;
      statusText = 'Pass-through';
    } else {
      power = '0 W';
      statusText = 'Idle';
    }
  }

  return (
    <div className="flex-[0_0_100%] snap-start bg-gradient-to-br from-blue-500 to-blue-700 rounded-2xl py-3.5 px-4 text-white shadow-[0_4px_20px_rgba(59,130,246,0.3)]">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-lg">
          🔋
        </div>
        <div>
          <h3 className="text-base font-semibold m-0">Battery Status</h3>
          <p className="text-xs opacity-90 m-0">EcoFlow DELTA Pro</p>
        </div>
      </div>
      <div className="flex items-center gap-4 mt-2">
        <div id="battery-percent" className="text-[2.5rem] font-bold">
          {batteryPercent}%
        </div>
        <div className="flex flex-col gap-1 text-sm opacity-90">
          <span id="battery-power">{power}</span>
          <span id="battery-status">{statusText}</span>
        </div>
      </div>
    </div>
  );
}
