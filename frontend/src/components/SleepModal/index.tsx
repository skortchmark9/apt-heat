import { useEffect, useRef, useState } from 'react';
import { WakeTimePicker } from './WakeTimePicker';
import { TemperatureCurve } from './TemperatureCurve';

interface SleepModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStart: (wakeTime: string, curve: { progress: number; temp: number }[]) => void;
  onCancel: () => void;
  currentTarget: number;
  sleepActive: boolean;
  sleepProgress?: number;
  serverCurve?: { progress: number; temp: number }[];
}

export function SleepModal({
  isOpen,
  onClose,
  onStart,
  onCancel,
  currentTarget,
  sleepActive,
  sleepProgress,
  serverCurve,
}: SleepModalProps) {
  const [wakeTime, setWakeTime] = useState(() =>
    localStorage.getItem('sleepWakeTime') || '7:00 AM'
  );
  const [curve, setCurve] = useState<{ progress: number; delta: number }[]>([]);
  const modalRef = useRef<HTMLDivElement>(null);

  // Save settings when they change
  useEffect(() => {
    if (wakeTime) {
      localStorage.setItem('sleepWakeTime', wakeTime);
    }
  }, [wakeTime]);

  useEffect(() => {
    if (curve.length > 0) {
      localStorage.setItem('sleepCurve', JSON.stringify(curve));
    }
  }, [curve]);

  // Close on backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === modalRef.current) {
      onClose();
    }
  };

  // Handle start/cancel
  const handleAction = () => {
    if (sleepActive) {
      onCancel();
    } else {
      // Convert deltas to absolute temps
      const absoluteCurve = curve.map(p => ({
        progress: p.progress,
        temp: Math.round(currentTarget + p.delta),
      }));
      onStart(wakeTime, absoluteCurve);
    }
  };

  // Calculate time labels for curve
  const getTimeLabels = () => {
    const now = new Date();
    const [timePart, ampm] = wakeTime.split(' ');
    const [hours, mins] = timePart.split(':').map(Number);
    let wakeHour = hours;
    if (ampm === 'PM' && hours !== 12) wakeHour += 12;
    if (ampm === 'AM' && hours === 12) wakeHour = 0;

    const wake = new Date(now);
    wake.setHours(wakeHour, mins, 0, 0);
    if (wake <= now) wake.setDate(wake.getDate() + 1);

    const duration = wake.getTime() - now.getTime();

    const formatTime = (date: Date) => {
      let h = date.getHours();
      let m = date.getMinutes();
      if (m < 15) m = 0;
      else if (m < 45) m = 30;
      else { m = 0; h = (h + 1) % 24; }
      const suffix = h >= 12 ? 'pm' : 'am';
      h = h % 12 || 12;
      return m === 0 ? `${h}${suffix}` : `${h}:30${suffix}`;
    };

    return [
      formatTime(now),
      formatTime(new Date(now.getTime() + duration * 0.25)),
      formatTime(new Date(now.getTime() + duration * 0.5)),
      formatTime(new Date(now.getTime() + duration * 0.75)),
      formatTime(wake),
    ];
  };

  if (!isOpen) return null;

  const timeLabels = getTimeLabels();

  // Calculate stats from curve
  const temps = curve.map(p => Math.round(currentTarget + p.delta));
  const startTemp = temps[0] || currentTarget;
  const minTemp = temps.length > 0 ? Math.min(...temps) : currentTarget - 5;
  const wakeTemp = temps[temps.length - 1] || currentTarget;

  return (
    <div
      ref={modalRef}
      onClick={handleBackdropClick}
      className={`fixed inset-0 bg-black/50 z-50 transition-opacity duration-300 ${
        isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
      }`}
    >
      <div
        className={`fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[428px] bg-white rounded-t-3xl z-50 max-h-[85vh] overflow-y-auto transition-transform duration-300 ${
          isOpen ? 'translate-y-0' : 'translate-y-full'
        }`}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white z-10 px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-xl font-bold">Sleep Mode</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-xl"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {/* Wake Time Picker */}
          <div className="mb-8">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
              Wake Time
            </div>
            <WakeTimePicker value={wakeTime} onChange={setWakeTime} />
          </div>

          {/* Temperature Curve */}
          <div className="mb-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
              Temperature Curve
            </div>
            <TemperatureCurve
              currentTarget={currentTarget}
              timeLabels={timeLabels}
              onChange={setCurve}
              viewOnly={sleepActive}
              progress={sleepProgress}
              serverCurve={serverCurve}
            />

            {/* Curve Stats */}
            <div className="flex gap-4 mt-4">
              <div className="flex-1 text-center py-3 bg-white rounded-lg">
                <div className="text-xl font-bold text-purple-500">{startTemp}°</div>
                <div className="text-[0.625rem] text-gray-500 mt-1">Start</div>
              </div>
              <div className="flex-1 text-center py-3 bg-white rounded-lg">
                <div className="text-xl font-bold text-purple-500">{minTemp}°</div>
                <div className="text-[0.625rem] text-gray-500 mt-1">Lowest</div>
              </div>
              <div className="flex-1 text-center py-3 bg-white rounded-lg">
                <div className="text-xl font-bold text-purple-500">{wakeTemp}°</div>
                <div className="text-[0.625rem] text-gray-500 mt-1">Wake</div>
              </div>
            </div>
          </div>

          {/* Action Button */}
          <button
            onClick={handleAction}
            className={`w-full py-4 rounded-xl text-white font-semibold text-base transition-transform active:scale-[0.98] ${
              sleepActive ? 'bg-red-500' : 'bg-purple-500'
            }`}
          >
            {sleepActive ? 'Cancel Sleep Mode' : 'Start Sleep Mode'}
          </button>
        </div>
      </div>
    </div>
  );
}
