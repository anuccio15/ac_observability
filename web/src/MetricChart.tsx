import * as echarts from "echarts";
import { useEffect, useRef } from "react";
import type { SeriesResponse } from "./api";

const COLORS = ["#52d6c7", "#ffb86b", "#73a9ff", "#e67ca1", "#a99cff", "#9dd67c"];

interface Props {
  data: SeriesResponse | null;
  metrics: string[];
  height?: number;
}

export function MetricChart({ data, metrics, height = 300 }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const selected = metrics
      .map((key) => [key, data?.series[key]] as const)
      .filter((entry) => Boolean(entry[1]));
    if (!selected.length) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const units = [...new Set(selected.map(([, series]) => series?.unit).filter(Boolean))];
    chart.setOption({
      animationDuration: 450,
      color: COLORS,
      backgroundColor: "transparent",
      grid: { left: 54, right: units.length > 1 ? 54 : 22, top: 45, bottom: 38 },
      legend: {
        top: 0,
        left: 0,
        textStyle: { color: "#9fb1bd", fontFamily: "Inter, system-ui", fontSize: 11 },
        itemWidth: 18,
        itemHeight: 3
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(8, 17, 24, .96)",
        borderColor: "#283b47",
        textStyle: { color: "#e8f0f3" },
        valueFormatter: (value: unknown) =>
          typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : String(value)
      },
      xAxis: {
        type: "time",
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#2b3d48" } },
        axisLabel: { color: "#758b98", hideOverlap: true },
        splitLine: { show: false }
      },
      yAxis: units.map((unit, index) => ({
        type: "value",
        position: index === 0 ? "left" : "right",
        name: unit,
        nameTextStyle: { color: "#758b98" },
        axisLabel: { color: "#758b98" },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(112, 142, 158, .11)" } },
        scale: true
      })),
      series: selected.map(([key, series], index) => ({
        id: key,
        name: series!.label,
        type: "line",
        yAxisIndex: Math.max(0, units.indexOf(series!.unit)),
        showSymbol: false,
        smooth: 0.22,
        connectNulls: false,
        lineStyle: { width: 2 },
        emphasis: { focus: "series" },
        data: series!.points.map((point) => [point.timestamp, point.value])
      }))
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [data, metrics]);

  return <div ref={ref} style={{ height }} role="img" aria-label="Telemetry time series chart" />;
}
