import { useEffect, useRef } from 'react';

interface WakeTimePickerProps {
  value: string;
  onChange: (time: string) => void;
}

// Generate wake times from 5:00 AM to 11:30 AM
const WAKE_TIMES: string[] = [];
for (let h = 5; h <= 11; h++) {
  WAKE_TIMES.push(`${h}:00 AM`);
  WAKE_TIMES.push(`${h}:30 AM`);
}

export function WakeTimePicker({ value, onChange }: WakeTimePickerProps) {
  const wheelRef = useRef<HTMLDivElement>(null);

  // Scroll to selected time on mount
  useEffect(() => {
    const wheel = wheelRef.current;
    if (!wheel) return;

    const items = wheel.querySelectorAll('[data-time]');
    const target = Array.from(items).find(
      (item) => (item as HTMLElement).dataset.time === value
    ) as HTMLElement | undefined;

    if (target) {
      // Calculate scroll position to center the item
      const wheelRect = wheel.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const scrollTop = target.offsetTop - wheelRect.height / 2 + targetRect.height / 2;
      wheel.scrollTop = scrollTop;
    }
  }, []);

  // Handle scroll to update selection
  useEffect(() => {
    const wheel = wheelRef.current;
    if (!wheel) return;

    const handleScroll = () => {
      const items = wheel.querySelectorAll('[data-time]');
      const wheelRect = wheel.getBoundingClientRect();
      const centerY = wheelRect.height / 2;

      let closest: HTMLElement | null = null;
      let closestDist = Infinity;

      items.forEach((item) => {
        const el = item as HTMLElement;
        const rect = el.getBoundingClientRect();
        const itemCenterY = rect.top - wheelRect.top + rect.height / 2;
        const dist = Math.abs(centerY - itemCenterY);
        if (dist < closestDist) {
          closestDist = dist;
          closest = el;
        }
      });

      if (closest) {
        const time = (closest as HTMLElement).dataset.time;
        if (time && time !== value) {
          onChange(time);
        }
      }
    };

    wheel.addEventListener('scroll', handleScroll);
    return () => wheel.removeEventListener('scroll', handleScroll);
  }, [value, onChange]);

  return (
    <div className="relative h-[150px] overflow-hidden bg-gray-50 rounded-2xl">
      {/* Highlight bar */}
      <div className="absolute top-1/2 left-4 right-4 h-[50px] -translate-y-1/2 bg-white rounded-lg shadow-sm z-0" />

      {/* Scroll wheel */}
      <div
        ref={wheelRef}
        className="h-full overflow-y-scroll snap-y snap-mandatory py-[50px] px-6 relative z-10 scrollbar-hide"
        style={{ WebkitOverflowScrolling: 'touch' }}
      >
        {WAKE_TIMES.map((time) => (
          <div
            key={time}
            data-time={time}
            className={`h-[50px] snap-center flex items-center justify-center text-2xl font-semibold transition-colors duration-200 ${
              time === value ? 'text-gray-900' : 'text-gray-400'
            }`}
          >
            {time}
          </div>
        ))}
      </div>
    </div>
  );
}
