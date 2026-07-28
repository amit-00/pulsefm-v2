import { timecode } from "../lib/format";

interface ProgressRailProps {
  positionMs: number;
  durationMs: number;
  showPlayhead: boolean;
  gapClassName: string;
}

export function ProgressRail({
  positionMs,
  durationMs,
  showPlayhead,
  gapClassName,
}: ProgressRailProps) {
  const fraction = durationMs > 0 ? Math.min(1, Math.max(0, positionMs / durationMs)) : 0;
  const percent = fraction * 100;

  return (
    <div className={`flex flex-1 items-center min-w-0 ${gapClassName}`}>
      <span className="font-mono text-[11px] tracking-[0.16em] text-paper/60">
        {timecode(positionMs)}
      </span>
      <div className="relative h-0.5 flex-1 bg-paper/[.18]">
        <div
          className="absolute inset-y-0 left-0 bg-paper"
          style={{ right: `${100 - percent}%` }}
        />
        {showPlayhead && (
          <div
            className="absolute -top-[3px] size-2 rounded-full bg-accent"
            style={{ left: `${percent}%` }}
          />
        )}
      </div>
      <span className="font-mono text-[11px] tracking-[0.16em] text-paper/60">
        {timecode(durationMs)}
      </span>
    </div>
  );
}
