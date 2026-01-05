interface HeroProps {
  savingsToday?: number;
  streakDays?: number | null;
}

export function Hero({ savingsToday = 0, streakDays = null }: HeroProps) {
  return (
    <div className="bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] text-white px-6 pt-6 pb-5 relative">
      <div className="flex justify-between items-start mb-2">
        <div className="text-[0.875rem] opacity-90">Saved today</div>
        <div className="flex items-center gap-[0.375rem] bg-[rgba(255,255,255,0.2)] px-3 py-[0.375rem] rounded-full text-xs font-semibold">
          <span id="streak-count">{streakDays ?? '--'}</span>
          <span>day streak</span>
        </div>
      </div>
      <div
        id="savings-today"
        className="text-[4rem] font-bold tracking-[-0.03em] leading-none mb-1"
      >
        ${savingsToday.toFixed(2)}
      </div>
      <div className="text-base opacity-90">during peak hours</div>
    </div>
  );
}
