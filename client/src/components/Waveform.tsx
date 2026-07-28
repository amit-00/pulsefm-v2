import { useEffect, useRef } from "react";

/**
 * Deterministic bar-height profile from the design handoff.
 *
 * Fixed rather than random so the silhouette is stable across renders. Slice 4
 * replaces this with real WebAudio analyser data.
 */
export function barAmplitude(index: number): number {
  const i = index * 1.3;
  return 0.28 + 0.72 * Math.abs(Math.sin(i * 1.7 + Math.cos(i * 0.6)));
}

interface WaveformProps {
  bars: number;
  height: number;
  /** Playback progress through the track, 0 to 1. Drives the playhead bar. */
  progress: number;
  isPlaying: boolean;
  className?: string;
}

const GAP_PX = 3;
const PLAYHEAD_HALF_WIDTH = 0.02;

/**
 * Rendered to a single canvas rather than 60 animated DOM nodes, per the
 * handoff's production note. Honours prefers-reduced-motion by drawing the
 * static paused state.
 */
export function Waveform({ bars, height, progress, isPlaying, className }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const styles = getComputedStyle(document.documentElement);
    const ink = styles.getPropertyValue("--color-ink").trim() || "#111111";
    const accent = styles.getPropertyValue("--color-accent").trim() || "#D6252B";

    let frame = 0;

    const draw = (timestampMs: number) => {
      const ratio = window.devicePixelRatio || 1;
      const cssWidth = canvas.clientWidth;
      canvas.width = cssWidth * ratio;
      canvas.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, cssWidth, height);

      const barWidth = (cssWidth - GAP_PX * (bars - 1)) / bars;
      const centre = height / 2;
      const animate = isPlaying && !reduceMotion;

      for (let i = 0; i < bars; i += 1) {
        const position = i / bars;
        let scale = 1;

        if (animate) {
          // mirrorPulse: scaleY .18 -> 1 -> .18, six interleaved tempos with a
          // left-to-right ripple, matching the handoff's keyframe timings.
          const durationS = 1.2 + (i % 6) * 0.09;
          const delayS = i * 0.035;
          const phase = ((timestampMs / 1000 - delayS) / durationS) % 1;
          const eased = 0.5 - 0.5 * Math.cos(2 * Math.PI * (phase < 0 ? phase + 1 : phase));
          scale = 0.18 + 0.82 * eased;
        }

        const barHeight = barAmplitude(i) * height * scale;

        if (position > progress - PLAYHEAD_HALF_WIDTH && position < progress) {
          context.fillStyle = accent;
          context.globalAlpha = 1;
        } else if (position > progress) {
          context.fillStyle = ink;
          context.globalAlpha = 0.22;
        } else {
          context.fillStyle = ink;
          context.globalAlpha = isPlaying ? 1 : 0.5;
        }

        context.fillRect(
          i * (barWidth + GAP_PX),
          centre - barHeight / 2,
          barWidth,
          barHeight,
        );
      }

      context.globalAlpha = 1;
      if (animate) {
        frame = requestAnimationFrame(draw);
      }
    };

    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [bars, height, progress, isPlaying]);

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label="Waveform visualiser"
      style={{ height }}
      className={`w-full ${className ?? ""}`}
    />
  );
}
