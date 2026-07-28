import { useCallback, useEffect, useRef, useState } from "react";

import { fetchState } from "../lib/api";
import { computeOffsetMs } from "../lib/clock";
import type { StateSnapshot } from "../lib/types";

const POLL_INTERVAL_MS = 2000;
const POLL_JITTER_MS = 500;
const BOUNDARY_WAKE_MS = 300;

export interface StationState {
  snapshot: StateSnapshot | null;
  offsetMs: number;
  error: Error | null;
}

/**
 * Poll the station snapshot.
 *
 * Three things schedule a fetch: a 2s interval with jitter (jitter keeps a
 * thousand listeners from hitting the origin on the same tick), and a wake
 * shortly after the known song boundary so changeovers feel immediate rather
 * than up to a poll-interval late.
 */
export function useStation(baseUrl: string): StationState {
  const [snapshot, setSnapshot] = useState<StateSnapshot | null>(null);
  const [offsetMs, setOffsetMs] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = useCallback(
    async (signal: AbortSignal) => {
      try {
        const received = Date.now();
        const next = await fetchState(baseUrl, signal);
        if (signal.aborted) {
          return next;
        }
        setSnapshot(next);
        setOffsetMs(computeOffsetMs(next.serverTime, received));
        setError(null);
        return next;
      } catch (caught) {
        if (signal.aborted) {
          return null;
        }
        setError(caught instanceof Error ? caught : new Error(String(caught)));
        return null;
      }
    },
    [baseUrl],
  );

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    const schedule = (delayMs: number) => {
      if (cancelled) {
        return;
      }
      timerRef.current = setTimeout(run, Math.max(0, delayMs));
    };

    const run = async () => {
      const next = await poll(controller.signal);
      if (cancelled) {
        return;
      }

      const interval = POLL_INTERVAL_MS + Math.random() * POLL_JITTER_MS;
      if (next === null) {
        schedule(interval);
        return;
      }

      // Wake just after the boundary if it lands sooner than the next interval.
      const received = Date.now();
      const correctedNow = received + computeOffsetMs(next.serverTime, received);
      const untilBoundary =
        Date.parse(next.current.endAt) - correctedNow + BOUNDARY_WAKE_MS;
      schedule(untilBoundary > 0 ? Math.min(interval, untilBoundary) : interval);
    };

    void run();

    return () => {
      cancelled = true;
      controller.abort();
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, [poll]);

  return { snapshot, offsetMs, error };
}
