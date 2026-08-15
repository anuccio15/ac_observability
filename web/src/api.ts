export type Metrics = Record<string, number | string | null>;

export interface Sample {
  event_id: string;
  device_id: string;
  captured_at: string;
  server_received_at: string;
  decoder_version: number;
  urgent: boolean;
  urgent_reason: string | null;
  metrics: Metrics;
}

export interface Device {
  device_id: string;
  friendly_name: string | null;
  timezone: string;
  first_seen_at: string;
  last_seen_at: string;
  event_count: number;
  urgent_count: number;
  latest: Sample | null;
}

export interface MetricSeries {
  label: string;
  unit: string | null;
  category: string;
  confidence: string;
  points: Array<{
    timestamp: string;
    value: number;
    minimum: number;
    maximum: number;
    sample_count: number;
  }>;
}

export interface SeriesResponse {
  device_id: string;
  start: string;
  end: string;
  bucket_seconds: number;
  series: Record<string, MetricSeries>;
}

export interface SummaryResponse {
  device_id: string;
  window_hours: number;
  start: string;
  end: string;
  event_count: number;
  urgent_count: number;
  first_sample_at: string | null;
  last_sample_at: string | null;
  latest: Sample | null;
  aggregates: Record<string, { average: number; minimum: number; maximum: number }>;
}

export interface Cycle {
  mode: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  sample_count: number;
  average_compressor_hz: number | null;
  maximum_compressor_hz: number | null;
}

const json = async <T>(path: string): Promise<T> => {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
};

const query = (values: Record<string, string | number | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  return params.toString();
};

export const api = {
  devices: () => json<{ devices: Device[] }>("/api/v1/devices"),
  summary: (deviceId: string, hours: number) =>
    json<SummaryResponse>(`/api/v1/summary?${query({ device_id: deviceId, hours })}`),
  series: (deviceId: string, hours: number) => {
    const end = new Date();
    const start = new Date(end.getTime() - hours * 3_600_000);
    return json<SeriesResponse>(
      `/api/v1/telemetry/series?${query({
        device_id: deviceId,
        start: start.toISOString(),
        end: end.toISOString(),
        max_points: 1200
      })}`
    );
  },
  cycles: (deviceId: string, hours: number) => {
    const end = new Date();
    const start = new Date(end.getTime() - Math.min(hours, 24 * 31) * 3_600_000);
    return json<{ device_id: string; cycles: Cycle[] }>(
      `/api/v1/cycles?${query({
        device_id: deviceId,
        start: start.toISOString(),
        end: end.toISOString(),
        limit: 100
      })}`
    );
  },
  faults: (deviceId: string) =>
    json<{ device_id: string; faults: Sample[] }>(
      `/api/v1/faults?${query({ device_id: deviceId, limit: 100 })}`
    )
};
