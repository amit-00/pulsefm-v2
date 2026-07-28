import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Player } from "./Player";
import type { StateSnapshot } from "../lib/types";

const snapshot: StateSnapshot = {
  serverTime: "2026-07-28T12:01:00Z",
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

/**
 * Stubs matchMedia so Player's `useMediaQuery(DESKTOP_QUERY)` resolves to a
 * chosen value, mirroring the stub Waveform.test.tsx uses for
 * prefers-reduced-motion.
 */
function stubMatchMedia(matches: boolean): void {
  const mediaQueryList: MediaQueryList = {
    matches,
    media: "(min-width: 768px)",
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  };
  vi.stubGlobal(
    "matchMedia",
    vi.fn((): MediaQueryList => mediaQueryList),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Player", () => {
  it("renders the track identity and the desktop sub-label", () => {
    stubMatchMedia(true);
    render(<Player snapshot={snapshot} offsetMs={0} />);

    expect(screen.getByText("Nightshift Drift")).toBeInTheDocument();
    expect(screen.getByText("SABLE UNIT / WAVEFORM STEREO")).toBeInTheDocument();
  });

  it("shows a waiting message before the first snapshot", () => {
    stubMatchMedia(true);
    render(<Player snapshot={null} offsetMs={0} />);

    expect(screen.getByText(/tuning in/i)).toBeInTheDocument();
  });

  it("renders only the mobile composition when the desktop query does not match", () => {
    stubMatchMedia(false);
    render(<Player snapshot={snapshot} offsetMs={0} />);

    // Mobile carries the artist bare (TransportSheet), not the desktop's
    // "ARTIST / WAVEFORM STEREO" sub-label.
    expect(screen.getByText("SABLE UNIT")).toBeInTheDocument();
    expect(screen.queryByText("SABLE UNIT / WAVEFORM STEREO")).not.toBeInTheDocument();
    expect(screen.getByText("WAVEFORM / STEREO")).toBeInTheDocument();
  });

  it("renders only the desktop composition when the desktop query matches", () => {
    stubMatchMedia(true);
    render(<Player snapshot={snapshot} offsetMs={0} />);

    expect(screen.getByText("SABLE UNIT / WAVEFORM STEREO")).toBeInTheDocument();
    // Mobile's bare-artist label would otherwise collide with this query.
    expect(screen.queryByText("WAVEFORM / STEREO")).not.toBeInTheDocument();
  });
});
