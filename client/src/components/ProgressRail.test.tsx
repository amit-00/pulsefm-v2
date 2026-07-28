import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProgressRail } from "./ProgressRail";

describe("ProgressRail", () => {
  it("renders position and duration as M:SS timecodes", () => {
    render(
      <ProgressRail
        positionMs={182_000}
        durationMs={232_000}
        showPlayhead
        gapClassName="gap-4"
      />,
    );

    expect(screen.getByText("03:02")).toBeInTheDocument();
    expect(screen.getByText("03:52")).toBeInTheDocument();
  });

  it("clamps the fill to 100% when position exceeds duration", () => {
    const { container } = render(
      <ProgressRail
        positionMs={999_000}
        durationMs={232_000}
        showPlayhead={false}
        gapClassName="gap-3.5"
      />,
    );

    const fill = container.querySelector(".bg-paper");
    expect(fill).toHaveStyle({ right: "0%" });
  });

  it("omits the playhead dot when showPlayhead is false", () => {
    const { container } = render(
      <ProgressRail
        positionMs={100_000}
        durationMs={232_000}
        showPlayhead={false}
        gapClassName="gap-3.5"
      />,
    );

    expect(container.querySelector(".bg-accent")).not.toBeInTheDocument();
  });
});
