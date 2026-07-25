"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const byId = (id) => document.getElementById(id);
const labels = {
  HEALTHY_PPS: "PPS locked",
  NETWORK_FALLBACK: "Network fallback",
  UNSYNCHRONIZED: "Unsynchronized",
  HARDWARE_ERROR: "Hardware error",
  HEALTHY: "Healthy",
  WARNING: "Warning",
  CRITICAL: "Critical",
  UNKNOWN: "Unknown",
};
const stateClass = (state) =>
  state === "HEALTHY_PPS" || state === "HEALTHY"
    ? "state-good"
    : state === "NETWORK_FALLBACK" || state === "WARNING" || state === "UNKNOWN"
      ? "state-warn"
      : "state-bad";
const value = (input, suffix = "") =>
  input === null || input === undefined ? "—" : `${input}${suffix}`;
const metricValue = (input, scale = 1) =>
  input === null || input === undefined ? null : Number(input) * scale;
const formatTime = (input) =>
  input
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(input),
      )
    : "—";
const formatSeconds = (input) => {
  if (input === null || input === undefined) return "—";
  const absolute = Math.abs(input);
  if (absolute < 0.000001) return `${(input * 1e9).toFixed(1)} ns`;
  if (absolute < 0.001) return `${(input * 1e6).toFixed(2)} µs`;
  return `${(input * 1e3).toFixed(2)} ms`;
};

function setState(id, state) {
  const node = byId(id);
  node.textContent = labels[state] || "Unknown";
  node.className = stateClass(state);
}

function renderLatest(sample) {
  if (!sample) {
    setState("timing-state", "UNKNOWN");
    setState("host-state", "UNKNOWN");
    for (const id of ["timing-detail", "host-detail", "signal-state", "signal-detail", "temperature", "storage", "source", "satellites", "rtc", "stratum", "offset", "dispersion", "timing-transition", "host-transition", "updates", "sample-time"]) {
      byId(id).textContent = "—";
    }
    return;
  }
  setState(
    "timing-state",
    sample.timing_collection_available === true ? sample.timing_state : "UNKNOWN",
  );
  setState(
    "host-state",
    sample.host_collection_available === true ? sample.host_state : "UNKNOWN",
  );
  byId("timing-detail").textContent =
    sample.timing_collection_available === false
      ? "Collector unavailable"
      : `${value(sample.selected_source)} source · ${value(sample.pps_pulses)}`;
  byId("host-detail").textContent =
    sample.host_collection_available === false
      ? "Collector unavailable"
      : `Root ${value(sample.root_available_percent, "%")} free`;
  byId("signal-state").textContent = value(sample.gps_fix);
  byId("signal-state").className =
    sample.gps_fix === "3D" || sample.gps_fix === "2D" ? "state-good" : "state-warn";
  byId("signal-detail").textContent = `PPS ${value(sample.pps_pulses).toLowerCase()}`;
  byId("temperature").textContent = value(sample.temperature_celsius, "°C");
  byId("storage").textContent = `Boot ${value(sample.boot_available_percent, "%")} free`;
  byId("source").textContent = value(sample.selected_source);
  byId("satellites").textContent = value(sample.satellites_used);
  byId("rtc").textContent = sample.rtc_available === true ? "Available" : sample.rtc_available === false ? "Unavailable" : "—";
  byId("stratum").textContent = value(sample.stratum);
  byId("offset").textContent = formatSeconds(sample.system_offset_seconds);
  byId("dispersion").textContent = formatSeconds(sample.root_dispersion_seconds);
  const transitionText = (transition) =>
    transition
      ? `${labels[transition.from] || transition.from} → ${labels[transition.to] || transition.to} · ${formatTime(transition.at)}`
      : "No recorded transition";
  byId("timing-transition").textContent = transitionText(sample.timing_transition);
  byId("host-transition").textContent = transitionText(sample.host_transition);
  byId("updates").textContent = `${value(sample.update_status)}${sample.reboot_required ? " · reboot pending" : ""}`;
  byId("sample-time").textContent = formatTime(sample.sampled_at);
  const age = Math.max(0, Math.round((Date.now() - new Date(sample.sampled_at).getTime()) / 60000));
  byId("freshness").textContent = age < 1 ? "Sampled just now" : `Sampled ${age} min ago`;
}

function svg(name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, val]) => node.setAttribute(key, String(val)));
  return node;
}

