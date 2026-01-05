interface HeroProps {
  savingsToday?: number;
  streakDays?: number | null;
}

export function Hero({ savingsToday = 0, streakDays = null }: HeroProps) {
  return (
    <div
      className="hero"
      style={{
        background: 'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)',
        color: 'white',
        padding: '1.5rem 1.5rem 1.25rem',
        position: 'relative'
      }}
    >
      <div
        className="hero-top"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '0.5rem'
        }}
      >
        <div className="hero-label" style={{ fontSize: '0.875rem', opacity: 0.9 }}>
          Saved today
        </div>
        <div
          className="streak-badge"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            background: 'rgba(255,255,255,0.2)',
            padding: '0.375rem 0.75rem',
            borderRadius: '100px',
            fontSize: '0.75rem',
            fontWeight: 600
          }}
        >
          <span id="streak-count">{streakDays ?? '--'}</span>
          <span>day streak</span>
        </div>
      </div>
      <div
        id="savings-today"
        className="hero-amount"
        style={{
          fontSize: '4rem',
          fontWeight: 700,
          letterSpacing: '-0.03em',
          lineHeight: 1,
          marginBottom: '0.25rem'
        }}
      >
        ${savingsToday.toFixed(2)}
      </div>
      <div className="hero-subtitle" style={{ fontSize: '1rem', opacity: 0.9 }}>
        during peak hours
      </div>
    </div>
  );
}
