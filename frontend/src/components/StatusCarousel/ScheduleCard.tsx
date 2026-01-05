export function ScheduleCard() {
  // TODO: Calculate actual schedule based on TOU rates
  const scheduleItems = [
    { time: '12am', event: 'Off-peak charging', status: 'past' as const },
    { time: 'Now', event: 'Peak hours', status: 'current' as const },
    { time: '12am', event: 'Off-peak begins', status: 'future' as const },
  ];

  return (
    <div
      className="status-card schedule-card"
      style={{
        flex: '0 0 100%',
        scrollSnapAlign: 'start',
        background: 'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)',
        borderRadius: '16px',
        padding: '0.875rem 1rem',
        color: 'white',
        boxShadow: '0 4px 20px rgba(139, 92, 246, 0.3)'
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
          📅
        </div>
        <div className="status-text">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Today's Schedule</h3>
          <p style={{ fontSize: '0.75rem', opacity: 0.9, margin: 0 }}>Swipe to see events</p>
        </div>
      </div>
      <div
        id="schedule-timeline"
        className="schedule-timeline"
        style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', marginTop: '0.5rem' }}
      >
        {scheduleItems.map((item, i) => (
          <div
            key={i}
            className={`timeline-item ${item.status}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              fontSize: '0.8125rem',
              padding: '0.375rem 0.625rem',
              borderRadius: '6px',
              background: item.status === 'current' ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.1)',
              opacity: item.status === 'past' ? 0.6 : 1
            }}
          >
            <span className="time" style={{ fontWeight: 600, minWidth: '3rem' }}>{item.time}</span>
            <span className="event" style={{ opacity: 0.9 }}>{item.event}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
