import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TestCaseLibraryPage from "./TestCaseLibraryPage";
import type {
  CaseStep,
  TestCase,
  TestCaseApi,
  TestCaseInput
} from "./types";


const CASE: TestCase = {
  id: "case-1",
  case_code: "ONU-WAN-001",
  title: "Verify IPoE WAN",
  device_type: "ONU",
  category: "WAN",
  priority: "P1",
  preconditions: "ONU is registered",
  description: null,
  enabled: true,
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00",
  steps: [
    {
      id: "step-1",
      test_case_id: "case-1",
      step_number: 1,
      action: "Create an IPoE WAN",
      expected_result: "WAN obtains an address",
      created_at: "2026-07-29T08:00:00",
      updated_at: "2026-07-29T08:00:00"
    },
    {
      id: "step-2",
      test_case_id: "case-1",
      step_number: 2,
      action: "Ping the gateway",
      expected_result: "Ping succeeds",
      created_at: "2026-07-29T08:00:00",
      updated_at: "2026-07-29T08:00:00"
    }
  ]
};


class MemoryTestCaseApi implements TestCaseApi {
  private cases: TestCase[];

  constructor(cases: TestCase[] = []) {
    this.cases = structuredClone(cases);
  }

  async list(): Promise<TestCase[]> {
    return structuredClone(this.cases);
  }

  async create(input: TestCaseInput): Promise<TestCase> {
    const created = this.buildCase(
      `case-${this.cases.length + 1}`,
      input
    );
    this.cases.unshift(created);
    return structuredClone(created);
  }

  async update(id: string, input: TestCaseInput): Promise<TestCase> {
    const index = this.cases.findIndex((testCase) => testCase.id === id);
    const updated = this.buildCase(id, input);
    this.cases[index] = updated;
    return structuredClone(updated);
  }

  async delete(id: string): Promise<void> {
    this.cases = this.cases.filter((testCase) => testCase.id !== id);
  }

  private buildCase(id: string, input: TestCaseInput): TestCase {
    const steps: CaseStep[] = input.steps.map((step, index) => ({
      ...step,
      id: `${id}-step-${index + 1}`,
      test_case_id: id,
      step_number: index + 1,
      created_at: "2026-07-29T09:00:00",
      updated_at: "2026-07-29T09:00:00"
    }));
    return {
      ...input,
      id,
      steps,
      created_at: "2026-07-29T09:00:00",
      updated_at: "2026-07-29T09:00:00"
    };
  }
}


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});


describe("Test Case Library", () => {
  it("shows existing test cases and step counts", async () => {
    render(<TestCaseLibraryPage api={new MemoryTestCaseApi([CASE])} />);

    const row = await screen.findByRole("row", { name: /ONU-WAN-001/ });

    expect(within(row).getByText("Verify IPoE WAN")).toBeInTheDocument();
    expect(within(row).getByText("P1")).toBeInTheDocument();
    expect(within(row).getByText("2")).toBeInTheDocument();
    expect(within(row).getByText("启用")).toBeInTheDocument();
  });

  it("creates a case and moves steps before saving", async () => {
    render(<TestCaseLibraryPage api={new MemoryTestCaseApi()} />);

    fireEvent.click(screen.getByRole("button", { name: "新建用例" }));
    fireEvent.change(screen.getByLabelText("用例编号"), {
      target: { value: "OLT-PON-001" }
    });
    fireEvent.change(screen.getByLabelText("用例标题"), {
      target: { value: "Verify ONU registration" }
    });
    fireEvent.change(screen.getByLabelText("分类"), {
      target: { value: "PON" }
    });
    fireEvent.change(screen.getByLabelText("步骤 1 操作"), {
      target: { value: "Connect ONU" }
    });
    fireEvent.change(screen.getByLabelText("步骤 1 预期结果"), {
      target: { value: "ONU powers on" }
    });
    fireEvent.click(screen.getByRole("button", { name: "添加步骤" }));
    fireEvent.change(screen.getByLabelText("步骤 2 操作"), {
      target: { value: "Query ONU state" }
    });
    fireEvent.change(screen.getByLabelText("步骤 2 预期结果"), {
      target: { value: "ONU reaches O5" }
    });
    fireEvent.click(screen.getByRole("button", { name: "上移步骤 2" }));
    fireEvent.click(screen.getByRole("button", { name: "下移步骤 1" }));
    fireEvent.click(screen.getByRole("button", { name: "上移步骤 2" }));
    fireEvent.click(screen.getByRole("button", { name: "保存用例" }));

    const row = await screen.findByRole("row", { name: /OLT-PON-001/ });
    expect(row).toHaveTextContent("2");

    fireEvent.click(screen.getByRole("button", { name: "编辑 OLT-PON-001" }));
    expect(screen.getByLabelText("步骤 1 操作")).toHaveValue("Query ONU state");
    expect(screen.getByLabelText("步骤 2 操作")).toHaveValue("Connect ONU");
  });

  it("edits a case and deletes a step with full replacement", async () => {
    render(<TestCaseLibraryPage api={new MemoryTestCaseApi([CASE])} />);
    await screen.findByRole("row", { name: /ONU-WAN-001/ });

    fireEvent.click(screen.getByRole("button", { name: "编辑 ONU-WAN-001" }));
    fireEvent.change(screen.getByLabelText("用例标题"), {
      target: { value: "Updated WAN case" }
    });
    fireEvent.click(screen.getByRole("button", { name: "删除步骤 2" }));
    fireEvent.click(screen.getByRole("button", { name: "保存用例" }));

    await waitFor(() => {
      const row = screen.getByRole("row", { name: /ONU-WAN-001/ });
      expect(row).toHaveTextContent("Updated WAN case");
      expect(within(row).getByText("1")).toBeInTheDocument();
    });
  });

  it("deletes a case after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<TestCaseLibraryPage api={new MemoryTestCaseApi([CASE])} />);
    await screen.findByRole("row", { name: /ONU-WAN-001/ });

    fireEvent.click(screen.getByRole("button", { name: "删除 ONU-WAN-001" }));

    await waitFor(() => {
      expect(
        screen.queryByRole("row", { name: /ONU-WAN-001/ })
      ).not.toBeInTheDocument();
    });
    expect(screen.getByText("暂无测试用例")).toBeInTheDocument();
  });
});
