export function BatteryCard() {
  // TODO: Connect to EcoFlow API
  const batteryPercent = '--';
  const power = '-- W';
  const status = 'Not connected';

  return (
    <div
      className="status-card battery-card"
      style={{
        flex: '0 0 100%',
        scrollSnapAlign: 'start',
        background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
        borderRadius: '16px',
        padding: '0.875rem 1rem',
        color: 'white',
        boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
      }}
    >
      <div
        className="status-top"
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}
      >
        <div
          className="status-icon"
          style={{
            width: '32px',
            height: '32px',
            background: 'rgba(255,255,255,0.2)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.125rem'
          }}
        >
          🔋
        </div>
        <div className="status-text">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Battery Status</h3>
          <p style={{ fontSize: '0.75rem', opacity: 0.9, margin: 0 }}>EcoFlow DELTA Pro</p>
        </div>
      </div>
      <div
        className="battery-visual"
        style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.5rem' }}
      >
        <div
          id="battery-percent"
          className="battery-big-percent"
          style={{ fontSize: '2.5rem', fontWeight: 700 }}
        >
          {batteryPercent}%
        </div>
        <div
          className="battery-details"
          style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', fontSize: '0.875rem', opacity: 0.9 }}
        >
          <span id="battery-power">{power}</span>
          <span id="battery-status">{status}</span>
        </div>
      </div>
    </div>
  );
}
