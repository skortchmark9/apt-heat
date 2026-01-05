interface StatsRowProps {
  monthlySavings: number;
  dailyKwh: number;
  peakKwh: number;
}

export function StatsRow({ monthlySavings, dailyKwh, peakKwh }: StatsRowProps) {
  return (
    <div className="stats-row" style={{ display: 'flex', gap: '0.75rem', padding: '1.5rem' }}>
      <div
        className="stat-card"
        style={{ flex: 1, background: '#F9FAFB', borderRadius: '12px', padding: '1rem', textAlign: 'center' }}
      >
        <div id="stat-month" className="stat-value" style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10B981' }}>
          ${monthlySavings.toFixed(0)}
        </div>
        <div className="stat-label" style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.25rem' }}>
          This month
        </div>
      </div>
      <div
        className="stat-card"
        style={{ flex: 1, background: '#F9FAFB', borderRadius: '12px', padding: '1rem', textAlign: 'center' }}
      >
        <div id="stat-energy" className="stat-value" style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10B981' }}>
          {dailyKwh.toFixed(1)}
        </div>
        <div className="stat-label" style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.25rem' }}>
          kWh today
        </div>
      </div>
      <div
        className="stat-card"
        style={{ flex: 1, background: '#F9FAFB', borderRadius: '12px', padding: '1rem', textAlign: 'center' }}
      >
        <div id="stat-events" className="stat-value" style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10B981' }}>
          {peakKwh.toFixed(1)}
        </div>
        <div className="stat-label" style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.25rem' }}>
          Peak kWh
        </div>
      </div>
    </div>
  );
}
