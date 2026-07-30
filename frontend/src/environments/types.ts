export interface EnvironmentParameterInput {
  section: string;
  param_key: string;
  param_value: string;
  display_order: number;
}

export interface EnvironmentProfileInput {
  name: string;
  description: string | null;
  enabled: boolean;
  parameters: EnvironmentParameterInput[];
}

export interface EnvironmentParameter extends EnvironmentParameterInput {
  id: string;
  profile_id: string;
  created_at: string;
  updated_at: string;
}

export interface EnvironmentProfile {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  parameters: EnvironmentParameter[];
}

export interface EnvironmentApi {
  list(): Promise<EnvironmentProfile[]>;
  create(input: EnvironmentProfileInput): Promise<EnvironmentProfile>;
  update(
    id: string,
    input: EnvironmentProfileInput
  ): Promise<EnvironmentProfile>;
  delete(id: string): Promise<void>;
}
