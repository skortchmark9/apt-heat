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
      <div className="h-20" />

      <nav
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[428px] bg-white border-t border-gray-200 flex px-6 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom,0))]"
      >
        {NAV_ITEMS.map((item) => (
          <a
            key={item.label}
            href="#"
            className={`flex-1 flex flex-col items-center gap-1 text-[0.625rem] no-underline ${
              item.active ? 'text-purple-500' : 'text-gray-400'
            }`}
          >
            <span className="text-2xl">{item.icon}</span>
            <span>{item.label}</span>
          </a>
        ))}
      </nav>
    </>
  );
}
