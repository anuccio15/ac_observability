import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type Cycle, type Device, type Sample, type SeriesResponse, type SummaryResponse } from "./api";
import { MetricChart } from "./MetricChart";

const RANGE_OPTIONS = [
  { label: "6h", value: 6 },
  { label: "24h", value: 24 },
  { label: "3d", value: 72 },
  { label: "7d", value: 168 },
  { label: "30d", value: 720 }
];

const number = (value: unknown, digits = 0) =>
  typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : "—";
const when = (value?: string | null) => value ? new Date(value).toLocaleString() : "—";
const duration = (seconds: number) => {
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes} min`;
};

function StatCard({ label, value, unit, detail, accent }: {
  label: string; value: string; unit?: string; detail: string; accent?: string;
}) {
  return (
    <article className="stat-card" style={{ "--accent": accent ?? "#52d6c7" } as React.CSSProperties}>
      <p>{label}</p>
      <div className="stat-value">{value}<span>{unit}</span></div>
      <small>{detail}</small>
    </article>
  );
}

function CycleTable({ cycles }: { cycles: Cycle[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Mode</th><th>Started</th><th>Duration</th><th>Avg Hz</th><th>Peak Hz</th></tr></thead>
        <tbody>
          {cycles.slice(0, 12).map((cycle) => (
            <tr key={`${cycle.started_at}-${cycle.mode}`}>
              <td><span className={`mode mode-${cycle.mode}`}>{cycle.mode}</span></td>
              <td>{when(cycle.started_at)}</td>
              <td>{duration(cycle.duration_seconds)}</td>
              <td>{number(cycle.average_compressor_hz, 1)}</td>
              <td>{number(cycle.maximum_compressor_hz, 0)}</td>
            </tr>
          ))}
          {!cycles.length && <tr><td colSpan={5} className="empty">No cycles in this range</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [hours, setHours] = useState(24);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [series, setSeries] = useState<SeriesResponse | null>(null);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [faults, setFaults] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  useEffect(() => {
    api.devices()
      .then(({ devices: available }) => {
        setDevices(available);
        setDeviceId((current) => current || available[0]?.device_id || "");
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const refresh = useCallback(async () => {
    if (!deviceId) return;
    setLoading(true);
    try {
      const [nextSummary, nextSeries, nextCycles, nextFaults, nextDevices] = await Promise.all([
        api.summary(deviceId, hours),
        api.series(deviceId, hours),
        api.cycles(deviceId, hours),
        api.faults(deviceId),
        api.devices()
      ]);
      setSummary(nextSummary);
      setSeries(nextSeries);
      setCycles(nextCycles.cycles);
      setFaults(nextFaults.faults);
      setDevices(nextDevices.devices);
      setLastRefresh(new Date());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load telemetry");
    } finally {
      setLoading(false);
    }
  }, [deviceId, hours]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const latest = summary?.latest;
  const metrics = latest?.metrics ?? {};
  const selectedDevice = devices.find((device) => device.device_id === deviceId);
  const fresh = latest ? Date.now() - new Date(latest.captured_at).getTime() < 4 * 3_600_000 : false;
  const cycleStats = useMemo(() => {
    const active = cycles.filter((cycle) => cycle.mode !== "standby");
    return {
      count: active.length,
      runtime: active.reduce((total, cycle) => total + cycle.duration_seconds, 0)
    };
  }, [cycles]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><span /></div>
          <div><strong>AC Observatory</strong><small>Bosch IDS Premium Connected</small></div>
        </div>
        <div className="top-actions">
          <div className={`status-pill ${fresh ? "online" : "stale"}`}><span />{fresh ? "Current" : "Awaiting upload"}</div>
          <button className="refresh" onClick={() => void refresh()} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      <main>
        <section className="hero-row">
          <div>
            <p className="eyebrow">SYSTEM OVERVIEW</p>
            <h1>Outdoor unit telemetry</h1>
            <p className="subtitle">Recent inverter, refrigerant, and thermal performance from your edge collector.</p>
          </div>
          <div className="filters">
            <label>Unit<select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}>
              {devices.map((device) => <option key={device.device_id} value={device.device_id}>{device.friendly_name || device.device_id}</option>)}
            </select></label>
            <div className="range" aria-label="Time range">
              {RANGE_OPTIONS.map((option) => <button key={option.value} className={hours === option.value ? "active" : ""} onClick={() => setHours(option.value)}>{option.label}</button>)}
            </div>
          </div>
        </section>

        {error && <div className="error-banner"><strong>Data unavailable</strong><span>{error}</span></div>}

        <section className="stats-grid">
          <StatCard label="Operating mode" value={String(metrics.mode ?? "Unknown")} detail={`Updated ${when(latest?.captured_at)}`} accent="#52d6c7" />
          <StatCard label="Compressor command" value={number(metrics.compressor_set_hz)} unit="Hz" detail={`${cycleStats.count} active segments in range`} accent="#73a9ff" />
          <StatCard label="Outdoor ambient" value={number(metrics.outdoor_ambient_t4_f)} unit="°F" detail={`Coil ${number(metrics.outdoor_coil_t3_f)}°F`} accent="#ffb86b" />
          <StatCard label="Pressure lift" value={number(metrics.pressure_lift_psid)} unit="psi" detail={`${number(metrics.evaporating_pressure_pe_psig)} / ${number(metrics.condensing_pressure_pc_psig)} psig`} accent="#e67ca1" />
        </section>

        <section className="dashboard-grid">
          <article className="panel span-2">
            <div className="panel-head"><div><p className="eyebrow">CAPACITY</p><h2>Compressor demand</h2></div><span>{series?.bucket_seconds ?? 0}s resolution</span></div>
            <MetricChart data={series} metrics={["compressor_set_hz"]} />
          </article>
          <article className="panel system-card">
            <div className="panel-head"><div><p className="eyebrow">SYSTEM</p><h2>Collector status</h2></div></div>
            <dl>
              <div><dt>Last sample</dt><dd>{when(latest?.captured_at)}</dd></div>
              <div><dt>Samples in range</dt><dd>{summary?.event_count.toLocaleString() ?? "—"}</dd></div>
              <div><dt>Stored events</dt><dd>{selectedDevice?.event_count.toLocaleString() ?? "—"}</dd></div>
              <div><dt>Active runtime</dt><dd>{duration(cycleStats.runtime)}</dd></div>
              <div><dt>Decoder</dt><dd>v{latest?.decoder_version ?? "—"}</dd></div>
              <div><dt>Urgent events</dt><dd className={faults.length ? "warning" : "good"}>{faults.length}</dd></div>
            </dl>
          </article>

          <article className="panel span-2">
            <div className="panel-head"><div><p className="eyebrow">THERMAL</p><h2>Temperature profile</h2></div><span>°F</span></div>
            <MetricChart data={series} metrics={["outdoor_ambient_t4_f", "outdoor_coil_t3_f", "compressor_discharge_t5_f", "compressor_suction_th_f", "compressor_ipm_temp_f"]} height={340} />
          </article>
          <article className="panel">
            <div className="panel-head"><div><p className="eyebrow">TARGET TRACKING</p><h2>Refrigerant temperatures</h2></div></div>
            <MetricChart data={series} metrics={["target_evaporating_temp_tes_f", "evaporating_temp_te_f", "target_condensing_temp_tcs_f", "condensing_temp_tc_f"]} height={340} />
          </article>

          <article className="panel">
            <div className="panel-head"><div><p className="eyebrow">REFRIGERANT</p><h2>System pressures</h2></div><span>psig</span></div>
            <MetricChart data={series} metrics={["evaporating_pressure_pe_psig", "condensing_pressure_pc_psig"]} />
          </article>
          <article className="panel">
            <div className="panel-head"><div><p className="eyebrow">SUPERHEAT</p><h2>Discharge tracking</h2></div><span>°F</span></div>
            <MetricChart data={series} metrics={["target_discharge_superheat_f", "compressor_discharge_superheat_f"]} />
          </article>
          <article className="panel">
            <div className="panel-head"><div><p className="eyebrow">ELECTRICAL · CANDIDATE</p><h2>Inverter input</h2></div></div>
            <MetricChart data={series} metrics={["candidate_ac_input_voltage_v", "candidate_compressor_current_a"]} />
            <p className="candidate-note">Candidate mappings are plausible but remain under validation.</p>
          </article>

          <article className="panel span-2">
            <div className="panel-head"><div><p className="eyebrow">HISTORY</p><h2>Operating segments</h2></div><span>{cycles.length} detected</span></div>
            <CycleTable cycles={cycles} />
          </article>
          <article className="panel faults">
            <div className="panel-head"><div><p className="eyebrow">EVENTS</p><h2>Fault monitor</h2></div></div>
            {!faults.length ? <div className="all-clear"><span>✓</span><strong>All clear</strong><p>No urgent events have been captured.</p></div> : faults.slice(0, 8).map((fault) => <div className="fault" key={fault.event_id}><strong>{fault.urgent_reason || "Urgent event"}</strong><span>{when(fault.captured_at)}</span></div>)}
          </article>
        </section>
      </main>
      <footer><span>AC Observatory · Read-only equipment monitoring</span><span>Last dashboard refresh {lastRefresh?.toLocaleTimeString() ?? "—"}</span></footer>
    </div>
  );
}
