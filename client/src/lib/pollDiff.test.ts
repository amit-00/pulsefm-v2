import { describe, expect, it } from "vitest";

import { diffSnapshots } from "./pollDiff";
import type { StateSnapshot } from "./types";

const base: StateSnapshot = {
  serverTime: "2026-07-28T12:00:00Z",
  current: {
    songId: "a",
    title: "Nightshift Drift",
    artist: "Sable Unit",
    descriptor: "melancholic",
    url: "https://cdn.example/tracks/a.m4a",
    startAt: "2026-07-28T12:00:00Z",
    endAt: "2026-07-28T12:03:52Z",
    durationMs: 232_000,
  },
  next: { songId: "b", status: "fallback" },
};

describe("diffSnapshots", () => {
  it("reports no change against an identical snapshot", () => {
    expect(diffSnapshots(base, base)).toEqual({ songChanged: false, nextSongChanged: false });
  });

  it("detects a song change by id", () => {
    const next = { ...base, current: { ...base.current, songId: "b" } };
    expect(diffSnapshots(base, next).songChanged).toBe(true);
  });

  it("detects a queued song change", () => {
    const next = { ...base, next: { songId: "c", status: "fallback" as const } };
    expect(diffSnapshots(base, next).nextSongChanged).toBe(true);
  });

  it("treats the first snapshot as a song change", () => {
    expect(diffSnapshots(null, base).songChanged).toBe(true);
  });
});
