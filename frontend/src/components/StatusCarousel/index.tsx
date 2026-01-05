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
    <div
      className="status-carousel-container"
      style={{ margin: '-1rem 1rem 0', position: 'relative', zIndex: 10 }}
    >
      <div
        ref={carouselRef}
        id="status-carousel"
        className="status-carousel scrollbar-hide"
        style={{
          display: 'flex',
          overflowX: 'auto',
          scrollSnapType: 'x mandatory',
          gap: '0.75rem',
          paddingBottom: '0.5rem',
          WebkitOverflowScrolling: 'touch',
          scrollbarWidth: 'none',
          msOverflowStyle: 'none'
        }}
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
      <div
        className="carousel-dots"
        style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '0.5rem' }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="dot"
            style={{
              width: i === activeIndex ? '18px' : '6px',
              height: '6px',
              borderRadius: i === activeIndex ? '3px' : '50%',
              background: i === activeIndex ? '#8B5CF6' : '#E5E7EB',
              transition: 'all 0.2s ease'
            }}
          />
        ))}
      </div>
    </div>
  );
}
