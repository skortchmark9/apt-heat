interface NavItem {
  icon: string;
  label: string;
  active?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { icon: '🏠', label: 'Home', active: true },
  { icon: '📊', label: 'History' },
  { icon: '📅', label: 'Schedule' },
  { icon: '⚙️', label: 'Settings' },
];

export function BottomNav() {
  return (
    <>
      {/* Spacer to prevent content from being hidden behind nav */}
      <div className="nav-spacer" style={{ height: '80px' }} />

      <nav
        className="bottom-nav"
        style={{
          position: 'fixed',
          bottom: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '100%',
          maxWidth: '428px',
          background: 'white',
          borderTop: '1px solid #E5E7EB',
          display: 'flex',
          padding: '0.75rem 1.5rem',
          paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom, 0))'
        }}
      >
        {NAV_ITEMS.map((item) => (
          <a
            key={item.label}
            href="#"
            className={`nav-item ${item.active ? 'active' : ''}`}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.625rem',
              color: item.active ? '#8B5CF6' : '#9CA3AF',
              textDecoration: 'none'
            }}
          >
            <span className="nav-icon" style={{ fontSize: '1.5rem' }}>{item.icon}</span>
            <span>{item.label}</span>
          </a>
        ))}
      </nav>
    </>
  );
}
