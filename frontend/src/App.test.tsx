import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("application shell", () => {
  it("identifies the local test workbench without exposing business modules", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Test Workbench" })
    ).toBeInTheDocument();
    expect(screen.getByText("基础工程已就绪")).toBeInTheDocument();
  });
});
