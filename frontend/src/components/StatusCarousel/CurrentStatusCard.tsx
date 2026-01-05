import type { HeaterStatus, SleepSchedule, SavingsData } from '../../types';

interface CurrentStatusCardProps {
  status: HeaterStatus | null;
  sleepSchedule: SleepSchedule | null;
  savings: SavingsData | null;
  onClick?: () => void;
}

export function CurrentStatusCard({ status, sleepSchedule, savings, onClick }: CurrentStatusCardProps) {
  const isOff = !status?.power;
  const isHeating = status?.power && (status?.power_watts ?? 0) > 0;
  const isSleepActive = sleepSchedule?.active;

  // Determine card style
  let cardBackground = 'linear-gradient(135deg, #10B981 0%, #059669 100%)';
  let cardShadow = '0 4px 20px rgba(16, 185, 129, 0.3)';

  if (isSleepActive) {
    cardBackground = 'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)';
    cardShadow = '0 4px 20px rgba(139, 92, 246, 0.3)';
  } else if (isOff) {
    cardBackground = 'linear-gradient(135deg, #9CA3AF 0%, #6B7280 100%)';
    cardShadow = '0 4px 20px rgba(107, 114, 128, 0.3)';
  } else if (isHeating) {
    cardBackground = 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)';
    cardShadow = '0 4px 20px rgba(245, 158, 11, 0.3)';
  }

  // Determine icon and text
  let icon = '✅';
  let title = 'Temperature reached';
  let subtitle = `Maintaining ${status?.target_temp_f ?? '--'}°F`;

  if (isSleepActive && sleepSchedule) {
    icon = '🌙';
    title = 'Sleep mode active';
    const wakeDate = new Date(sleepSchedule.wake_time!);
    const wakeStr = wakeDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    subtitle = `Target: ${sleepSchedule.current_target}°F · Wake: ${wakeStr}`;
  } else if (isOff) {
    icon = '⏸️';
    title = 'Heater is off';
    subtitle = 'Tap Power to turn on';
  } else if (isHeating) {
    icon = '🔥';
    title = 'Heating your home';
    subtitle = `Target: ${status?.target_temp_f ?? '--'}°F`;
  } else if (!status) {
    icon = '⏳';
    title = 'Loading...';
    subtitle = 'Checking heater status';
  }

  const gridRate = savings?.current_rate ?? 0.35;
  const offpeakRate = 0.0249;

  return (
    <div
      id="status-card"
      className="status-card"
      onClick={onClick}
      style={{
        flex: '0 0 100%',
        scrollSnapAlign: 'start',
        background: cardBackground,
        borderRadius: '16px',
        padding: '0.875rem 1rem',
        color: 'white',
        boxShadow: cardShadow,
        cursor: onClick ? 'pointer' : 'default'
      }}
    >
      <div
        className="status-top"
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}
      >
        <div
          id="status-icon"
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
          {icon}
        </div>
        <div className="status-text">
          <h3 id="status-title" style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>
            {title}
          </h3>
          <p id="status-subtitle" style={{ fontSize: '0.75rem', opacity: 0.9, margin: 0 }}>
            {subtitle}
          </p>
        </div>
      </div>
      <div
        className="rate-comparison"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(255,255,255,0.15)',
          borderRadius: '8px',
          padding: '0.5rem 0.75rem'
        }}
      >
        <div className="rate-item" style={{ textAlign: 'center' }}>
          <div
            className="rate-label"
            style={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em', opacity: 0.8 }}
          >
            Grid rate
          </div>
          <div
            id="grid-rate"
            className="rate-value crossed"
            style={{ fontSize: '1.25rem', fontWeight: 700, textDecoration: 'line-through', opacity: 0.7 }}
          >
            ${gridRate.toFixed(2)}
          </div>
        </div>
        <div className="rate-arrow" style={{ fontSize: '1.25rem', opacity: 0.6 }}>→</div>
        <div className="rate-item" style={{ textAlign: 'center' }}>
          <div
            className="rate-label"
            style={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em', opacity: 0.8 }}
          >
            You pay
          </div>
          <div id="your-rate" className="rate-value" style={{ fontSize: '1.25rem', fontWeight: 700 }}>
            ${offpeakRate.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  );
}
