import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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

describe("Player", () => {
  it("renders the track identity and the desktop sub-label", () => {
    render(<Player snapshot={snapshot} offsetMs={0} />);

    // Both the mobile and desktop compositions are always in the DOM — CSS
    // breakpoints, not JS conditionals, decide which one is visible — so the
    // title renders twice in jsdom (which does not evaluate media queries).
    expect(screen.getAllByText("Nightshift Drift").length).toBeGreaterThan(0);
    expect(screen.getByText("SABLE UNIT / WAVEFORM STEREO")).toBeInTheDocument();
  });

  it("shows a waiting message before the first snapshot", () => {
    render(<Player snapshot={null} offsetMs={0} />);

    expect(screen.getByText(/tuning in/i)).toBeInTheDocument();
  });
});
