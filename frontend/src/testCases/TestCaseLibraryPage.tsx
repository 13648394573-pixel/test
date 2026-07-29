import { useEffect, useState } from "react";

import TestCaseForm from "./TestCaseForm";
import { testCaseApi } from "./api";
import type { TestCase, TestCaseApi, TestCaseInput } from "./types";


interface TestCaseLibraryPageProps {
  api?: TestCaseApi;
}


export default function TestCaseLibraryPage({
  api = testCaseApi
}: TestCaseLibraryPageProps) {
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [editing, setEditing] = useState<TestCase | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .list()
      .then(setTestCases)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [api]);

  const startCreate = () => {
    setEditing(null);
    setShowForm(true);
    setError("");
  };

  const startEdit = (testCase: TestCase) => {
    setEditing(testCase);
    setShowForm(true);
    setError("");
  };

  const closeForm = () => {
    setEditing(null);
    setShowForm(false);
  };

  const saveTestCase = async (input: TestCaseInput) => {
    try {
      if (editing) {
        const updated = await api.update(editing.id, input);
        setTestCases((current) =>
          current.map((testCase) =>
            testCase.id === updated.id ? updated : testCase
          )
        );
      } else {
        const created = await api.create(input);
        setTestCases((current) => [created, ...current]);
      }
      closeForm();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存测试用例失败");
    }
  };

  const deleteTestCase = async (testCase: TestCase) => {
    if (!window.confirm(`确认删除测试用例 ${testCase.case_code}？`)) {
      return;
    }

    try {
      await api.delete(testCase.id);
      setTestCases((current) =>
        current.filter((candidate) => candidate.id !== testCase.id)
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除测试用例失败");
    }
  };

  return (
    <section
      className="test-case-library"
      aria-labelledby="test-case-library-title"
    >
      <div className="page-heading">
        <div>
          <p className="section-kicker">Test Case Library</p>
          <h2 id="test-case-library-title">测试用例库</h2>
          <p>集中维护手工测试用例与有序测试步骤。</p>
        </div>
        <button className="button button-primary" type="button" onClick={startCreate}>
          新建用例
        </button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      {showForm && (
        <TestCaseForm
          testCase={editing}
          onSubmit={saveTestCase}
          onCancel={closeForm}
        />
      )}

      <div className="table-panel">
        {loading ? (
          <p className="empty-state">正在加载测试用例…</p>
        ) : testCases.length === 0 ? (
          <p className="empty-state">暂无测试用例</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>用例编号</th>
                  <th>标题</th>
                  <th>设备类型</th>
                  <th>分类</th>
                  <th>优先级</th>
                  <th>步骤数</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {testCases.map((testCase) => (
                  <tr key={testCase.id}>
                    <td className="mono">{testCase.case_code}</td>
                    <td>{testCase.title}</td>
                    <td>{testCase.device_type ?? "—"}</td>
                    <td>{testCase.category}</td>
                    <td><span className="priority-badge">{testCase.priority}</span></td>
                    <td>{testCase.steps.length}</td>
                    <td>{testCase.enabled ? "启用" : "停用"}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="button button-quiet"
                          type="button"
                          aria-label={`编辑 ${testCase.case_code}`}
                          onClick={() => startEdit(testCase)}
                        >
                          编辑
                        </button>
                        <button
                          className="button button-danger"
                          type="button"
                          aria-label={`删除 ${testCase.case_code}`}
                          onClick={() => deleteTestCase(testCase)}
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
