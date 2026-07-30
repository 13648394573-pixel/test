import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import EnvironmentSnapshotPanel from "./EnvironmentSnapshotPanel";


afterEach(cleanup);


describe("EnvironmentSnapshotPanel", () => {
  it("groups immutable parameters and supports historical runs without snapshots", () => {
    const { rerender } = render(
      <EnvironmentSnapshotPanel snapshot={{
        id: "snapshot-1",
        test_run_id: "run-1",
        environment_profile_source_id: "env-1",
        snapshot_version: 1,
        created_at: "2026-07-30T15:00:00",
        profile_snapshot: {
          profile_name: "ONU Lab",
          description: null,
          profile_updated_at: "2026-07-30T14:00:00",
          captured_at: "2026-07-30T15:00:00",
          parameters: [{
            section: "OLT",
            param_key: "model",
            param_value: "MA5800-X7",
            display_order: 1
          }]
        }
      }} />
    );

    expect(screen.getByText("ONU Lab")).toBeInTheDocument();
    expect(screen.getByText("MA5800-X7")).toBeInTheDocument();
    rerender(<EnvironmentSnapshotPanel snapshot={null} />);
    expect(screen.getByText(/No environment snapshot/)).toBeInTheDocument();
  });
});
