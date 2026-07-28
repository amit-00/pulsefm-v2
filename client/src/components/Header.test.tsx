import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Header } from "./Header";

describe("Header", () => {
  it("renders the brand and both desktop nav items", () => {
    render(<Header variant="desktop" />);

    expect(screen.getByText("PULSE FM")).toBeInTheDocument();
    expect(screen.getByText("HOW IT WORKS")).toBeInTheDocument();
    expect(screen.getByText("LOGIN")).toBeInTheDocument();
  });

  it("drops HOW IT WORKS on mobile", () => {
    render(<Header variant="mobile" />);

    expect(screen.getByText("LOGIN")).toBeInTheDocument();
    expect(screen.queryByText("HOW IT WORKS")).not.toBeInTheDocument();
  });
});
