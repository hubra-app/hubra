import { apiFetch } from '@vollbuild/api-client';

export interface FeatureFlag {
  key: string;
  enabled: boolean;
  label: string | null;
  description: string | null;
  requiresConfiguration: boolean;
}

export interface FeatureSettingField {
  key: string;
  value: string;
  label: string;
  description: string;
  validation_type: string | null;
  sensitive: boolean;
}

export interface FeatureSettingsResponse {
  key: string;
  settings: FeatureSettingField[];
}

export async function getFeatures(): Promise<FeatureFlag[]> {
  return apiFetch<FeatureFlag[]>("/features");
}

export async function updateFeature(
  key: string,
  enabled: boolean,
): Promise<FeatureFlag> {
  return apiFetch<FeatureFlag>(`/features/${key}`, {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
}

export async function getFeatureSettings(
  key: string,
): Promise<FeatureSettingsResponse> {
  return apiFetch<FeatureSettingsResponse>(`/features/${key}/settings`);
}

export async function saveFeatureSettings(
  key: string,
  settings: Record<string, string>,
): Promise<{ ok: boolean; requiresConfiguration: boolean }> {
  return apiFetch<{ ok: boolean; requiresConfiguration: boolean }>(
    `/features/${key}/settings`,
    {
      method: "PUT",
      body: JSON.stringify({ settings }),
    },
  );
}
