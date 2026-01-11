import { useState, useEffect } from 'react';
import { useBatteryStatus } from '../hooks/useBatteryStatus';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, ReferenceLine, Tooltip } from 'recharts';

function ToggleSwitch({ enabled, onToggle, loading }: { enabled: boolean; onToggle: () => void; loading: boolean }) {
  return (
    <button
      onClick={onToggle}
      disabled={loading}
      className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
        enabled ? 'bg-emerald-500' : 'bg-gray-300'
      } ${loading ? 'opacity-50' : ''}`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

interface Reading {
  timestamp: string;
  current_temp_f: number | null;
  target_temp_f: number | null;
  power_watts: number | null;
}

function HistoryChart() {
  const [readings, setReadings] = useState<Reading[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchReadings = async () => {
      try {
        const res = await fetch('/api/readings?hours=4&max_points=100');
        if (res.ok) {
          const data = await res.json();
          setReadings(data);
        }
      } catch (e) {
        console.error('Failed to fetch readings:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchReadings();
    const interval = setInterval(fetchReadings, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="h-48 flex items-center justify-center text-gray-400">
        Loading chart...
      </div>
    );
  }

  if (readings.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-gray-400">
        No data yet
      </div>
    );
  }

  // Format data for chart
  const chartData = readings.map((r) => ({
    time: new Date(r.timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
    temp: r.current_temp_f,
    target: r.target_temp_f,
    watts: r.power_watts ? r.power_watts / 20 : null, // Scale watts to fit on temp axis
  }));

  // Get current target for reference line
  const currentTarget = readings[readings.length - 1]?.target_temp_f;

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: '#9ca3af' }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={['dataMin - 2', 'dataMax + 2']}
            tick={{ fontSize: 10, fill: '#9ca3af' }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(255,255,255,0.95)',
              border: 'none',
              borderRadius: '8px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
            }}
            formatter={(value: number, name: string) => {
              if (name === 'watts') return [`${Math.round(value * 20)}W`, 'Power'];
              return [`${value}°F`, name === 'temp' ? 'Room' : 'Target'];
            }}
          />
          {currentTarget && (
            <ReferenceLine
              y={currentTarget}
              stroke="#22c55e"
              strokeDasharray="3 3"
              strokeOpacity={0.7}
            />
          )}
          <Line
            type="monotone"
            dataKey="temp"
            stroke="#f97316"
            strokeWidth={2}
            dot={false}
            name="temp"
          />
          <Line
            type="stepAfter"
            dataKey="target"
            stroke="#22c55e"
            strokeWidth={1.5}
            strokeOpacity={0.5}
            dot={false}
            name="target"
          />
          <Line
            type="monotone"
            dataKey="watts"
            stroke="#3b82f6"
            strokeWidth={1.5}
            strokeOpacity={0.4}
            dot={false}
            name="watts"
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex justify-center gap-4 mt-2 text-xs">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-orange-500 rounded"></span>
          <span className="text-gray-500">Room</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-green-500 rounded opacity-50"></span>
          <span className="text-gray-500">Target</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-blue-500 rounded opacity-40"></span>
          <span className="text-gray-500">Power</span>
        </span>
      </div>
    </div>
  );
}

function AnimatedArrow({ active, direction, color }: { active: boolean; direction: 'right' | 'left'; color: string }) {
  if (!active) {
    return <div className="w-16 h-8 flex items-center justify-center text-gray-300">---</div>;
  }

  return (
    <div className="w-16 h-8 flex items-center justify-center overflow-hidden">
      <div
        className={`flex items-center gap-1 ${direction === 'right' ? 'animate-flow-right' : 'animate-flow-left'}`}
        style={{ color }}
      >
        {direction === 'right' ? (
          <>
            <span className="text-lg font-bold">›</span>
            <span className="text-lg font-bold">›</span>
            <span className="text-lg font-bold">›</span>
          </>
        ) : (
          <>
            <span className="text-lg font-bold">‹</span>
            <span className="text-lg font-bold">‹</span>
            <span className="text-lg font-bold">‹</span>
          </>
        )}
      </div>
      <style>{`
        @keyframes flowRight {
          0% { transform: translateX(-100%); opacity: 0; }
          50% { opacity: 1; }
          100% { transform: translateX(100%); opacity: 0; }
        }
        @keyframes flowLeft {
          0% { transform: translateX(100%); opacity: 0; }
          50% { opacity: 1; }
          100% { transform: translateX(-100%); opacity: 0; }
        }
        .animate-flow-right { animation: flowRight 1s linear infinite; }
        .animate-flow-left { animation: flowLeft 1s linear infinite; }
      `}</style>
    </div>
  );
}

function PowerFlowDiagram({ wattsIn, wattsOut, soc }: { wattsIn: number; wattsOut: number; soc: number }) {
  // Calculate net battery flow
  const netFlow = wattsIn - wattsOut;
  const batteryCharging = netFlow > 50;
  const batteryDischarging = netFlow < -50;

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
      <h3 className="text-sm font-medium text-gray-500 mb-4">Power Flow</h3>

      <div className="flex justify-between">
        {/* Wall/Grid */}
        <div className="flex flex-col items-center w-20">
          <div className="flex items-center">
            <div className="w-14 h-14 rounded-xl bg-blue-100 flex items-center justify-center">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-2">Grid</div>
          <div className={`text-sm font-bold ${wattsIn > 0 ? 'text-blue-600' : 'text-gray-400'}`}>
            {wattsIn > 0 ? `${wattsIn}W` : '0W'}
          </div>
        </div>

        {/* Arrow: Grid → Battery - aligned with icons */}
        <div className="flex items-start pt-3">
          <AnimatedArrow
            active={wattsIn > 0}
            direction="right"
            color="#2563eb"
          />
        </div>

        {/* Battery */}
        <div className="flex flex-col items-center w-20">
          <div className="flex items-center">
            <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${
              batteryCharging ? 'bg-green-100' : batteryDischarging ? 'bg-orange-100' : 'bg-gray-100'
            }`}>
              <div className="relative">
                <svg className={`w-8 h-8 ${
                  batteryCharging ? 'text-green-600' : batteryDischarging ? 'text-orange-600' : 'text-gray-400'
                }`} fill="currentColor" viewBox="0 0 24 24">
                  <rect x="2" y="7" width="18" height="10" rx="2" stroke="currentColor" strokeWidth="2" fill="none"/>
                  <rect x="20" y="10" width="2" height="4" fill="currentColor"/>
                  <rect x="4" y="9" width={`${Math.max(1, soc / 100 * 14)}`} height="6" fill="currentColor" opacity="0.5"/>
                </svg>
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-2">Battery</div>
          <div className={`text-sm font-bold ${
            batteryCharging ? 'text-green-600' : batteryDischarging ? 'text-orange-600' : 'text-gray-500'
          }`}>
            {soc}%
          </div>
        </div>

        {/* Arrow: Battery → Heater - aligned with icons */}
        <div className="flex items-start pt-3">
          <AnimatedArrow
            active={wattsOut > 0}
            direction="right"
            color="#ea580c"
          />
        </div>

        {/* Heater */}
        <div className="flex flex-col items-center w-20">
          <div className="flex items-center">
            <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${
              wattsOut > 0 ? 'bg-orange-100' : 'bg-gray-100'
            }`}>
              <svg className={`w-8 h-8 ${wattsOut > 0 ? 'text-orange-600' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
              </svg>
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-2">Heater</div>
          <div className={`text-sm font-bold ${wattsOut > 0 ? 'text-orange-600' : 'text-gray-400'}`}>
            {wattsOut > 0 ? `${wattsOut}W` : '0W'}
          </div>
        </div>
      </div>

      {/* Flow summary */}
      <div className="mt-4 pt-3 border-t border-gray-100 text-center">
        <span className={`text-sm font-medium ${
          batteryCharging ? 'text-green-600' : batteryDischarging ? 'text-orange-600' : 'text-gray-500'
        }`}>
          {batteryCharging
            ? `Charging at ${netFlow}W`
            : batteryDischarging
              ? `Discharging at ${Math.abs(netFlow)}W`
              : wattsIn > 0 && wattsOut > 0
                ? 'Pass-through (grid → heater)'
                : 'Idle'}
        </span>
      </div>
    </div>
  );
}

