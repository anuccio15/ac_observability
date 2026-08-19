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

export interface Page<T> {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  items: T[];
}

export interface SyncResponse {
  status: "complete";
  edge: {
    accepted: boolean;
    queued_samples: number;
    delivered_samples: number;
    pending_samples: number;
    completed_at: string;
  };
}

export type EdgeState = "healthy" | "bosch_disconnected" | "pi_unreachable" | "telemetry_stale" | "unknown";

export interface EdgeStatus {
  edge_id: string;
  state: EdgeState;
  checked_at: string | null;
  state_since: string | null;
  pi_reachable: boolean | null;
  bluetooth_connected: boolean | null;
  last_frame_at: string | null;
  detail: Record<string, unknown>;
}

export interface EdgeTransition {
  id: number;
  from_state: EdgeState | null;
  to_state: EdgeState;
  changed_at: string;
  detail: Record<string, unknown>;
}

export interface DailySummary {
  date: string;
  sample_count: number;
  cooling_runtime_seconds: number;
  cycle_count: number;
  average_outdoor_temp_f: number | null;
  maximum_outdoor_temp_f: number | null;
  average_compressor_hz: number | null;
  peak_compressor_hz: number | null;
  average_running_power_w: number | null;
  peak_power_w: number | null;
  outdoor_energy_kwh: number;
  high_effort_seconds: number;
  urgent_count: number;
  telemetry_gap_count: number;
  telemetry_coverage_percent: number;
  narrative: string;
  versus_previous: { outdoor_temp_f: number | null; cooling_runtime_seconds: number | null };
  versus_7_day_average: { cooling_runtime_seconds: number | null; comparison_days: number };
}

export interface AuthSession {
  authenticated: boolean;
  username: string | null;
}

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: { Accept: "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    if (response.status === 401 && !path.startsWith("/api/v1/auth/")) {
      window.dispatchEvent(new Event("ac-auth-required"));
    }
    throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
};

const json = async <T>(path: string): Promise<T> => {
  return request<T>(path);
};

const post = async <T>(path: string, body?: unknown): Promise<T> => {
  return request<T>(path, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
};

const query = (values: Record<string, string | number | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  return params.toString();
};

export const api = {
  authSession: () => json<AuthSession>("/api/v1/auth/session"),
  login: (username: string, password: string) =>
    post<AuthSession>("/api/v1/auth/login", { username, password }),
  logout: () => post<AuthSession>("/api/v1/auth/logout"),
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
  cycles: async (deviceId: string, hours: number, page: number, pageSize = 12): Promise<Page<Cycle>> => {
    const end = new Date();
    const start = new Date(end.getTime() - Math.min(hours, 24 * 31) * 3_600_000);
    const result = await json<{ device_id: string; page: number; page_size: number; total: number; total_pages: number; cycles: Cycle[] }>(
      `/api/v1/cycles?${query({
        device_id: deviceId,
        start: start.toISOString(),
        end: end.toISOString(),
        page,
        page_size: pageSize
      })}`
    );
    return { ...result, items: result.cycles };
  },
  faults: async (deviceId: string, page: number, pageSize = 8): Promise<Page<Sample>> => {
    const result = await json<{ device_id: string; page: number; page_size: number; total: number; total_pages: number; faults: Sample[] }>(
      `/api/v1/faults?${query({ device_id: deviceId, page, page_size: pageSize })}`
    );
    return { ...result, items: result.faults };
  },
  sync: () => post<SyncResponse>("/api/v1/edge/sync"),
  checkEdgeStatus: () => post<{ current: EdgeStatus }>("/api/v1/edge/status/check"),
  edgeStatus: () => json<{ current: EdgeStatus; transitions: EdgeTransition[] }>("/api/v1/edge/status"),
  dailySummaries: (deviceId: string, days = 14) =>
    json<{ device_id: string; timezone: string; days: DailySummary[] }>(
      `/api/v1/daily-summaries?${query({
        device_id: deviceId,
        days,
        timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Phoenix"
      })}`
    )
};
