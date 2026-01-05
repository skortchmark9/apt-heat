import { useRef, useEffect, useCallback, useState } from 'react';
import type { CurvePoint, SleepCurvePoint } from '../../types';

interface TemperatureCurveProps {
  curvePoints: CurvePoint[];
  currentSetpoint: number;
  timeLabels: string[];
  isViewingProgress?: boolean;
  progress?: number;
  serverCurve?: SleepCurvePoint[];
  onPointUpdate: (index: number, y: number) => void;
  onDragEnd: () => void;
  onInit: (width: number, height: number) => void;
}

export function TemperatureCurve({
  curvePoints,
  currentSetpoint,
  timeLabels,
  isViewingProgress = false,
  progress = 0,
  serverCurve,
  onPointUpdate,
  onDragEnd,
  onInit,
}: TemperatureCurveProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [draggingPoint, setDraggingPoint] = useState<number | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  // Initialize canvas and points
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    setCanvasSize({ width: rect.width, height: rect.height });
    onInit(rect.width, rect.height);
  }, [onInit]);

  // Draw the curve
  const drawCurve = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || curvePoints.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width: w, height: h } = canvasSize;
    ctx.setTransform(2, 0, 0, 2, 0, 0);
    ctx.clearRect(0, 0, w, h);

    // Get points to draw (either curve points or server curve for progress view)
    let points = curvePoints;
    if (isViewingProgress && serverCurve) {
      const tempToY = (temp: number) => ((currentSetpoint + 5 - temp) / 10) * h;
      points = serverCurve.map((p) => ({
        x: p.progress * w,
        y: tempToY(p.temp),
      }));
    }

    // Draw grid
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      ctx.beginPath();
      ctx.moveTo(0, (h * i) / 4);
      ctx.lineTo(w, (h * i) / 4);
      ctx.stroke();
    }

    // Create gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, 'rgba(139, 92, 246, 0.3)');
    gradient.addColorStop(1, 'rgba(139, 92, 246, 0.05)');

    // Draw smooth curve with fill
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cpx = (prev.x + curr.x) / 2;
      ctx.quadraticCurveTo(prev.x, prev.y, cpx, (prev.y + curr.y) / 2);
    }
    const last = points[points.length - 1];
    const secondLast = points[points.length - 2];
    ctx.quadraticCurveTo(secondLast.x, secondLast.y, last.x, last.y);
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cpx = (prev.x + curr.x) / 2;
      ctx.quadraticCurveTo(prev.x, prev.y, cpx, (prev.y + curr.y) / 2);
    }
    ctx.quadraticCurveTo(secondLast.x, secondLast.y, last.x, last.y);
    ctx.strokeStyle = '#8B5CF6';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Draw control points (only if not viewing progress)
    if (!isViewingProgress) {
      points.forEach((p, i) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = i === 0 || i === points.length - 1 ? '#10B981' : '#8B5CF6';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = 'white';
        ctx.fill();
      });
    }

    // Draw progress indicator if viewing active sleep
    if (isViewingProgress && progress !== undefined) {
      const progressX = progress * w;

      // Find Y position by interpolating
      let progressY = points[0].y;
      for (let i = 0; i < points.length - 1; i++) {
        const p1 = points[i];
        const p2 = points[i + 1];
        if (progressX >= p1.x && progressX <= p2.x) {
          const t = (progressX - p1.x) / (p2.x - p1.x);
          progressY = p1.y + (p2.y - p1.y) * t;
          break;
        }
      }

      // Draw vertical line
      ctx.beginPath();
      ctx.moveTo(progressX, 0);
      ctx.lineTo(progressX, h);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw "you are here" dot
      ctx.beginPath();
      ctx.arc(progressX, progressY, 12, 0, Math.PI * 2);
      ctx.fillStyle = '#F59E0B';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(progressX, progressY, 6, 0, Math.PI * 2);
      ctx.fillStyle = 'white';
      ctx.fill();

      // Draw "NOW" label
      ctx.fillStyle = '#F59E0B';
      ctx.font = 'bold 10px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('NOW', progressX, progressY - 20);
    }
  }, [curvePoints, canvasSize, currentSetpoint, isViewingProgress, progress, serverCurve]);

  useEffect(() => {
    drawCurve();
  }, [drawCurve]);

  // Handle pointer events for dragging
  const handlePointerDown = (e: React.PointerEvent) => {
    if (isViewingProgress) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Check if clicking on a point
    for (let i = 0; i < curvePoints.length; i++) {
      const p = curvePoints[i];
      if (Math.hypot(p.x - x, p.y - y) < 20) {
        setDraggingPoint(i);
        canvas.setPointerCapture(e.pointerId);
        return;
      }
    }

    // If not on a point, move nearest middle point
    let nearestDist = Infinity;
    let nearestIdx = -1;
    for (let i = 1; i < curvePoints.length - 1; i++) {
      const dist = Math.abs(curvePoints[i].x - x);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearestIdx = i;
      }
    }
    if (nearestIdx >= 0) {
      onPointUpdate(nearestIdx, Math.max(10, Math.min(canvasSize.height - 10, y)));
    }
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (draggingPoint === null) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const y = e.clientY - rect.top;
    onPointUpdate(draggingPoint, Math.max(10, Math.min(canvasSize.height - 10, y)));
  };

  const handlePointerUp = () => {
    if (draggingPoint !== null) {
      setDraggingPoint(null);
      onDragEnd();
    }
  };

  // Calculate curve stats
  const getCurveStats = () => {
    if (curvePoints.length === 0) return { start: 0, min: 0, wake: 0 };
    const h = canvasSize.height;
    const yToDelta = (y: number) => 5 - (y / h) * 10;
    const deltas = curvePoints.map((p) => yToDelta(p.y));
    const temps = deltas.map((d) => Math.round(currentSetpoint + d));
    return {
      start: temps[0],
      min: Math.min(...temps),
      wake: temps[temps.length - 1],
    };
  };

  const stats = getCurveStats();

  return (
    <div className="mb-6">
      <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
        Temperature Curve
      </div>
      <div className="bg-gray-50 rounded-2xl p-4 relative">
        {/* Y-axis labels */}
        <div className="absolute left-2 top-4 bottom-10 flex flex-col justify-between text-[10px] text-gray-400">
          <span>{currentSetpoint + 5}°</span>
          <span>{currentSetpoint}°</span>
          <span>{currentSetpoint - 5}°</span>
        </div>

        {/* Canvas */}
        <canvas
          ref={canvasRef}
          className="w-full h-[200px] rounded-lg canvas-touch cursor-crosshair"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        />

        {/* X-axis labels */}
        <div className="flex justify-between mt-2 text-[10px] text-gray-400 uppercase">
          {timeLabels.map((label, i) => (
            <span key={i}>{label}</span>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 mt-4">
        <div className="flex-1 text-center py-3 bg-white rounded-lg">
          <div className="text-xl font-bold text-purple">{stats.start}°</div>
          <div className="text-[10px] text-gray-500 mt-1">Start</div>
        </div>
        <div className="flex-1 text-center py-3 bg-white rounded-lg">
          <div className="text-xl font-bold text-purple">{stats.min}°</div>
          <div className="text-[10px] text-gray-500 mt-1">Lowest</div>
        </div>
        <div className="flex-1 text-center py-3 bg-white rounded-lg">
          <div className="text-xl font-bold text-purple">{stats.wake}°</div>
          <div className="text-[10px] text-gray-500 mt-1">Wake</div>
        </div>
      </div>
    </div>
  );
}
