import { useState, useEffect } from 'react';

interface TodayStats {
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
  days: TodayStats[];
  streak: number;
  month_savings: number;
  month_kwh: number;
}

export function HistoryPage() {
  const [today, setToday] = useState<TodayStats | null>(null);
  const [history, setHistory] = useState<HistoryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [todayRes, historyRes] = await Promise.all([
          fetch('/api/stats/today'),
          fetch('/api/stats/history?days=30'),
        ]);

        if (todayRes.ok) {
          setToday(await todayRes.json());
        }
        if (historyRes.ok) {
          setHistory(await historyRes.json());
        }
      } catch (e) {
        console.error('Failed to fetch stats:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading stats...</div>
      </div>
    );
  }

  const todayStats = today || {
    savings: 0,
    would_have_cost: 0,
    actual_cost: 0,
    total_kwh: 0,
    peak_kwh: 0,
  };

  const streak = history?.streak || 0;
  const monthSavings = history?.month_savings || 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero Card - Saved Today */}
      <div className="bg-gradient-to-br from-purple-500 to-purple-700 text-white px-6 pt-6 pb-8">
        <div className="flex justify-between items-start mb-4">
          <div className="text-sm opacity-90">Saved today</div>
          <div className="bg-white/20 rounded-full px-3 py-1 text-xs font-medium">
            {streak > 0 ? `${streak} day streak` : '-- day streak'}
          </div>
        </div>
        <div className="text-5xl font-bold mb-2">
          ${todayStats.savings.toFixed(2)}
        </div>
        <div className="text-sm opacity-90">during peak hours</div>
      </div>

      {/* Rate Comparison Card */}
      <div className="px-6 -mt-4">
        <div className="bg-gradient-to-br from-orange-400 to-orange-500 rounded-2xl p-5 shadow-lg text-white mb-4">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <span className="text-xl">🔥</span>
            </div>
            <div>
              <div className="font-semibold">Heating your home</div>
              <div className="text-sm opacity-90">Target: 70°F</div>
            </div>
          </div>

          <div className="flex items-center justify-around bg-white/10 rounded-xl p-4">
            <div className="text-center">
              <div className="text-xs opacity-75 mb-1">GRID RATE</div>
              <div className="text-2xl font-bold">${todayStats.would_have_cost.toFixed(2)}</div>
            </div>
            <div className="text-2xl opacity-75">→</div>
            <div className="text-center">
              <div className="text-xs opacity-75 mb-1">YOU PAY</div>
              <div className="text-2xl font-bold">${todayStats.actual_cost.toFixed(2)}</div>
            </div>
          </div>
        </div>

        {/* Stats Row */}
        <div className="flex gap-3 mb-4">
          <div className="flex-1 bg-white rounded-xl p-4 shadow-sm text-center">
            <div className="text-xl font-bold text-emerald-500">${monthSavings.toFixed(0)}</div>
            <div className="text-xs text-gray-500 mt-1">This month</div>
          </div>
          <div className="flex-1 bg-white rounded-xl p-4 shadow-sm text-center">
            <div className="text-xl font-bold text-emerald-500">{todayStats.total_kwh.toFixed(1)}</div>
            <div className="text-xs text-gray-500 mt-1">kWh today</div>
          </div>
          <div className="flex-1 bg-white rounded-xl p-4 shadow-sm text-center">
            <div className="text-xl font-bold text-emerald-500">{todayStats.peak_kwh.toFixed(1)}</div>
            <div className="text-xs text-gray-500 mt-1">Peak kWh</div>
          </div>
        </div>

        {/* Daily History */}
        <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
          <h3 className="text-sm font-medium text-gray-500 mb-4">Daily Breakdown</h3>
          <div className="space-y-3">
            {history?.days.slice(0, 7).map((day, i) => {
              const date = new Date(day.date + 'T12:00:00');
              const dayLabel = i === 0 ? 'Today' : i === 1 ? 'Yesterday' : date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

              return (
                <div key={day.date} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                  <div>
                    <div className="text-sm font-medium text-gray-700">{dayLabel}</div>
                    <div className="text-xs text-gray-400">{day.total_kwh.toFixed(1)} kWh</div>
                  </div>
                  <div className="text-right">
                    <div className={`text-sm font-bold ${day.savings > 0 ? 'text-emerald-500' : 'text-gray-400'}`}>
                      {day.savings > 0 ? `+$${day.savings.toFixed(2)}` : '$0.00'}
                    </div>
                    <div className="text-xs text-gray-400">
                      {day.peak_kwh.toFixed(1)} peak
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom spacer for nav */}
      <div className="h-24" />
    </div>
  );
}
