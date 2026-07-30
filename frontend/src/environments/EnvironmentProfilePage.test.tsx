import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EnvironmentProfilePage from "./EnvironmentProfilePage";
import type {
  EnvironmentApi,
  EnvironmentProfile,
  EnvironmentProfileInput
} from "./types";


class MemoryEnvironmentApi implements EnvironmentApi {
  profiles: EnvironmentProfile[] = [];

  async list() {
    return structuredClone(this.profiles);
  }

  async create(input: EnvironmentProfileInput) {
    const profile = this.build("env-1", input);
    this.profiles = [profile];
    return structuredClone(profile);
  }

  async update(id: string, input: EnvironmentProfileInput) {
    const profile = this.build(id, input);
    this.profiles = [profile];
    return structuredClone(profile);
  }

  async delete() {
    this.profiles = [];
  }

  private build(id: string, input: EnvironmentProfileInput): EnvironmentProfile {
    return {
      ...input,
      id,
      created_at: "2026-07-30T14:00:00",
      updated_at: "2026-07-30T14:00:00",
      parameters: input.parameters.map((parameter, index) => ({
        ...parameter,
        id: `parameter-${index}`,
        profile_id: id,
        created_at: "2026-07-30T14:00:00",
        updated_at: "2026-07-30T14:00:00"
      }))
    };
  }
}


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});


describe("EnvironmentProfilePage", () => {
  it("creates, edits, and deletes an environment profile with parameters", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const api = new MemoryEnvironmentApi();
    render(<EnvironmentProfilePage api={api} />);

    fireEvent.click(await screen.findByRole("button", { name: "New Profile" }));
    fireEvent.change(screen.getByLabelText("Profile Name"), {
      target: { value: "ONU Lab A" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Add Parameter" }));
    fireEvent.change(screen.getByLabelText("Section 1"), {
      target: { value: "OLT" }
    });
    fireEvent.change(screen.getByLabelText("Key 1"), {
      target: { value: "model" }
    });
    fireEvent.change(screen.getByLabelText("Value 1"), {
      target: { value: "MA5800-X7" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Profile" }));

    expect(await screen.findByText("ONU Lab A")).toBeInTheDocument();
    expect(screen.getByText(/MA5800-X7/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit ONU Lab A" }));
    fireEvent.change(screen.getByLabelText("Profile Name"), {
      target: { value: "ONU Lab B" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Profile" }));
    expect(await screen.findByText("ONU Lab B")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete ONU Lab B" }));
    await waitFor(() =>
      expect(screen.queryByText("ONU Lab B")).not.toBeInTheDocument()
    );
  });
});