export function BatteryPage() {
  const { status, loading, error, refresh } = useBatteryStatus();
  const [toggling, setToggling] = useState(false);
  const [plugOn, setPlugOn] = useState<boolean | null>(null);
  const [togglingPlug, setTogglingPlug] = useState(false);

  // Fetch plug status
  useEffect(() => {
    const fetchPlugStatus = async () => {
      try {
        const res = await fetch('/api/plug');
        if (res.ok) {
          const data = await res.json();
          setPlugOn(data.target_on ?? data.on);
        }
      } catch (e) {
        console.error('Failed to fetch plug status:', e);
      }
    };
    fetchPlugStatus();
    const interval = setInterval(fetchPlugStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTogglePlug = async () => {
    setTogglingPlug(true);
    try {
      const res = await fetch('/api/plug/toggle', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setPlugOn(data.plug_on);
      }
    } catch (e) {
      console.error('Failed to toggle plug:', e);
    } finally {
      setTogglingPlug(false);
    }
  };

  const handleToggleAutomation = async () => {
    setToggling(true);
    try {
      // Toggle between "tou" and "manual" modes
      const newMode = status?.automation_mode === 'tou' ? 'manual' : 'tou';
      const res = await fetch('/api/settings/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      if (res.ok) {
        await refresh();
      }
    } catch (e) {
      console.error('Failed to toggle automation:', e);
    } finally {
      setToggling(false);
    }
  };

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
  const touPeriod = status.tou_period ?? 'unknown';
  // Convert BMS temp from C to F
  const bmsTempC = status.bms_temp_c;
  const bmsTempF = bmsTempC != null ? Math.round(bmsTempC * 9/5 + 32) : null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-br from-emerald-500 to-emerald-700 text-white px-6 pt-6 pb-8">
        <div className="flex justify-between items-start">
          <div>
            <div className="text-sm opacity-90 mb-1">EcoFlow Delta Pro</div>
            <div className="text-3xl font-bold">Battery Status</div>
          </div>
          {bmsTempF != null && (
            <div className="text-right">
              <div className="text-2xl font-bold">{bmsTempF}°F</div>
              <div className="text-xs opacity-75">BMS Temp</div>
            </div>
          )}
        </div>
      </div>

      {/* History Chart */}
      <div className="px-6 -mt-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm mb-4">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Last 4 Hours</h3>
          <HistoryChart />
        </div>

        {/* Power Flow */}
        <PowerFlowDiagram wattsIn={wattsIn} wattsOut={wattsOut} soc={soc} />

        {/* Plug Control */}
        <div className={`rounded-2xl p-5 shadow-sm mb-4 ${plugOn === false ? 'bg-red-50 border-2 border-red-200' : 'bg-white'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${plugOn ? 'bg-blue-100' : 'bg-gray-100'}`}>
                <svg className={`w-5 h-5 ${plugOn ? 'text-blue-600' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-700">Wall Outlet</h3>
                <p className={`text-xs ${plugOn ? 'text-gray-500' : 'text-red-600 font-medium'}`}>
                  {plugOn ? 'Supplying power to battery' : 'Outlet is OFF - battery on its own'}
                </p>
              </div>
            </div>
            <ToggleSwitch
              enabled={plugOn ?? true}
              onToggle={handleTogglePlug}
              loading={togglingPlug}
            />
          </div>
        </div>

        {/* Automation Control */}
        <div className={`rounded-2xl p-5 shadow-sm mb-4 ${status.automation_mode === 'tou' ? 'bg-white' : 'bg-red-50 border-2 border-red-200'}`}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="text-sm font-medium text-gray-700">TOU Automation</h3>
              <p className={`text-xs ${status.automation_mode === 'tou' ? 'text-gray-500' : 'text-red-600 font-medium'}`}>
                {status.automation_mode === 'tou' ? 'Charges off-peak, pauses during peak' : 'Manual mode - you control charging'}
              </p>
            </div>
            <ToggleSwitch
              enabled={status.automation_mode === 'tou'}
              onToggle={handleToggleAutomation}
              loading={toggling}
            />
          </div>
        </div>

        {/* TOU Status */}
        <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-500">Current Rate Period</h3>
              <div className={`text-xl font-bold mt-1 ${touPeriod === 'off_peak' ? 'text-green-600' : 'text-orange-600'}`}>
                {touPeriod === 'off_peak' ? 'Off-Peak (Cheap)' : touPeriod === 'super_peak' ? 'Super Peak ($$$)' : 'Peak ($$)'}
              </div>
            </div>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
              touPeriod === 'off_peak' ? 'bg-green-100' : 'bg-orange-100'
            }`}>
              <span className="text-2xl">{touPeriod === 'off_peak' ? '🌙' : '☀️'}</span>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            {touPeriod === 'off_peak'
              ? 'Off-peak hours: 12AM - 8AM'
              : 'Peak hours: 8AM - 12AM'}
          </p>
        </div>
      </div>

      {/* Bottom spacer for nav */}
      <div className="h-24" />
    </div>
  );
}
