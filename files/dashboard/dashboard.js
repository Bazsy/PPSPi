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
const oneDecimal = (input, suffix = "") =>
  typeof input === "number" && Number.isFinite(input)
    ? `${input.toFixed(1)}${suffix}`
    : "—";
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
      : `Root ${oneDecimal(sample.root_available_percent, "%")} free`;
  byId("signal-state").textContent = value(sample.gps_fix);
  byId("signal-state").className =
    sample.gps_fix === "3D" || sample.gps_fix === "2D" ? "state-good" : "state-warn";
  byId("signal-detail").textContent = `PPS ${value(sample.pps_pulses).toLowerCase()}`;
  byId("temperature").textContent = oneDecimal(sample.temperature_celsius, "°C");
  byId("storage").textContent = `Boot ${oneDecimal(sample.boot_available_percent, "%")} free`;
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
    axis: { domain: [0, 3], labels: ["Error", "Unsync", "Fallback", "Healthy"] },
    series: [
      ["Timing", (sample) => sample.timing_collection_available === true ? healthScore(sample.timing_state) : null, "timing"],
      ["Host", (sample) => sample.host_collection_available === true ? healthScore(sample.host_state) : null, "host"],
    ],
  },
  signal: {
    title: "Satellites and PPS availability",
    axis: { includeZero: true, integer: true },
    series: [
      ["Satellites", (sample) => sample.timing_collection_available === true ? metricValue(sample.satellites_used) : null, "timing"],
      ["PPS", (sample) => sample.timing_collection_available === true && sample.pps_pulses !== null ? (sample.pps_pulses === "ACTIVE" ? 1 : 0) : null, "host", "binary"],
    ],
  },
  stratum: {
    title: "NTP stratum",
    series: [["Stratum", (sample) => sample.timing_collection_available === true ? metricValue(sample.stratum) : null, "timing"]],
    axis: { integer: true },
  },
  precision: {
    title: "Offset and root dispersion (µs)",
    axis: { includeZero: true, unit: "µs" },
    series: [
      ["Offset", (sample) => sample.timing_collection_available === true ? metricValue(sample.system_offset_seconds, 1e6) : null, "timing"],
      ["Dispersion", (sample) => sample.timing_collection_available === true ? metricValue(sample.root_dispersion_seconds, 1e6) : null, "host"],
    ],
  },
  thermal: {
    title: "Temperature and throttling",
    axis: { unit: "°C" },
    series: [
      ["Temperature °C", (sample) => sample.host_collection_available === true ? metricValue(sample.temperature_celsius) : null, "timing"],
      ["Throttled", (sample) => sample.host_collection_available === true && sample.throttled_flags !== null ? (sample.throttled_flags ? 1 : 0) : null, "host", "binary"],
    ],
  },
};

function niceStep(value, integer) {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const fraction = value / magnitude;
  const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return Math.max(integer ? 1 : Number.MIN_VALUE, niceFraction * magnitude);
}

function buildScale(values, options = {}) {
  if (Array.isArray(options.domain)) {
    const [minimum, maximum] = options.domain;
    const tickCount = options.labels ? options.labels.length : 4;
    return {
      minimum,
      maximum,
      ticks: Array.from(
        { length: tickCount },
        (_, index) => minimum + ((maximum - minimum) * index) / (tickCount - 1),
      ),
    };
  }
  let minimum = Math.min(...values);
  let maximum = Math.max(...values);
  if (options.includeZero) {
    minimum = Math.min(0, minimum);
    maximum = Math.max(0, maximum);
  }
  if (minimum === maximum) {
    const padding = options.integer ? 1 : Math.max(Math.abs(minimum) * 0.1, 1);
    minimum -= padding;
    maximum += padding;
    if (options.includeZero) minimum = Math.min(0, minimum);
  }
  const step = niceStep((maximum - minimum) / 4, options.integer === true);
  const niceMinimum = Math.floor(minimum / step) * step;
  const niceMaximum = Math.ceil(maximum / step) * step;
  const ticks = [];
  for (let tick = niceMinimum; tick <= niceMaximum + step / 2; tick += step) {
    ticks.push(Number(tick.toPrecision(12)));
  }
  return { minimum: niceMinimum, maximum: niceMaximum, ticks };
}

function formatAxisNumber(number) {
  const absolute = Math.abs(number);
  if (absolute >= 100 || Number.isInteger(number)) return number.toFixed(0);
  if (absolute >= 1) return number.toFixed(1).replace(/\.0$/, "");
  if (absolute >= 0.01) return number.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  return number.toExponential(1);
}

function formatAxisTick(number, options, index) {
  if (options.labels) return options.labels[index] || formatAxisNumber(number);
  return `${formatAxisNumber(number)}${options.unit ? ` ${options.unit}` : ""}`;
}

function renderLegend(definition) {
  const legend = byId("chart-legend");
  legend.replaceChildren();
  definition.series.forEach(([name, , cssClass]) => {
    const item = document.createElement("span");
    const key = document.createElement("i");
    key.className = `${cssClass}-key`;
    key.setAttribute("aria-hidden", "true");
    item.append(key, document.createTextNode(name));
    legend.append(item);
  });
}

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
  renderLegend(definition);
  const values = definition.series
    .filter(([, , , axis]) => axis !== "binary")
    .flatMap(([, getter]) => samples.map(getter))
    .filter(Number.isFinite);
  if (!values.length) {
    empty.hidden = false;
    chart.hidden = true;
    chart.querySelector("desc").textContent = "No finite samples are available for this metric.";
    return;
  }
  const scale = buildScale(values, definition.axis);
  const span = scale.maximum - scale.minimum;
  const plotLeft = 112;
  const plotRight = definition.series.some(([, , , axis]) => axis === "binary") ? 875 : 970;
  const x = (index) => plotLeft + (samples.length === 1 ? (plotRight - plotLeft) / 2 : (index * (plotRight - plotLeft)) / (samples.length - 1));
  const y = (number, axis) => axis === "binary" ? 210 - number * 180 : 210 - ((number - scale.minimum) / span) * 180;
  scale.ticks.forEach((tick, index) => {
    const position = y(tick);
    chart.append(svg("line", { x1: plotLeft, y1: position, x2: plotRight, y2: position, class: "grid" }));
    const label = svg("text", { x: plotLeft - 14, y: position + 7, class: "axis", "text-anchor": "end" });
    label.textContent = formatAxisTick(tick, definition.axis, index);
    chart.append(label);
  });
  if (definition.series.some(([, , , axis]) => axis === "binary")) {
    [[30, "On"], [210, "Off"]].forEach(([position, text]) => {
      const label = svg("text", { x: plotRight + 14, y: position + 7, class: "axis", "text-anchor": "start" });
      label.textContent = text;
      chart.append(label);
    });
  }
  definition.series.forEach(([, getter, cssClass, axis]) => {
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
      segment.push(`${x(index)},${y(number, axis)}`);
    });
    flush();
  });
  chart.querySelector("desc").textContent = `${samples.length} sanitized samples. ${definition.series.map(([name]) => name).join(" and ")}. Y-axis ${formatAxisTick(scale.minimum, definition.axis, 0)} to ${formatAxisTick(scale.maximum, definition.axis, scale.ticks.length - 1)}.`;
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

function initializeDashboard() {
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
}

if (typeof document !== "undefined") initializeDashboard();
if (typeof module !== "undefined") {
  module.exports = { buildScale, formatAxisNumber, formatAxisTick, oneDecimal };
}
