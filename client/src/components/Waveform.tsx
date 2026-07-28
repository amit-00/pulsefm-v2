import { useEffect, useRef, useState } from "react";

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
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function matchesReducedMotion(): boolean {
  // matchMedia is absent under jsdom (and, in principle, any non-browser
  // renderer). Default to full motion rather than crash or force the static
  // state on environments that can't tell us either way.
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/**
 * Tracks prefers-reduced-motion live via a change listener, so an OS-level
 * toggle mid-session is honoured on its own rather than as a side effect of
 * some unrelated, frequently re-running effect.
 */
function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(matchesReducedMotion);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const query = window.matchMedia(REDUCED_MOTION_QUERY);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);

    // Modern browsers expose EventTarget's addEventListener/removeEventListener
    // on MediaQueryList. Safari < 14 only has the deprecated
    // addListener/removeListener pair; both are typed on MediaQueryList in
    // lib.dom, so no assertion is needed to call either.
    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", onChange);
      return () => query.removeEventListener("change", onChange);
    }

    query.addListener(onChange);
    return () => query.removeListener(onChange);
  }, []);

  return reduced;
}

/**
 * Rendered to a single canvas rather than 60 animated DOM nodes, per the
 * handoff's production note. Honours prefers-reduced-motion by drawing the
 * static paused state.
 *
 * The canvas backing store is sized on mount and on real container resize
 * only (see the sizing effect below) — not per animation frame, which would
 * reallocate the buffer, implicitly clear it, and force a synchronous layout
 * read sixty times a second. Playback position is threaded through a ref
 * rather than a prop dependency so the ~4Hz position ticker doesn't tear
 * down and rebuild the rAF loop; only bar count, height, play state, and the
 * reduced-motion preference restart it.
 */
export function Waveform({ bars, height, progress, isPlaying, className }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef(progress);
  const widthRef = useRef(0);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    progressRef.current = progress;
  }, [progress]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      const cssWidth = canvas.clientWidth;
      widthRef.current = cssWidth;
      canvas.width = cssWidth * ratio;
      canvas.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [height]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const styles = getComputedStyle(document.documentElement);
    const ink = styles.getPropertyValue("--color-ink").trim() || "#111111";
    const accent = styles.getPropertyValue("--color-accent").trim() || "#D6252B";
    const animate = isPlaying && !reduceMotion;

    let frame = 0;

    const draw = (timestampMs: number) => {
      const cssWidth = widthRef.current;
      const progress = progressRef.current;
      context.clearRect(0, 0, cssWidth, height);

      const barWidth = (cssWidth - GAP_PX * (bars - 1)) / bars;
      const centre = height / 2;

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
  }, [bars, height, isPlaying, reduceMotion]);

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
