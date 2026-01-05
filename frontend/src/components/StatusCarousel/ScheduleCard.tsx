export function ScheduleCard() {
  // TODO: Calculate actual schedule based on TOU rates
  const scheduleItems = [
    { time: '12am', event: 'Off-peak charging', status: 'past' as const },
    { time: 'Now', event: 'Peak hours', status: 'current' as const },
    { time: '12am', event: 'Off-peak begins', status: 'future' as const },
  ];

  return (
    <div className="flex-[0_0_100%] snap-start bg-gradient-to-br from-purple-500 to-purple-700 rounded-2xl py-3.5 px-4 text-white shadow-[0_4px_20px_rgba(139,92,246,0.3)]">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-lg">
          📅
        </div>
        <div>
          <h3 className="text-base font-semibold m-0">Today's Schedule</h3>
          <p className="text-xs opacity-90 m-0">Swipe to see events</p>
        </div>
      </div>
      <div id="schedule-timeline" className="flex flex-col gap-1.5 mt-2">
        {scheduleItems.map((item, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 text-[0.8125rem] py-1.5 px-2.5 rounded-md ${
              item.status === 'current' ? 'bg-white/25' : 'bg-white/10'
            } ${item.status === 'past' ? 'opacity-60' : ''}`}
          >
            <span className="font-semibold min-w-12">{item.time}</span>
            <span className="opacity-90">{item.event}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
