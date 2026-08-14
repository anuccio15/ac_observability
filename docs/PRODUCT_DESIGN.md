# Product and dashboard design

## Primary user questions

The interface should answer these without requiring HVAC expertise:

1. Is the system running normally right now?
2. When did it heat, cool, defrost, or remain idle?
3. Are temperatures, pressures, compressor demand, or electrical values unusual?
4. Did a fault occur, and what was happening immediately before it?
5. Is the Pi collecting and uploading healthy data?

## Navigation

- **Overview:** live/recent status, last contact, active mode, current headline
  metrics, latest fault, and a 24-hour operating timeline
- **Performance:** synchronized temperature, pressure, compressor, and electrical
  charts with range comparison
- **Cycles:** heating/cooling cycle list and duration/behavior comparisons
- **Faults:** urgent events, mapped Bosch faults, context window, and notes
- **Data explorer:** every confirmed/candidate value, raw frames, decoder version,
  export, and unknown-word analysis
- **Collector:** Pi health, boot ID, clock, BLE/reconnect quality, upload backlog,
  storage, and software versions
- **Settings:** device labels, units, timezone, alert thresholds, and retention

## Overview wireframe

```text
┌──────────────────────────────────────────────────────────────────┐
│ Home AC                         Last sample 8 sec ago     Healthy │
├───────────────┬───────────────┬───────────────┬──────────────────┤
│ Mode          │ Compressor    │ Outdoor temp  │ Active alerts    │
│ Cooling       │ 43 Hz         │ 96 °F         │ None             │
├───────────────┴───────────────┴───────────────┴──────────────────┤
│ 24-hour operating timeline                                      │
│  standby ── cooling ── standby ─── cooling ─────────             │
├─────────────────────────────────┬────────────────────────────────┤
│ Temperatures                    │ Pressures                      │
│ T3 / T4 / T5 / suction          │ Evaporating / condensing       │
├─────────────────────────────────┴────────────────────────────────┤
│ Latest cycle: 31 min   Peak compressor: 69 Hz   No data issues   │
└──────────────────────────────────────────────────────────────────┘
```

## Chart behavior

- Default to the device timezone but store/query UTC.
- Link crosshairs and zoom across charts so the same instant is comparable.
- Shade operating-mode regions behind the series.
- Show data gaps explicitly; never interpolate across missing telemetry.
- Visually distinguish confirmed, candidate, and derived metrics.
- Use server-selected rollup resolution and disclose it in the legend/export.
- Preserve raw values in tooltips even when charts display friendly precision.

## Initial metric groups

- Operating: mode and compressor set frequency
- Temperatures: T3, T4, T5, Th, T3L, IPM, Te/Tc, and targets
- Pressures: evaporating, condensing, lift, and compression ratio
- Electrical candidates: compressor current, AC input voltage, DC bus voltage
- Diagnostics: decoder confidence, invalid/incomplete frames, reconnects, and
  upload/storage state

Fault-code decoding remains explicitly unconfirmed. The UI must not label an
unknown word as a Bosch fault until its mapping is validated.

## Responsive strategy

The first web release is mobile-responsive and installable as a PWA. A native
mobile app is deferred until the query API and product workflows stabilize.
