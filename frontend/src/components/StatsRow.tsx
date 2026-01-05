interface StatsRowProps {
  monthlySavings: number;
  dailyKwh: number;
  peakKwh: number;
}

export function StatsRow({ monthlySavings, dailyKwh, peakKwh }: StatsRowProps) {
  return (
    <div className="flex gap-3 p-6">
      <div className="flex-1 bg-gray-50 rounded-xl p-4 text-center">
        <div id="stat-month" className="text-2xl font-bold text-emerald-500">
          ${monthlySavings.toFixed(0)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          This month
        </div>
      </div>
      <div className="flex-1 bg-gray-50 rounded-xl p-4 text-center">
        <div id="stat-energy" className="text-2xl font-bold text-emerald-500">
          {dailyKwh.toFixed(1)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          kWh today
        </div>
      </div>
      <div className="flex-1 bg-gray-50 rounded-xl p-4 text-center">
        <div id="stat-events" className="text-2xl font-bold text-emerald-500">
          {peakKwh.toFixed(1)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          Peak kWh
        </div>
      </div>
    </div>
  );
}
