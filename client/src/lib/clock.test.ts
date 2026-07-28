import { describe, expect, it } from "vitest";

import { computeOffsetMs, positionMs, serverNow } from "./clock";

describe("computeOffsetMs", () => {
  it("is positive when the server clock leads the client", () => {
    expect(computeOffsetMs("2026-07-28T12:00:05Z", Date.parse("2026-07-28T12:00:00Z"))).toBe(5000);
  });

  it("is negative when the client clock leads the server", () => {
    expect(computeOffsetMs("2026-07-28T12:00:00Z", Date.parse("2026-07-28T12:00:05Z"))).toBe(-5000);
  });
});

describe("serverNow", () => {
  it("applies the offset to local time", () => {
    expect(serverNow(5000, 1000)).toBe(6000);
  });
});

describe("positionMs", () => {
  const startAt = "2026-07-28T12:00:00Z";

  it("returns elapsed milliseconds against the corrected clock", () => {
    const now = Date.parse("2026-07-28T12:00:30Z");
    expect(positionMs(startAt, 0, now)).toBe(30_000);
  });

  it("corrects a skewed client clock", () => {
    const now = Date.parse("2026-07-28T11:59:30Z");
    expect(positionMs(startAt, 60_000, now)).toBe(30_000);
  });

  it("never returns a negative position", () => {
    const now = Date.parse("2026-07-28T11:59:00Z");
    expect(positionMs(startAt, 0, now)).toBe(0);
  });
});
