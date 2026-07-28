import { describe, expect, it } from "vitest";

import { timecode } from "./format";

describe("timecode", () => {
  it("pads minutes and seconds to two digits", () => {
    expect(timecode(182_000)).toBe("03:02");
    expect(timecode(232_000)).toBe("03:52");
    expect(timecode(0)).toBe("00:00");
  });

  it("truncates partial seconds rather than rounding up", () => {
    expect(timecode(1999)).toBe("00:01");
  });

  it("clamps negative input to zero", () => {
    expect(timecode(-500)).toBe("00:00");
  });

  it("carries past an hour without a separate hours field", () => {
    expect(timecode(3_660_000)).toBe("61:00");
  });
});
