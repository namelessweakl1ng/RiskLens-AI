import { el, title } from "./utils.js";
const colors = {
  Low: "#059669",
  low: "#059669",
  medium: "#d97706",
  Moderate: "#d97706",
  High: "#c2410c",
  high: "#c2410c",
  critical: "#b42318",
  Critical: "#b42318",
};
const NS = "http://www.w3.org/2000/svg";
function svg(tag, attrs, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs))
    node.setAttribute(key, String(value));
  node.append(...children);
  return node;
}
function svgText(attrs, value) {
  const node = svg("text", attrs);
  node.textContent = value;
  return node;
}
export function bars(values, label = title) {
  const total = Object.values(values).reduce((a, b) => a + b, 0);
  if (!total) return el("p", { class: "tiny" }, "No findings to chart.");
  return el(
    "div",
    { class: "bars" },
    Object.entries(values).map(([key, value]) => {
      const fill = el("div", {
        class: "bar-fill",
        style: `width:${(value / total) * 100}%;background:${colors[key] || "#059669"}`,
      });
      return el(
        "div",
        { class: "bar-line" },
        el("span", {}, label(key)),
        el("div", { class: "bar-track", "aria-hidden": "true" }, fill),
        el("span", {}, value),
      );
    }),
  );
}
export function gauge(score, severity) {
  const circumference = 2 * Math.PI * 70;
  const arc = svg("circle", {
    cx: 90,
    cy: 90,
    r: 70,
    fill: "none",
    stroke: colors[severity] || "#059669",
    "stroke-width": 9,
    "stroke-dasharray": circumference,
    "stroke-dashoffset": circumference,
    transform: "rotate(-90 90 90)",
  });
  const number = svgText(
    {
      x: 90,
      y: 92,
      "text-anchor": "middle",
      fill: "#111827",
      "font-size": 40,
      "font-weight": 500,
    },
    "0",
  );
  const root = svg(
    "svg",
    {
      viewBox: "0 0 180 180",
      class: "gauge",
      role: "img",
      "aria-label": `Risk score ${score} out of 100, ${severity}`,
    },
    svg("circle", {
      cx: 90,
      cy: 90,
      r: 70,
      fill: "none",
      stroke: "#e5e7eb",
      "stroke-width": 9,
    }),
    arc,
    number,
    svgText(
      {
        x: 90,
        y: 116,
        "text-anchor": "middle",
        fill: "#64748b",
        "font-size": 10,
        "letter-spacing": 2,
      },
      "RISK / 100",
    ),
  );
  const animate = !window.matchMedia("(prefers-reduced-motion: reduce)")
    .matches;
  const started = performance.now();
  function update(now) {
    const progress = animate ? Math.min((now - started) / 650, 1) : 1;
    const value = score * (1 - Math.pow(1 - progress, 3));
    number.textContent = value.toFixed(1);
    arc.setAttribute("stroke-dashoffset", circumference * (1 - value / 100));
    if (progress < 1 && root.isConnected) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
  return root;
}
