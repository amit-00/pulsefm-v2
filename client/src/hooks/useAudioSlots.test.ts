import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAudioSlots } from "./useAudioSlots";

/**
 * jsdom does not implement `HTMLMediaElement.play()` (it throws
 * "Not implemented"), so it must be stubbed for any test that touches
 * useAudioSlots. We also intercept the `Audio` constructor so the test can
 * reach the two underlying slot elements the hook creates internally.
 */
let audioInstances: HTMLAudioElement[];
let playSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse("2026-07-28T12:00:00Z"));

  audioInstances = [];
  class TrackedAudio extends Audio {
    constructor() {
      super();
      audioInstances.push(this);
    }
  }
  vi.stubGlobal("Audio", TrackedAudio);

  playSpy = vi.fn().mockResolvedValue(undefined);
  HTMLMediaElement.prototype.play = playSpy;
  HTMLMediaElement.prototype.pause = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useAudioSlots", () => {
  it("seeks the incoming element to the current server position rather than 0", () => {
    // Station started 5s before "now", so the correct seek is 5s, not 0.
    const startAtIso = "2026-07-28T11:59:55Z";

    renderHook(() =>
      useAudioSlots({
        url: "https://cdn.example/tracks/a.m4a",
        startAtIso,
        offsetMs: 0,
        durationMs: 60_000,
      }),
    );

    // The hook loads the incoming track into the second slot on first mount
    // (activeIndexRef starts at 0, so it swaps to index 1).
    const incoming = audioInstances[1];
    expect(incoming.src).toBe("https://cdn.example/tracks/a.m4a");
    expect(incoming.currentTime).toBe(5);
  });

  it("re-seeks to live before playing when toggled from paused", () => {
    const startAtIso = "2026-07-28T11:59:55Z";

    const { result } = renderHook(() =>
      useAudioSlots({
        url: "https://cdn.example/tracks/a.m4a",
        startAtIso,
        offsetMs: 0,
        durationMs: 60_000,
      }),
    );

    // Let the station clock move on past the initial mount-time seek.
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    act(() => {
      result.current.toggle();
    });

    const active = audioInstances[1];
    // Live position is now 7s (5s at mount + 2s elapsed), not the stale 5s
    // from mount, and not wherever a paused element happened to be left.
    expect(active.currentTime).toBe(7);
    expect(playSpy).toHaveBeenCalledTimes(1);
  });
});
