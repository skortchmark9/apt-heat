import { useEffect, useCallback, useMemo, useState } from 'react';
import { WakeTimePicker } from './WakeTimePicker';
import { TemperatureCurve } from './TemperatureCurve';
import { useSleepCurve, WAKE_TIME_OPTIONS } from '../../hooks/useSleepCurve';
import type { SleepSchedule } from '../../types';

interface SleepModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentSetpoint: number;
  sleepSchedule: SleepSchedule | null;
  onStartSleep: (wakeTime: string, curve: { progress: number; temp: number }[]) => Promise<boolean>;
  onCancelSleep: () => Promise<void>;
}

export function SleepModal({
  isOpen,
  onClose,
  currentSetpoint,
  sleepSchedule,
  onStartSleep,
  onCancelSleep,
}: SleepModalProps) {
  const isViewingProgress = sleepSchedule?.active ?? false;
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  const {
    selectedWakeTime,
    curvePoints,
    initializeCurve,
    saveSettings,
    updateWakeTime,
    updatePoint,
    toApiCurve,
    getWakeDate,
  } = useSleepCurve(currentSetpoint);

  // Initialize curve when modal opens
  const handleInit = useCallback(
    (width: number, height: number) => {
      setCanvasSize({ width, height });
      if (!isViewingProgress) {
        initializeCurve(width, height);
      }
    },
    [initializeCurve, isViewingProgress]
  );

  // Handle point updates
  const handlePointUpdate = useCallback(
    (index: number, y: number) => {
      updatePoint(index, y, canvasSize.height);
    },
    [updatePoint, canvasSize.height]
  );

  // Save settings on drag end
  const handleDragEnd = useCallback(() => {
    saveSettings(curvePoints, canvasSize.width, canvasSize.height);
  }, [saveSettings, curvePoints, canvasSize]);

  // Calculate time labels
  const timeLabels = useMemo(() => {
    const now = new Date();
    const wake = getWakeDate();
    const duration = wake.getTime() - now.getTime();

    const formatTime = (date: Date) => {
      let h = date.getHours();
      let m = date.getMinutes();
      if (m < 15) m = 0;
      else if (m < 45) m = 30;
      else {
        m = 0;
        h = (h + 1) % 24;
      }
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
  }, [getWakeDate]);

  // Handle start/cancel button
  const handleAction = async () => {
    if (isViewingProgress) {
      await onCancelSleep();
      onClose();
    } else {
      const curve = toApiCurve(canvasSize.width, canvasSize.height);
      const success = await onStartSleep(selectedWakeTime, curve);
      if (success) {
        onClose();
      }
    }
  };

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className={`fixed inset-0 bg-black/50 z-[100] transition-opacity duration-300 ${
        isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
      }`}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className={`fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[428px] bg-white rounded-t-3xl z-[101] max-h-[85vh] overflow-y-auto transition-transform duration-300 ${
          isOpen ? 'translate-y-0' : 'translate-y-full'
        }`}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white z-10 px-6 py-6 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-xl font-bold">Sleep Mode</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full border-none bg-gray-100 text-xl cursor-pointer flex items-center justify-center"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-6">
          {!isViewingProgress && (
            <WakeTimePicker
              options={WAKE_TIME_OPTIONS}
              selectedTime={selectedWakeTime}
              onSelect={updateWakeTime}
            />
          )}

          <TemperatureCurve
            curvePoints={curvePoints}
            currentSetpoint={currentSetpoint}
            timeLabels={timeLabels}
            isViewingProgress={isViewingProgress}
            progress={sleepSchedule?.progress}
            serverCurve={sleepSchedule?.curve}
            onPointUpdate={handlePointUpdate}
            onDragEnd={handleDragEnd}
            onInit={handleInit}
          />

          <button
            onClick={handleAction}
            className={`w-full py-4 rounded-xl border-none text-base font-semibold cursor-pointer mt-4 transition-all active:scale-98 ${
              isViewingProgress
                ? 'bg-red text-white'
                : 'bg-purple text-white'
            }`}
          >
            {isViewingProgress ? 'Cancel Sleep Mode' : 'Start Sleep Mode'}
          </button>
        </div>
      </div>
    </div>
  );
}
