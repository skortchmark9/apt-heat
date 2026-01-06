import { useBatteryStatus } from '../hooks/useBatteryStatus';

function BatteryIcon({ soc }: { soc: number }) {
  // Battery fill color based on charge level
  const fillColor = soc > 50 ? '#22c55e' : soc > 20 ? '#eab308' : '#ef4444';
  const fillHeight = Math.max(0, Math.min(100, soc));

  return (
    <div className="relative w-24 h-40 mx-auto mb-6">
      {/* Battery cap */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-10 h-3 bg-gray-300 rounded-t-md" />
      {/* Battery body */}
      <div className="absolute top-3 w-full h-[calc(100%-12px)] border-4 border-gray-300 rounded-lg overflow-hidden bg-gray-100">
        {/* Fill level */}
        <div
          className="absolute bottom-0 left-0 right-0 transition-all duration-500"
          style={{ height: `${fillHeight}%`, backgroundColor: fillColor }}
        />
        {/* Percentage text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold text-gray-700">{soc}%</span>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ label, value, variant = 'default' }: { label: string; value: string; variant?: 'default' | 'success' | 'warning' }) {
  const variantClasses = {
    default: 'bg-gray-100 text-gray-700',
    success: 'bg-green-100 text-green-700',
    warning: 'bg-yellow-100 text-yellow-700',
  };

  return (
    <div className={`px-4 py-2 rounded-xl ${variantClasses[variant]}`}>
      <div className="text-xs opacity-70">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

function PowerFlow({ wattsIn, wattsOut }: { wattsIn: number; wattsOut: number }) {
  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
      <h3 className="text-sm font-medium text-gray-500 mb-4">Power Flow</h3>
      <div className="flex justify-between items-center">
        <div className="text-center flex-1">
          <div className="text-3xl mb-1">
            {wattsIn > 0 ? '🔌' : ''}
          </div>
          <div className="text-2xl font-bold text-green-600">{wattsIn}W</div>
          <div className="text-xs text-gray-500">AC In</div>
        </div>
        <div className="text-4xl text-gray-300 px-4">
          {wattsIn > 0 ? '→' : wattsOut > 0 ? '←' : '·'}
        </div>
        <div className="text-center flex-1">
          <div className="text-3xl mb-1">
            {wattsOut > 0 ? '⚡' : ''}
          </div>
          <div className="text-2xl font-bold text-orange-500">{wattsOut}W</div>
          <div className="text-xs text-gray-500">AC Out</div>
        </div>
      </div>
    </div>
  );
}

export function BatteryPage() {
  const { status, loading, error } = useBatteryStatus();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading battery status...</div>
      </div>
    );
  }

  if (!status?.configured) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm text-center">
          <div className="text-4xl mb-4">🔋</div>
          <h2 className="text-xl font-semibold mb-2">Battery Not Configured</h2>
          <p className="text-gray-500">
            Add ECOFLOW_ACCESS_KEY, ECOFLOW_SECRET_KEY, and ECOFLOW_SERIAL_NUMBER to your environment variables.
          </p>
        </div>
      </div>
    );
  }

  if (error || status.error) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="bg-red-50 rounded-2xl p-6 text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-red-700 mb-2">Connection Error</h2>
          <p className="text-red-600">{error || status.error}</p>
        </div>
      </div>
    );
  }

  const soc = status.soc ?? 0;
  const wattsIn = status.watts_in ?? 0;
  const wattsOut = status.watts_out ?? 0;
  const chargeLimit = status.charge_limit ?? 0;
  const touPeriod = status.tou_period ?? 'unknown';
  const chargeState = status.charge_state ?? 'unknown';

  // Determine battery state
  let stateLabel = 'Idle';
  let stateVariant: 'default' | 'success' | 'warning' = 'default';
  if (status.charging) {
    stateLabel = 'Charging';
    stateVariant = 'success';
  } else if (status.discharging) {
    stateLabel = 'Discharging';
    stateVariant = 'warning';
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-br from-emerald-500 to-emerald-700 text-white px-6 pt-6 pb-8">
        <div className="text-sm opacity-90 mb-1">EcoFlow Delta Pro</div>
        <div className="text-3xl font-bold">Battery Status</div>
      </div>

      {/* Battery Visualization */}
      <div className="px-6 -mt-4">
        <div className="bg-white rounded-2xl p-6 shadow-sm mb-4">
          <BatteryIcon soc={soc} />

          {/* Status badges */}
          <div className="grid grid-cols-2 gap-3">
            <StatusBadge label="State" value={stateLabel} variant={stateVariant} />
            <StatusBadge
              label="Charge Limit"
              value={chargeLimit > 0 ? `${chargeLimit}W` : 'Paused'}
            />
          </div>
        </div>

        {/* Power Flow */}
        <PowerFlow wattsIn={wattsIn} wattsOut={wattsOut} />

        {/* Peak Shaving Status */}
        <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
          <h3 className="text-sm font-medium text-gray-500 mb-4">Peak Shaving</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className={`p-4 rounded-xl ${touPeriod === 'off_peak' ? 'bg-green-100' : 'bg-orange-100'}`}>
              <div className="text-xs opacity-70 mb-1">TOU Period</div>
              <div className={`text-lg font-semibold ${touPeriod === 'off_peak' ? 'text-green-700' : 'text-orange-700'}`}>
                {touPeriod === 'off_peak' ? 'Off-Peak' : touPeriod === 'super_peak' ? 'Super Peak' : 'Peak'}
              </div>
            </div>
            <div className={`p-4 rounded-xl ${chargeState === 'charging' ? 'bg-green-100' : 'bg-gray-100'}`}>
              <div className="text-xs opacity-70 mb-1">Charge Mode</div>
              <div className={`text-lg font-semibold ${chargeState === 'charging' ? 'text-green-700' : 'text-gray-700'}`}>
                {chargeState === 'charging' ? 'Active' : 'Paused'}
              </div>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-4">
            {touPeriod === 'off_peak'
              ? 'Charging from grid during cheap off-peak hours (12AM-8AM)'
              : 'Grid charging paused during expensive peak hours (8AM-12AM)'}
          </p>
        </div>
      </div>

      {/* Bottom spacer for nav */}
      <div className="h-24" />
    </div>
  );
}
