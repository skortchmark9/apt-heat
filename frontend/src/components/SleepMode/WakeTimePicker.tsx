import { useRef, useEffect } from 'react';

interface WakeTimePickerProps {
  options: string[];
  selectedTime: string;
  onSelect: (time: string) => void;
}

export function WakeTimePicker({ options, selectedTime, onSelect }: WakeTimePickerProps) {
  const wheelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wheel = wheelRef.current;
    if (!wheel) return;

    // Scroll to selected time on mount
    const items = wheel.querySelectorAll<HTMLDivElement>('[data-time]');
    const target = Array.from(items).find((i) => i.dataset.time === selectedTime);
    if (target) {
      target.scrollIntoView({ block: 'center', behavior: 'instant' });
    }
  }, []);

  const handleScroll = () => {
    const wheel = wheelRef.current;
    if (!wheel) return;

    const items = wheel.querySelectorAll<HTMLDivElement>('[data-time]');
    const wheelRect = wheel.getBoundingClientRect();
    const centerY = wheelRect.top + wheelRect.height / 2;

    let closest: HTMLDivElement | null = null;
    let closestDist = Infinity;

    items.forEach((item) => {
      const rect = item.getBoundingClientRect();
      const dist = Math.abs(centerY - (rect.top + rect.height / 2));
      if (dist < closestDist) {
        closestDist = dist;
        closest = item;
      }
    });

    if (closest) {
      const time = (closest as HTMLDivElement).dataset.time;
      if (time && time !== selectedTime) {
        onSelect(time);
      }
    }
  };

  return (
    <div className="mb-8">
      <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
        Wake Time
      </div>
      <div className="relative h-[150px] overflow-hidden bg-gray-50 rounded-2xl">
        {/* Highlight bar */}
        <div className="absolute top-1/2 left-4 right-4 h-[50px] -translate-y-1/2 bg-white rounded-lg shadow-sm z-[1]" />

        {/* Scroll wheel */}
        <div
          ref={wheelRef}
          onScroll={handleScroll}
          className="h-full overflow-y-scroll scroll-snap-y hide-scrollbar scroll-smooth-touch py-[50px] px-6 relative z-[2]"
        >
          {options.map((time) => (
            <div
              key={time}
              data-time={time}
              className={`h-[50px] scroll-snap-center flex items-center justify-center text-2xl font-semibold transition-colors duration-200 ${
                time === selectedTime ? 'text-gray-900' : 'text-gray-400'
              }`}
            >
              {time}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
