import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Waveform, barAmplitude } from "./Waveform";

describe("barAmplitude", () => {
  it("is deterministic so the profile is stable across renders", () => {
    expect(barAmplitude(7)).toBe(barAmplitude(7));
  });

  it("stays within the handoff's 0.28 to 1.0 range", () => {
    for (let i = 0; i < 60; i += 1) {
      const amplitude = barAmplitude(i);
      expect(amplitude).toBeGreaterThanOrEqual(0.28);
      expect(amplitude).toBeLessThanOrEqual(1);
    }
  });
});

describe("Waveform", () => {
  it("exposes an accessible label rather than announcing 60 bars", () => {
    render(<Waveform bars={60} height={260} progress={0.5} isPlaying />);

    expect(screen.getByRole("img", { name: /waveform/i })).toBeInTheDocument();
  });
});
