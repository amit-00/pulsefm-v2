import { useAudioSlots } from "../hooks/useAudioSlots";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { StateSnapshot } from "../lib/types";
import { Header } from "./Header";
import { TransportSheet } from "./TransportSheet";
import { Waveform } from "./Waveform";

interface PlayerProps {
  snapshot: StateSnapshot | null;
  offsetMs: number;
}

// The handoff specifies two discrete viewport targets, not a fluid range, so
// one threshold is the right model — not a set of independent breakpoints.
const DESKTOP_QUERY = "(min-width: 768px)";

export function Player({ snapshot, offsetMs }: PlayerProps) {
  const current = snapshot?.current ?? null;
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const { positionMs, isPlaying, toggle } = useAudioSlots({
    url: current?.url ?? null,
    startAtIso: current?.startAt ?? null,
    offsetMs,
    durationMs: current?.durationMs ?? 0,
  });

  if (current === null) {
    return (
      <div className="grid h-full place-items-center font-mono text-[11px] tracking-[0.22em] text-ink/45 uppercase">
        Tuning in…
      </div>
    );
  }

  const progress = current.durationMs > 0 ? positionMs / current.durationMs : 0;

  // Only the matching composition mounts. Each owns a Waveform, whose rAF
  // loop has no visibility check of its own — keeping both trees mounted
  // (as CSS-only `md:hidden` toggling would) would run two independent
  // animation loops with one permanently invisible.
  if (isDesktop) {
    return (
      <div className="relative flex h-full flex-col bg-bone text-ink">
        <Header variant="desktop" />
        <div className="flex flex-1 flex-col items-center justify-center gap-[34px] pb-10">
          <div className="text-center">
            <div className="text-[56px] font-medium tracking-[-0.035em]">{current.title}</div>
            <div className="mt-[14px] font-mono text-[12px] tracking-[0.24em] text-ink/45">
              {`${current.artist} / WAVEFORM STEREO`.toUpperCase()}
            </div>
          </div>
          <Waveform bars={60} height={260} progress={progress} isPlaying={isPlaying} />
        </div>
        <div className="h-[126px]" />
        <TransportSheet
          variant="desktop"
          title={current.title}
          artist={current.artist.toUpperCase()}
          positionMs={positionMs}
          durationMs={current.durationMs}
          isPlaying={isPlaying}
          onToggle={toggle}
        />
      </div>
    );
  }

  return (
    <div className="relative flex h-full flex-col bg-bone text-ink">
      <Header variant="mobile" />
      <div className="flex flex-1 flex-col justify-center gap-6">
        <div className="px-[30px] font-mono text-[11px] tracking-[0.22em] text-ink/45">
          WAVEFORM / STEREO
        </div>
        <Waveform bars={30} height={190} progress={progress} isPlaying={isPlaying} />
      </div>
      <TransportSheet
        variant="mobile"
        title={current.title}
        artist={current.artist.toUpperCase()}
        positionMs={positionMs}
        durationMs={current.durationMs}
        isPlaying={isPlaying}
        onToggle={toggle}
      />
    </div>
  );
}
