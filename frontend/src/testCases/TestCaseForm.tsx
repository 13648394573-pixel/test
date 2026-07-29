import { FormEvent, useEffect, useState } from "react";

import type {
  CaseStepInput,
  TestCase,
  TestCaseInput,
  TestCasePriority
} from "./types";


interface TestCaseFormProps {
  testCase: TestCase | null;
  onSubmit: (input: TestCaseInput) => Promise<void>;
  onCancel: () => void;
}

interface FormState {
  case_code: string;
  title: string;
  device_type: string;
  category: string;
  priority: TestCasePriority;
  preconditions: string;
  description: string;
  enabled: boolean;
  steps: CaseStepInput[];
}


function emptyForm(): FormState {
  return {
    case_code: "",
    title: "",
    device_type: "",
    category: "",
    priority: "P2",
    preconditions: "",
    description: "",
    enabled: true,
    steps: [{ action: "", expected_result: "" }]
  };
}


function formStateFromTestCase(testCase: TestCase | null): FormState {
  if (testCase === null) {
    return emptyForm();
  }

  return {
    case_code: testCase.case_code,
    title: testCase.title,
    device_type: testCase.device_type ?? "",
    category: testCase.category,
    priority: testCase.priority,
    preconditions: testCase.preconditions ?? "",
    description: testCase.description ?? "",
    enabled: testCase.enabled,
    steps: testCase.steps.map(({ action, expected_result }) => ({
      action,
      expected_result
    }))
  };
}


export default function TestCaseForm({
  testCase,
  onSubmit,
  onCancel
}: TestCaseFormProps) {
  const [form, setForm] = useState<FormState>(
    () => formStateFromTestCase(testCase)
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm(formStateFromTestCase(testCase));
  }, [testCase]);

  const setField = <K extends keyof FormState>(
    field: K,
    value: FormState[K]
  ) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const setStep = (
    index: number,
    field: keyof CaseStepInput,
    value: string
  ) => {
    setForm((current) => ({
      ...current,
      steps: current.steps.map((step, stepIndex) =>
        stepIndex === index ? { ...step, [field]: value } : step
      )
    }));
  };

  const addStep = () => {
    setForm((current) => ({
      ...current,
      steps: [...current.steps, { action: "", expected_result: "" }]
    }));
  };

  const deleteStep = (index: number) => {
    setForm((current) => ({
      ...current,
      steps: current.steps.filter((_, stepIndex) => stepIndex !== index)
    }));
  };

  const moveStep = (index: number, direction: -1 | 1) => {
    setForm((current) => {
      const destination = index + direction;
      if (destination < 0 || destination >= current.steps.length) {
        return current;
      }
      const steps = [...current.steps];
      [steps[index], steps[destination]] = [steps[destination], steps[index]];
      return { ...current, steps };
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        case_code: form.case_code,
        title: form.title,
        device_type: form.device_type || null,
        category: form.category,
        priority: form.priority,
        preconditions: form.preconditions || null,
        description: form.description || null,
        enabled: form.enabled,
        steps: form.steps
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="test-case-form" onSubmit={handleSubmit}>
      <div className="form-heading">
        <div>
          <p className="section-kicker">Test Case</p>
          <h3>{testCase ? "编辑测试用例" : "新建测试用例"}</h3>
        </div>
        <button className="button button-quiet" type="button" onClick={onCancel}>
          取消
        </button>
      </div>

      <div className="form-grid test-case-fields">
        <label>
          <span>用例编号</span>
          <input
            required
            maxLength={100}
            value={form.case_code}
            onChange={(event) => setField("case_code", event.target.value)}
          />
        </label>
        <label>
          <span>用例标题</span>
          <input
            required
            maxLength={200}
            value={form.title}
            onChange={(event) => setField("title", event.target.value)}
          />
        </label>
        <label>
          <span>设备类型</span>
          <input
            maxLength={50}
            value={form.device_type}
            onChange={(event) => setField("device_type", event.target.value)}
          />
        </label>
        <label>
          <span>分类</span>
          <input
            required
            maxLength={100}
            value={form.category}
            onChange={(event) => setField("category", event.target.value)}
          />
        </label>
        <label>
          <span>优先级</span>
          <select
            value={form.priority}
            onChange={(event) =>
              setField("priority", event.target.value as TestCasePriority)
            }
          >
            {["P0", "P1", "P2", "P3"].map((priority) => (
              <option key={priority} value={priority}>{priority}</option>
            ))}
          </select>
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => setField("enabled", event.target.checked)}
          />
          <span>启用用例</span>
        </label>
        <label className="wide-field">
          <span>前置条件</span>
          <textarea
            rows={3}
            value={form.preconditions}
            onChange={(event) => setField("preconditions", event.target.value)}
          />
        </label>
        <label className="wide-field">
          <span>说明</span>
          <textarea
            rows={3}
            value={form.description}
            onChange={(event) => setField("description", event.target.value)}
          />
        </label>
      </div>

      <div className="step-editor">
        <div className="step-editor-heading">
          <div>
            <h3>测试步骤</h3>
            <p>步骤编号将在保存时按当前顺序自动生成。</p>
          </div>
          <button className="button button-quiet" type="button" onClick={addStep}>
            添加步骤
          </button>
        </div>
        {form.steps.map((step, index) => (
          <div className="step-card" key={index}>
            <div className="step-number">{index + 1}</div>
            <label>
              <span>{`步骤 ${index + 1} 操作`}</span>
              <textarea
                required
                rows={3}
                value={step.action}
                onChange={(event) =>
                  setStep(index, "action", event.target.value)
                }
              />
            </label>
            <label>
              <span>{`步骤 ${index + 1} 预期结果`}</span>
              <textarea
                required
                rows={3}
                value={step.expected_result}
                onChange={(event) =>
                  setStep(index, "expected_result", event.target.value)
                }
              />
            </label>
            <div className="step-actions">
              <button
                className="button button-quiet"
                type="button"
                aria-label={`上移步骤 ${index + 1}`}
                disabled={index === 0}
                onClick={() => moveStep(index, -1)}
              >
                ↑
              </button>
              <button
                className="button button-quiet"
                type="button"
                aria-label={`下移步骤 ${index + 1}`}
                disabled={index === form.steps.length - 1}
                onClick={() => moveStep(index, 1)}
              >
                ↓
              </button>
              <button
                className="button button-danger"
                type="button"
                aria-label={`删除步骤 ${index + 1}`}
                disabled={form.steps.length === 1}
                onClick={() => deleteStep(index)}
              >
                删除
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="form-actions">
        <button className="button button-primary" type="submit" disabled={saving}>
          {saving ? "保存中…" : "保存用例"}
        </button>
      </div>
    </form>
  );
}
