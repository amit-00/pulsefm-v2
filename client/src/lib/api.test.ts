import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchState, StationUnavailableError } from "./api";
import type { StateSnapshot } from "./types";

const snapshot: StateSnapshot = {
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchState", () => {
  it("returns the parsed snapshot on success", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(snapshot), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchState("https://api.example.com");

    expect(result).toEqual(snapshot);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/v1/state",
      expect.anything(),
    );
  });

  it("does not double a trailing slash on the base URL", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(snapshot), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchState("https://api.example.com/");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/v1/state",
      expect.anything(),
    );
  });

  it("throws StationUnavailableError with the not-started message on 503", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchState("https://api.example.com")).rejects.toMatchObject({
      status: 503,
      message: "The station has not started yet.",
    });
    await expect(fetchState("https://api.example.com")).rejects.toBeInstanceOf(
      StationUnavailableError,
    );
  });

  it("throws StationUnavailableError with the status but not the not-started message on a non-503 failure", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    const error = await fetchState("https://api.example.com").catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(StationUnavailableError);
    expect((error as StationUnavailableError).status).toBe(500);
    expect((error as StationUnavailableError).message).not.toBe(
      "The station has not started yet.",
    );
  });
});
