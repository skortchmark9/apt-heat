import { useEffect, useRef, useCallback, useState } from 'react';

interface CurvePoint {
  progress: number;
  delta: number; // relative to currentTarget
}

interface TemperatureCurveProps {
  currentTarget: number;
  timeLabels: string[];
  onChange: (curve: CurvePoint[]) => void;
  viewOnly?: boolean;
  progress?: number; // 0-1 for showing current position
  serverCurve?: { progress: number; temp: number }[];
}

// Default bathtub curve shape (as deltas from setpoint)
const DEFAULT_CURVE: CurvePoint[] = [
  { progress: 0, delta: 0 },      // Start: at setpoint
  { progress: 0.12, delta: -2.5 }, // Quick drop
  { progress: 0.25, delta: -5 },   // Bottom left
  { progress: 0.5, delta: -5 },    // Bottom middle (flat)
  { progress: 0.75, delta: -5 },   // Bottom right
  { progress: 0.88, delta: -2.5 }, // Quick rise
  { progress: 1, delta: 0 },       // Wake: back to setpoint
];

export function TemperatureCurve({
  currentTarget,
  timeLabels,
  onChange,
  viewOnly = false,
  progress,
  serverCurve,
}: TemperatureCurveProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<CurvePoint[]>([]);
  const draggingRef = useRef<number | null>(null);

  // Initialize curve from localStorage or default
  useEffect(() => {
    if (serverCurve && viewOnly) {
      // Convert server curve (absolute temps) to deltas
      const curveAsDeltas = serverCurve.map(p => ({
        progress: p.progress,
        delta: p.temp - currentTarget,
      }));
      setPoints(curveAsDeltas);
      return;
    }

    const saved = localStorage.getItem('sleepCurve');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed[0]?.delta !== undefined) {
          setPoints(parsed);
          return;
        }
      } catch (e) {
        // ignore
      }
    }
    setPoints(DEFAULT_CURVE);
  }, [serverCurve, viewOnly, currentTarget]);

  // Notify parent of curve changes
  useEffect(() => {
    if (points.length > 0) {
      onChange(points);
    }
  }, [points, onChange]);

  // Draw the curve
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || points.length === 0) return;

    const rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;

    // Convert delta to Y: delta=+5 → y=0, delta=-5 → y=h
    const deltaToY = (delta: number) => ((5 - delta) / 10) * h;

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Grid lines
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      ctx.beginPath();
      ctx.moveTo(0, (h * i) / 4);
      ctx.lineTo(w, (h * i) / 4);
      ctx.stroke();
    }

    // Convert points to canvas coordinates
    const canvasPoints = points.map(p => ({
      x: p.progress * w,
      y: deltaToY(p.delta),
    }));

    // Gradient fill under curve
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, 'rgba(139, 92, 246, 0.3)');
    gradient.addColorStop(1, 'rgba(139, 92, 246, 0.05)');

    // Draw filled area
    ctx.beginPath();
    ctx.moveTo(canvasPoints[0].x, canvasPoints[0].y);
    for (let i = 1; i < canvasPoints.length; i++) {
      const prev = canvasPoints[i - 1];
      const curr = canvasPoints[i];
      const cpx = (prev.x + curr.x) / 2;
      ctx.quadraticCurveTo(prev.x, prev.y, cpx, (prev.y + curr.y) / 2);
    }
    const last = canvasPoints[canvasPoints.length - 1];
    const secondLast = canvasPoints[canvasPoints.length - 2];
    ctx.quadraticCurveTo(secondLast.x, secondLast.y, last.x, last.y);
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw curve line
    ctx.beginPath();
    ctx.moveTo(canvasPoints[0].x, canvasPoints[0].y);
    for (let i = 1; i < canvasPoints.length; i++) {
      const prev = canvasPoints[i - 1];
      const curr = canvasPoints[i];
      const cpx = (prev.x + curr.x) / 2;
      ctx.quadraticCurveTo(prev.x, prev.y, cpx, (prev.y + curr.y) / 2);
    }
    ctx.quadraticCurveTo(secondLast.x, secondLast.y, last.x, last.y);
    ctx.strokeStyle = '#8B5CF6';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Draw control points (only if not view-only)
    if (!viewOnly) {
      canvasPoints.forEach((p, i) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = i === 0 || i === canvasPoints.length - 1 ? '#10B981' : '#8B5CF6';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = 'white';
        ctx.fill();
      });
    }

    // Draw progress indicator if viewing active sleep
    if (viewOnly && progress !== undefined) {
      const progressX = progress * w;

      // Interpolate Y at progress point
      let progressY = canvasPoints[0].y;
      for (let i = 0; i < canvasPoints.length - 1; i++) {
        const p1 = canvasPoints[i];
        const p2 = canvasPoints[i + 1];
        if (progressX >= p1.x && progressX <= p2.x) {
          const t = (progressX - p1.x) / (p2.x - p1.x);
          progressY = p1.y + (p2.y - p1.y) * t;
          break;
        }
      }

      // Vertical line
      ctx.beginPath();
      ctx.moveTo(progressX, 0);
      ctx.lineTo(progressX, h);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // "You are here" dot
      ctx.beginPath();
      ctx.arc(progressX, progressY, 12, 0, Math.PI * 2);
      ctx.fillStyle = '#F59E0B';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(progressX, progressY, 6, 0, Math.PI * 2);
      ctx.fillStyle = 'white';
      ctx.fill();

      // "NOW" label
      ctx.fillStyle = '#F59E0B';
      ctx.font = 'bold 10px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('NOW', progressX, progressY - 20);
    }
  }, [points, viewOnly, progress]);

  // Redraw on changes
  useEffect(() => {
    draw();
  }, [draw]);

  // Handle pointer events for dragging
  const handlePointerDown = (e: React.PointerEvent) => {
    if (viewOnly) return;

    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const w = rect.width;
    const h = rect.height;

    // Check if clicking on a point
    for (let i = 0; i < points.length; i++) {
      const px = points[i].progress * w;
      const py = ((5 - points[i].delta) / 10) * h;
      if (Math.hypot(px - x, py - y) < 20) {
        draggingRef.current = i;
        canvas.setPointerCapture(e.pointerId);
        return;
      }
    }

    // If not on a point, move nearest middle point
    let nearestDist = Infinity;
    let nearestIdx = -1;
    for (let i = 1; i < points.length - 1; i++) {
      const px = points[i].progress * w;
      const dist = Math.abs(px - x);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearestIdx = i;
      }
    }
    if (nearestIdx >= 0) {
      const newDelta = 5 - (y / h) * 10;
      const clampedDelta = Math.max(-5, Math.min(5, newDelta));
      setPoints((prev) => {
        const updated = [...prev];
        updated[nearestIdx] = { ...updated[nearestIdx], delta: clampedDelta };
        return updated;
      });
    }
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (draggingRef.current === null || viewOnly) return;

    const container = containerRef.current;
    if (!container) return;

    const rect = container.getBoundingClientRect();
    const y = e.clientY - rect.top;
    const h = rect.height;

    const newDelta = 5 - (y / h) * 10;
    const clampedDelta = Math.max(-5, Math.min(5, newDelta));

    setPoints((prev) => {
      const updated = [...prev];
      updated[draggingRef.current!] = {
        ...updated[draggingRef.current!],
        delta: clampedDelta,
      };
      return updated;
    });
  };

  const handlePointerUp = () => {
    draggingRef.current = null;
  };

  return (
    <div className="bg-gray-50 rounded-2xl p-4 relative">
      {/* Y-axis temp labels */}
      <div className="absolute left-2 top-4 bottom-10 flex flex-col justify-between text-[0.625rem] text-gray-400">
        <span>{currentTarget + 5}°</span>
        <span>{currentTarget}°</span>
        <span>{currentTarget - 5}°</span>
      </div>

      {/* Canvas container */}
      <div ref={containerRef} className="ml-6 h-[200px]">
        <canvas
          ref={canvasRef}
          className="w-full h-full rounded-lg touch-none cursor-crosshair"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        />
      </div>

      {/* X-axis time labels */}
      <div className="flex justify-between mt-2 ml-6 text-[0.625rem] text-gray-400 uppercase">
        {timeLabels.map((label, i) => (
          <span key={i}>{label}</span>
        ))}
      </div>
    </div>
  );
}
