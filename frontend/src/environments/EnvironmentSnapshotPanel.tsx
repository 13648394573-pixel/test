import type { RunEnvironmentSnapshot } from "../testExecution/types";


interface Props {
  snapshot: RunEnvironmentSnapshot | null;
}


export default function EnvironmentSnapshotPanel({ snapshot }: Props) {
  if (!snapshot) {
    return (
      <section aria-label="Environment snapshot">
        <h4>Environment Snapshot</h4>
        <p>No environment snapshot was recorded for this historical run.</p>
      </section>
    );
  }

  const grouped = snapshot.profile_snapshot.parameters.reduce<
    Record<string, typeof snapshot.profile_snapshot.parameters>
  >((result, parameter) => {
    (result[parameter.section] ??= []).push(parameter);
    return result;
  }, {});

  return (
    <section aria-label="Environment snapshot" className="environment-snapshot">
      <h4>Environment Snapshot</h4>
      <p>
        <strong>{snapshot.profile_snapshot.profile_name}</strong>
        {" · captured "}
        {snapshot.profile_snapshot.captured_at}
      </p>
      {Object.entries(grouped).map(([section, parameters]) => (
        <div key={section}>
          <h5>{section}</h5>
          <dl>
            {parameters.map((parameter) => (
              <div key={parameter.param_key}>
                <dt>{parameter.param_key}</dt>
                <dd>{parameter.param_value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </section>
  );
}
