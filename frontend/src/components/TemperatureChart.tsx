import {
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  ComposedChart,
} from 'recharts';
import { format } from 'date-fns';
import type { HeaterReading } from '../types';

interface TemperatureChartProps {
  readings: HeaterReading[];
  hours: number;
  onHoursChange: (hours: number) => void;
}

const HOUR_OPTIONS = [
  { label: '1H', value: 1 },
  { label: '6H', value: 6 },
  { label: '24H', value: 24 },
  { label: '7D', value: 168 },
];

export function TemperatureChart({ readings, hours, onHoursChange }: TemperatureChartProps) {
  const chartData = readings.map((r) => ({
    timestamp: new Date(r.timestamp).getTime(),
    indoor: r.current_temp_f,
    target: r.target_temp_f,
    outdoor: r.outdoor_temp_f,
  }));

  const formatXAxis = (timestamp: number) => {
    if (hours > 24) {
      return format(timestamp, 'EEE');
    }
    return format(timestamp, 'ha');
  };

  return (
    <div className="chart-section" style={{ background: '#F9FAFB', padding: '1.5rem', margin: 0 }}>
      <div
        className="section-header"
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}
      >
        <span
          className="section-title"
          style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7280' }}
        >
          Temperature History
        </span>
      </div>

      <div className="chart-controls" style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        {HOUR_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className="chart-btn"
            data-hours={opt.value}
            onClick={() => onHoursChange(opt.value)}
            style={{
              flex: 1,
              padding: '0.5rem',
              borderRadius: '8px',
              border: 'none',
              background: hours === opt.value ? '#8B5CF6' : '#F3F4F6',
              color: hours === opt.value ? 'white' : '#4B5563',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div
        className="chart-container"
        style={{ background: 'white', borderRadius: '16px', padding: '1rem', marginTop: '1rem' }}
      >
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
            <defs>
              <linearGradient id="indoorGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatXAxis}
              tick={{ fill: '#9CA3AF', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickCount={6}
            />
            <YAxis
              tick={{ fill: '#9CA3AF', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              domain={['dataMin - 5', 'dataMax + 5']}
            />
            <Tooltip
              contentStyle={{
                background: '#fff',
                border: '1px solid #E5E7EB',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              labelFormatter={(ts) => format(ts, 'MMM d, h:mm a')}
            />
            <Legend
              wrapperStyle={{ fontSize: '12px', paddingTop: '16px' }}
              iconType="line"
            />
            <Area
              type="monotone"
              dataKey="indoor"
              stroke="#8B5CF6"
              fill="url(#indoorGradient)"
              strokeWidth={2}
              dot={false}
              name="Indoor"
            />
            <Line
              type="monotone"
              dataKey="target"
              stroke="#9CA3AF"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              dot={false}
              name="Target"
            />
            <Line
              type="monotone"
              dataKey="outdoor"
              stroke="#60A5FA"
              strokeWidth={1.5}
              dot={false}
              name="Outdoor"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
