import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useStation } from "./useStation";

const snapshot = {
  serverTime: "2026-07-28T12:00:00Z",
  current: {
    songId: "a",
    title: "Nightshift Drift",
    artist: "Sable Unit",
    descriptor: "melancholic",
    url: "https://cdn.example/tracks/a.m4a",
    startAt: "2026-07-28T12:00:00Z",
    endAt: "2026-07-28T12:00:10Z",
    durationMs: 10_000,
  },
  next: { songId: "b", status: "fallback" },
};

describe("useStation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(Date.parse("2026-07-28T12:00:00Z"));
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(snapshot), { status: 200 })),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("fetches a snapshot on mount and derives the clock offset", async () => {
    const { result } = renderHook(() => useStation("https://api.example"));

    await waitFor(() => expect(result.current.snapshot).not.toBeNull());
    expect(result.current.snapshot?.current.songId).toBe("a");
    expect(result.current.offsetMs).toBe(0);
  });

  it("polls again after the interval elapses", async () => {
    renderHook(() => useStation("https://api.example"));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect((fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(1);
  });

  it("surfaces an error when the station is not started", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 503 })));
    const { result } = renderHook(() => useStation("https://api.example"));

    await waitFor(() => expect(result.current.error).not.toBeNull());
  });
});
