import { PlayGlyph } from "./PlayGlyph";
import { ProgressRail } from "./ProgressRail";

interface TransportSheetProps {
  variant: "desktop" | "mobile";
  title: string;
  artist: string;
  positionMs: number;
  durationMs: number;
  isPlaying: boolean;
  onToggle: () => void;
}

export function TransportSheet({
  variant,
  title,
  artist,
  positionMs,
  durationMs,
  isPlaying,
  onToggle,
}: TransportSheetProps) {
  const label = isPlaying ? "Pause" : "Play";

  if (variant === "desktop") {
    return (
      <div className="absolute inset-x-0 bottom-0 flex h-[126px] items-center gap-10 bg-ink px-11 text-paper">
        <button
          type="button"
          aria-label={label}
          onClick={onToggle}
          className="grid size-[66px] flex-none cursor-pointer place-items-center rounded-full bg-accent transition-transform duration-150 hover:scale-105"
        >
          <PlayGlyph isPlaying={isPlaying} />
        </button>
        <ProgressRail
          positionMs={positionMs}
          durationMs={durationMs}
          showPlayhead
          gapClassName="gap-4"
        />
      </div>
    );
  }

  return (
    <div className="rounded-t-[34px] rounded-b-[46px] bg-ink px-[30px] pt-[30px] pb-10 text-paper">
      <div className="flex items-center justify-between gap-5">
        <div className="min-w-0">
          <div className="truncate text-[23px] font-medium tracking-[-0.02em]">{title}</div>
          <div className="mt-[7px] font-mono text-[12px] tracking-[0.20em] text-paper/50 uppercase">
            {artist}
          </div>
        </div>
        <button
          type="button"
          aria-label={label}
          onClick={onToggle}
          className="grid size-16 flex-none cursor-pointer place-items-center rounded-full bg-accent transition-transform duration-150 hover:scale-105"
        >
          <PlayGlyph isPlaying={isPlaying} />
        </button>
      </div>
      <div className="mt-[26px]">
        <ProgressRail
          positionMs={positionMs}
          durationMs={durationMs}
          showPlayhead={false}
          gapClassName="gap-3.5"
        />
      </div>
    </div>
  );
}
