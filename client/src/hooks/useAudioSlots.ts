import { useCallback, useEffect, useRef, useState } from "react";

import { positionMs as computePositionMs } from "../lib/clock";

interface AudioSlotsOptions {
  url: string | null;
  startAtIso: string | null;
  offsetMs: number;
  durationMs: number;
}

export interface AudioSlots {
  positionMs: number;
  isPlaying: boolean;
  toggle: () => void;
  error: Error | null;
}

/**
 * Two <audio> elements, swapped at each changeover.
 *
 * A single element would have to load the next track at the boundary, which
 * audibly gaps. The idle slot preloads the incoming track so the swap is a
 * play() call on already-buffered audio.
 */
export function useAudioSlots({
  url,
  startAtIso,
  offsetMs,
  durationMs,
}: AudioSlotsOptions): AudioSlots {
  const slotsRef = useRef<[HTMLAudioElement, HTMLAudioElement] | null>(null);
  const activeIndexRef = useRef(0);
  const loadedUrlRef = useRef<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  if (slotsRef.current === null && typeof Audio !== "undefined") {
    const make = () => {
      const element = new Audio();
      element.preload = "auto";
      // Required for the slice 4 WebAudio analyser; harmless before then.
      element.crossOrigin = "anonymous";
      return element;
    };
    slotsRef.current = [make(), make()];
  }

  // Load and seek whenever the track changes.
  useEffect(() => {
    const slots = slotsRef.current;
    if (!slots || url === null || startAtIso === null || url === loadedUrlRef.current) {
      return;
    }

    const nextIndex = (activeIndexRef.current + 1) % 2;
    const incoming = slots[nextIndex];
    const outgoing = slots[activeIndexRef.current];

    incoming.src = url;
    incoming.currentTime = computePositionMs(startAtIso, offsetMs) / 1000;
    loadedUrlRef.current = url;
    activeIndexRef.current = nextIndex;

    outgoing.pause();
    if (isPlaying) {
      incoming.play().catch((caught: unknown) => {
        setError(caught instanceof Error ? caught : new Error(String(caught)));
      });
    }
  }, [url, startAtIso, offsetMs, isPlaying]);

  // Drive the progress rail from the server clock, not from the element, so a
  // paused or buffering element still shows the station's true position.
  useEffect(() => {
    if (startAtIso === null) {
      return;
    }
    const id = setInterval(() => {
      setPosition(Math.min(computePositionMs(startAtIso, offsetMs), durationMs));
    }, 250);
    return () => clearInterval(id);
  }, [startAtIso, offsetMs, durationMs]);

  const toggle = useCallback(() => {
    const slots = slotsRef.current;
    if (!slots || startAtIso === null) {
      return;
    }
    const active = slots[activeIndexRef.current];

    if (isPlaying) {
      active.pause();
      setIsPlaying(false);
      return;
    }

    // Resuming rejoins the live station rather than continuing where it paused.
    active.currentTime = computePositionMs(startAtIso, offsetMs) / 1000;
    active
      .play()
      .then(() => setIsPlaying(true))
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught : new Error(String(caught)));
      });
  }, [isPlaying, offsetMs, startAtIso]);

  return { positionMs: position, isPlaying, toggle, error };
}