function healthScore(state) {
  if (state === "HEALTHY_PPS" || state === "HEALTHY") return 3;
  if (state === "NETWORK_FALLBACK" || state === "WARNING") return 2;
  if (state === "UNSYNCHRONIZED" || state === "UNKNOWN") return 1;
  return 0;
}

const metricDefinitions = {
  health: {
    title: "Appliance health",
    series: [
      ["Timing", (sample) => sample.timing_collection_available === true ? healthScore(sample.timing_state) : null, "timing"],
      ["Host", (sample) => sample.host_collection_available === true ? healthScore(sample.host_state) : null, "host"],
    ],
  },
  signal: {
    title: "Satellites and PPS availability",
    series: [
      ["Satellites", (sample) => sample.timing_collection_available === true ? metricValue(sample.satellites_used) : null, "timing"],
      ["PPS", (sample) => sample.timing_collection_available === true && sample.pps_pulses !== null ? (sample.pps_pulses === "ACTIVE" ? 1 : 0) : null, "host"],
    ],
  },
  stratum: {
    title: "NTP stratum",
    series: [["Stratum", (sample) => sample.timing_collection_available === true ? metricValue(sample.stratum) : null, "timing"]],
  },
  precision: {
    title: "Offset and root dispersion (µs)",
    series: [
      ["Offset", (sample) => sample.timing_collection_available === true ? metricValue(sample.system_offset_seconds, 1e6) : null, "timing"],
      ["Dispersion", (sample) => sample.timing_collection_available === true ? metricValue(sample.root_dispersion_seconds, 1e6) : null, "host"],
    ],
  },
  thermal: {
    title: "Temperature and throttling",
    series: [
      ["Temperature °C", (sample) => sample.host_collection_available === true ? metricValue(sample.temperature_celsius) : null, "timing"],
      ["Throttled", (sample) => sample.host_collection_available === true && sample.throttled_flags !== null ? (sample.throttled_flags ? 1 : 0) : null, "host"],
    ],
  },
};

function renderChart(samples) {
  const chart = byId("history-chart");
  Array.from(chart.children)
    .filter((node) => !node.matches("title,desc"))
    .forEach((node) => node.remove());
  const empty = byId("empty-state");
  empty.hidden = samples.length > 0;
  chart.hidden = samples.length === 0;
  if (!samples.length) {
    chart.querySelector("desc").textContent = "No samples available.";
    return;
  }
  const definition = metricDefinitions[byId("metric").value] || metricDefinitions.health;
  byId("history-title").textContent = definition.title;
  const values = definition.series.flatMap(([, getter]) => samples.map(getter)).filter(Number.isFinite);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum === minimum ? 1 : maximum - minimum;
  const x = (index) => 36 + (samples.length === 1 ? 472 : (index * 944) / (samples.length - 1));
  const y = (number) => 210 - ((number - minimum) / span) * 180;
  [30, 90, 150, 210].forEach((position) =>
    chart.append(svg("line", { x1: 36, y1: position, x2: 980, y2: position, class: "grid" })),
  );
  definition.series.forEach(([, getter, cssClass]) => {
    let segment = [];
    const flush = () => {
      if (segment.length) {
        chart.append(svg("polyline", { points: segment.join(" "), class: cssClass }));
        segment = [];
      }
    };
    samples.forEach((sample, index) => {
      const number = getter(sample);
      if (!Number.isFinite(number)) {
        flush();
        return;
      }
      segment.push(`${x(index)},${y(number)}`);
    });
    flush();
  });
  chart.querySelector("desc").textContent = `${samples.length} sanitized samples. ${definition.series.map(([name]) => name).join(" and ")}.`;
}

let currentSamples = [];
async function load(hours) {
  byId("freshness").textContent = "Refreshing local history…";
  try {
    const response = await fetch(`/api/v1/dashboard?hours=${hours}`, {
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("unavailable");
    const payload = await response.json();
    currentSamples = payload.samples;
    renderLatest(payload.latest);
    renderChart(currentSamples);
    if (!payload.latest) byId("freshness").textContent = "No samples yet";
  } catch (_error) {
    byId("freshness").textContent = "Dashboard data unavailable";
    currentSamples = [];
    renderLatest(null);
    renderChart([]);
  }
}

document.querySelectorAll("[data-hours]").forEach((button) =>
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-hours]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    load(button.dataset.hours);
  }),
);
byId("metric").addEventListener("change", () => renderChart(currentSamples));
load("24");
setInterval(() => {
  const active = document.querySelector("[data-hours].active");
  load(active ? active.dataset.hours : "24");
}, 120000);
