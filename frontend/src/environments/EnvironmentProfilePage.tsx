import { FormEvent, useEffect, useState } from "react";

import { environmentApi } from "./api";
import type {
  EnvironmentApi,
  EnvironmentProfile,
  EnvironmentProfileInput
} from "./types";


const EMPTY_PROFILE: EnvironmentProfileInput = {
  name: "",
  description: null,
  enabled: true,
  parameters: []
};


export default function EnvironmentProfilePage({
  api = environmentApi
}: { api?: EnvironmentApi }) {
  const [profiles, setProfiles] = useState<EnvironmentProfile[]>([]);
  const [form, setForm] = useState<EnvironmentProfileInput>(EMPTY_PROFILE);
  const [editing, setEditing] = useState<EnvironmentProfile | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.list().then(setProfiles).catch((reason: Error) => setError(reason.message));
  }, [api]);

  const startCreate = () => {
    setEditing(null);
    setForm(EMPTY_PROFILE);
    setShowForm(true);
  };

  const startEdit = (profile: EnvironmentProfile) => {
    setEditing(profile);
    setForm({
      name: profile.name,
      description: profile.description,
      enabled: profile.enabled,
      parameters: profile.parameters.map((parameter) => ({
        section: parameter.section,
        param_key: parameter.param_key,
        param_value: parameter.param_value,
        display_order: parameter.display_order
      }))
    });
    setShowForm(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const saved = editing
        ? await api.update(editing.id, form)
        : await api.create(form);
      setProfiles((current) =>
        editing
          ? current.map((profile) => profile.id === saved.id ? saved : profile)
          : [saved, ...current]
      );
      setShowForm(false);
      setEditing(null);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save profile");
    }
  };

  const remove = async (profile: EnvironmentProfile) => {
    if (!window.confirm(`Delete environment profile ${profile.name}?`)) return;
    try {
      await api.delete(profile.id);
      setProfiles((current) => current.filter((item) => item.id !== profile.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete profile");
    }
  };

  const addParameter = () => {
    setForm((current) => ({
      ...current,
      parameters: [
        ...current.parameters,
        {
          section: "",
          param_key: "",
          param_value: "",
          display_order: current.parameters.length + 1
        }
      ]
    }));
  };

  const updateParameter = (
    index: number,
    field: "section" | "param_key" | "param_value",
    value: string
  ) => {
    setForm((current) => ({
      ...current,
      parameters: current.parameters.map((parameter, candidate) =>
        candidate === index ? { ...parameter, [field]: value } : parameter
      )
    }));
  };

  const removeParameter = (index: number) => {
    setForm((current) => ({
      ...current,
      parameters: current.parameters
        .filter((_parameter, candidate) => candidate !== index)
        .map((parameter, candidate) => ({
          ...parameter,
          display_order: candidate + 1
        }))
    }));
  };

  return (
    <section aria-labelledby="environment-profile-title">
      <div className="page-heading">
        <div>
          <p className="section-kicker">Environment</p>
          <h2 id="environment-profile-title">Environment Profiles</h2>
          <p>Maintain reusable lab parameters for traceable manual test runs.</p>
        </div>
        <button className="button button-primary" type="button" onClick={startCreate}>
          New Profile
        </button>
      </div>
      {error && <p className="error-message" role="alert">{error}</p>}
      {showForm && (
        <form className="execution-project-form" onSubmit={save}>
          <div className="form-grid">
            <label>
              Profile Name
              <input
                required
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    enabled: event.target.checked
                  }))
                }
              />
              Enabled
            </label>
            <label className="wide-field">
              Description
              <textarea
                value={form.description ?? ""}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    description: event.target.value || null
                  }))
                }
              />
            </label>
          </div>
          <div className="parameter-editor">
            {form.parameters.map((parameter, index) => (
              <div className="form-grid" key={index}>
                <label>
                  {`Section ${index + 1}`}
                  <input
                    required
                    aria-label={`Section ${index + 1}`}
                    value={parameter.section}
                    onChange={(event) =>
                      updateParameter(index, "section", event.target.value)
                    }
                  />
                </label>
                <label>
                  {`Key ${index + 1}`}
                  <input
                    required
                    aria-label={`Key ${index + 1}`}
                    value={parameter.param_key}
                    onChange={(event) =>
                      updateParameter(index, "param_key", event.target.value)
                    }
                  />
                </label>
                <label>
                  {`Value ${index + 1}`}
                  <input
                    aria-label={`Value ${index + 1}`}
                    value={parameter.param_value}
                    onChange={(event) =>
                      updateParameter(index, "param_value", event.target.value)
                    }
                  />
                </label>
                <button
                  className="button button-danger"
                  type="button"
                  aria-label={`Remove Parameter ${index + 1}`}
                  onClick={() => removeParameter(index)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <div className="form-actions">
            <button className="button button-quiet" type="button" onClick={addParameter}>
              Add Parameter
            </button>
            <button className="button button-primary" type="submit">
              Save Profile
            </button>
          </div>
        </form>
      )}
      <div className="table-panel">
        {profiles.length === 0 ? (
          <p className="empty-state">No environment profiles.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Parameters</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id}>
                    <td>{profile.name}</td>
                    <td>{profile.enabled ? "Enabled" : "Disabled"}</td>
                    <td>
                      {profile.parameters.map((parameter) => (
                        <span key={parameter.id}>
                          {parameter.param_key}: {parameter.param_value}
                        </span>
                      ))}
                    </td>
                    <td>
                      <button
                        className="button button-quiet"
                        type="button"
                        aria-label={`Edit ${profile.name}`}
                        onClick={() => startEdit(profile)}
                      >
                        Edit
                      </button>
                      <button
                        className="button button-danger"
                        type="button"
                        aria-label={`Delete ${profile.name}`}
                        onClick={() => remove(profile)}
                      >
                        Delete
                      </button>
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
