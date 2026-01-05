import type { HeaterStatus } from '../types';

interface HomeGridProps {
  status: HeaterStatus | null;
  outdoorTemp: number | null;
  onTempUp: () => void;
  onTempDown: () => void;
  onPowerToggle: () => void;
  onOscillateToggle: () => void;
  onSleepClick: () => void;
  sleepActive: boolean;
}

export function HomeGrid({
  status,
  outdoorTemp,
  onTempUp,
  onTempDown,
  onPowerToggle,
  onOscillateToggle,
  onSleepClick,
  sleepActive,
}: HomeGridProps) {
  const currentTemp = status?.current_temp_f ?? null;
  const targetTemp = status?.target_temp_f ?? 72;
  const powerWatts = status?.power_watts ?? 0;
  const isPowerOn = status?.power ?? false;
  const isOscillating = status?.oscillation ?? false;

  // Determine temperature status
  let tempStatus = 'Loading...';
  if (currentTemp !== null) {
    const diff = currentTemp - targetTemp;
    if (diff < -1) tempStatus = 'Heating to target';
    else if (diff > 1) tempStatus = 'Above target';
    else tempStatus = 'At target';
  }

  // Power status text
  let powerStatus = '--';
  if (isPowerOn) {
    powerStatus = powerWatts > 0 ? 'Heating' : 'Idle';
  } else {
    powerStatus = 'Off';
  }

  const buttonBaseStyle = {
    flex: 1,
    padding: '0.625rem',
    borderRadius: '12px',
    border: 'none',
    fontSize: '0.75rem',
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: '0.25rem'
  };

  return (
    <div className="section" style={{ padding: '1rem 1.25rem' }}>
      <div
        className="section-header"
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}
      >
        <span
          className="section-title"
          style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7280' }}
        >
          Your Home
        </span>
      </div>

      <div
        className="home-grid"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '0.5rem' }}
      >
        {/* Main Temperature Card */}
        <div
          className="home-card main"
          style={{
            gridColumn: '1 / -1',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%)',
            borderRadius: '16px',
            padding: '1rem 1.25rem'
          }}
        >
          <div>
            <div className="home-card-label" style={{ fontSize: '0.75rem', color: '#6B7280', marginBottom: '0.25rem' }}>
              Inside
            </div>
            <div id="current-temp" className="home-card-value" style={{ fontSize: '2rem', fontWeight: 700, color: '#111827' }}>
              {currentTemp !== null ? `${currentTemp}°` : '--°'}
            </div>
            <div id="temp-status" className="home-card-sub" style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.25rem' }}>
              {tempStatus}
            </div>
          </div>
          <div className="temp-controls" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button
              id="temp-down"
              className="temp-btn"
              onClick={onTempDown}
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                border: '2px solid #111827',
                background: 'white',
                fontSize: '1.5rem',
                fontWeight: 300,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              −
            </button>
            <div className="target-display" style={{ textAlign: 'center' }}>
              <div className="target-label" style={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7280' }}>
                Target
              </div>
              <div id="target-temp" className="target-value" style={{ fontSize: '1.75rem', fontWeight: 700 }}>
                {targetTemp}°
              </div>
            </div>
            <button
              id="temp-up"
              className="temp-btn"
              onClick={onTempUp}
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                border: '2px solid #111827',
                background: 'white',
                fontSize: '1.5rem',
                fontWeight: 300,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              +
            </button>
          </div>
        </div>

        {/* Outside Card */}
        <div className="home-card" style={{ background: '#F9FAFB', borderRadius: '16px', padding: '1rem' }}>
          <div className="home-card-label" style={{ fontSize: '0.75rem', color: '#6B7280', marginBottom: '0.25rem' }}>
            Outside
          </div>
          <div id="outdoor-temp" className="home-card-value small" style={{ fontSize: '1.5rem', fontWeight: 700, color: '#111827' }}>
            {outdoorTemp !== null ? `${outdoorTemp}°` : '--°'}
          </div>
          <div id="outdoor-feels" className="home-card-sub" style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.25rem' }}>
            {outdoorTemp !== null ? 'Current' : '--'}
          </div>
        </div>

        {/* Power Card */}
        <div className="home-card" style={{ background: '#F9FAFB', borderRadius: '16px', padding: '1rem' }}>
          <div className="home-card-label" style={{ fontSize: '0.75rem', color: '#6B7280', marginBottom: '0.25rem' }}>
            Power
          </div>
          <div id="power-watts" className="home-card-value small" style={{ fontSize: '1.5rem', fontWeight: 700, color: '#111827' }}>
            {powerWatts}W
          </div>
          <div id="power-status" className="home-card-sub" style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.25rem' }}>
            {powerStatus}
          </div>
        </div>
      </div>

      {/* Heater Controls */}
      <div className="heater-controls" style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
        <button
          id="btn-power"
          className="control-btn"
          onClick={onPowerToggle}
          style={{
            ...buttonBaseStyle,
            background: isPowerOn ? '#111827' : '#F3F4F6',
            color: isPowerOn ? 'white' : '#4B5563'
          }}
        >
          <span className="control-icon" style={{ fontSize: '1.125rem' }}>⚡</span>
          <span>Power</span>
        </button>
        <button
          id="btn-oscillate"
          className="control-btn"
          onClick={onOscillateToggle}
          style={{
            ...buttonBaseStyle,
            background: isOscillating ? '#111827' : '#F3F4F6',
            color: isOscillating ? 'white' : '#4B5563'
          }}
        >
          <span className="control-icon" style={{ fontSize: '1.125rem' }}>🌀</span>
          <span>Oscillate</span>
        </button>
        <button
          id="btn-sleep"
          className="control-btn"
          onClick={onSleepClick}
          style={{
            ...buttonBaseStyle,
            background: sleepActive ? '#111827' : '#F3F4F6',
            color: sleepActive ? 'white' : '#4B5563'
          }}
        >
          <span className="control-icon" style={{ fontSize: '1.125rem' }}>🌙</span>
          <span>Sleep</span>
        </button>
      </div>
    </div>
  );
}
