import { useState, useRef, useEffect } from 'react';
import { CurrentStatusCard } from './CurrentStatusCard';
import { ScheduleCard } from './ScheduleCard';
import { BatteryCard } from './BatteryCard';
import type { HeaterStatus, SleepSchedule, SavingsData } from '../../types';

interface StatusCarouselProps {
  status: HeaterStatus | null;
  sleepSchedule: SleepSchedule | null;
  savings: SavingsData | null;
  onSleepCardClick?: () => void;
}

export function StatusCarousel({ status, sleepSchedule, savings, onSleepCardClick }: StatusCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const carouselRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const carousel = carouselRef.current;
    if (!carousel) return;

    const handleScroll = () => {
      const scrollLeft = carousel.scrollLeft;
      const cardWidth = carousel.offsetWidth;
      const newIndex = Math.round(scrollLeft / cardWidth);
      setActiveIndex(newIndex);
    };

    carousel.addEventListener('scroll', handleScroll);
    return () => carousel.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="-mt-4 mx-4 relative z-10">
      <div
        ref={carouselRef}
        id="status-carousel"
        className="flex overflow-x-auto snap-x snap-mandatory gap-3 pb-2 scrollbar-hide"
        style={{ WebkitOverflowScrolling: 'touch' }}
      >
        <CurrentStatusCard
          status={status}
          sleepSchedule={sleepSchedule}
          savings={savings}
          onClick={sleepSchedule?.active ? onSleepCardClick : undefined}
        />
        <ScheduleCard />
        <BatteryCard />
      </div>
      <div className="flex justify-center gap-2 mt-2">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-1.5 rounded-sm transition-all duration-200 ${
              i === activeIndex
                ? 'w-[18px] bg-purple-500'
                : 'w-1.5 rounded-full bg-gray-200'
            }`}
          />
        ))}
      </div>
    </div>
  );
}
