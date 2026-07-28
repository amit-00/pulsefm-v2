import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Waveform, barAmplitude } from "./Waveform";

/**
 * jsdom implements neither `window.matchMedia` nor `HTMLCanvasElement`'s 2D
 * context. The component must tolerate both: it reads matchMedia
 * unconditionally (to track prefers-reduced-motion live), and must not crash
 * when getContext("2d") returns null.
 */
let addEventListenerSpy: ReturnType<
  typeof vi.fn<(type: string, listener: EventListenerOrEventListenerObject) => void>
>;
let removeEventListenerSpy: ReturnType<
  typeof vi.fn<(type: string, listener: EventListenerOrEventListenerObject) => void>
>;

beforeEach(() => {
  addEventListenerSpy = vi.fn((_type: string, _listener: EventListenerOrEventListenerObject) => {});
  removeEventListenerSpy = vi.fn((_type: string, _listener: EventListenerOrEventListenerObject) => {});

  const mediaQueryList: MediaQueryList = {
    matches: false,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addEventListener: addEventListenerSpy,
    removeEventListener: removeEventListenerSpy,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  };

  vi.stubGlobal(
    "matchMedia",
    vi.fn((): MediaQueryList => mediaQueryList),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

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

  it("does not crash when getContext(\"2d\") returns null, as it does under jsdom", () => {
    // jsdom's canvas returns a null 2D context by default (no `canvas` package
    // installed), which is also the real-world fallback path this guards.
    expect(() =>
      render(<Waveform bars={60} height={260} progress={0} isPlaying={false} />),
    ).not.toThrow();
    expect(screen.getByRole("img", { name: /waveform/i })).toBeInTheDocument();
  });

  it("registers and cleans up a prefers-reduced-motion change listener", () => {
    const { unmount } = render(
      <Waveform bars={60} height={260} progress={0.5} isPlaying />,
    );

    expect(addEventListenerSpy).toHaveBeenCalledWith("change", expect.any(Function));

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith("change", expect.any(Function));
  });
});
