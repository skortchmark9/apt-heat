import { useState, useEffect } from 'react';

interface DayStats {
  date: string;
  total_kwh: number;
  peak_kwh: number;
  offpeak_kwh: number;
  savings: number;
  would_have_cost: number;
  actual_cost: number;
  avg_temp?: number;
  min_temp?: number;
  max_temp?: number;
}

interface HistoryData {
  days: DayStats[];
  streak: number;
  month_savings: number;
  month_kwh: number;
}

export function HistoryPage() {
  const [history, setHistory] = useState<HistoryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('/api/stats/history?days=30');
        if (res.ok) {
          setHistory(await res.json());
        }
      } catch (e) {
        console.error('Failed to fetch stats:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 60000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading stats...</div>
      </div>
    );
  }

  const streak = history?.streak || 0;
  const monthSavings = history?.month_savings || 0;
  const monthKwh = history?.month_kwh || 0;
  const todayStats = history?.days[0];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-br from-purple-500 to-purple-700 text-white px-6 pt-6 pb-8">
        <div className="text-3xl font-bold">History</div>
        <div className="text-sm opacity-90 mt-1">Energy usage & savings</div>
      </div>

      <div className="px-6 -mt-4">
        {/* Summary Stats */}
        <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center p-3 bg-emerald-50 rounded-xl">
              <div className="text-2xl font-bold text-emerald-600">${monthSavings.toFixed(2)}</div>
              <div className="text-xs text-gray-500 mt-1">Saved this month</div>
            </div>
            <div className="text-center p-3 bg-purple-50 rounded-xl">
              <div className="text-2xl font-bold text-purple-600">{streak}</div>
              <div className="text-xs text-gray-500 mt-1">Day streak</div>
            </div>
            <div className="text-center p-3 bg-blue-50 rounded-xl">
              <div className="text-2xl font-bold text-blue-600">{monthKwh.toFixed(1)}</div>
              <div className="text-xs text-gray-500 mt-1">kWh this month</div>
            </div>
            <div className="text-center p-3 bg-orange-50 rounded-xl">
              <div className="text-2xl font-bold text-orange-600">{todayStats?.total_kwh.toFixed(1) || '0'}</div>
              <div className="text-xs text-gray-500 mt-1">kWh today</div>
            </div>
          </div>
        </div>

        {/* Daily Breakdown */}
        <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
          <h3 className="text-sm font-medium text-gray-500 mb-4">Daily Breakdown</h3>
          <div className="space-y-2">
            {(() => {
              const days = history?.days || [];
              const today = new Date().toISOString().split('T')[0];
              const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];

              return days.map((day) => {
                const date = new Date(day.date + 'T12:00:00');
                const dayLabel = day.date === today ? 'Today'
                  : day.date === yesterday ? 'Yesterday'
                  : date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

                return (
                  <div key={day.date} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                    <div>
                      <div className="text-sm font-medium text-gray-700">{dayLabel}</div>
                      <div className="text-xs text-gray-400">{day.total_kwh.toFixed(1)} kWh total</div>
                    </div>
                    <div className="text-right">
                      <div className={`text-sm font-bold ${day.savings > 0 ? 'text-emerald-500' : 'text-gray-400'}`}>
                        {day.savings > 0 ? `+$${day.savings.toFixed(2)}` : '$0.00'}
                      </div>
                      <div className="text-xs text-gray-400">
                        {day.peak_kwh.toFixed(1)} peak / {day.offpeak_kwh.toFixed(1)} off-peak
                      </div>
                    </div>
                  </div>
                );
              });
            })()}
          </div>
        </div>
      </div>

      {/* Bottom spacer for nav */}
      <div className="h-24" />
    </div>
  );
}
