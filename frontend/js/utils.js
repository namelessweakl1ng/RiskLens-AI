export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith("on") && typeof value === "function")
      node.addEventListener(key.slice(2), value);
    else if (value !== null && value !== undefined)
      node.setAttribute(key, String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(
      child instanceof Node ? child : document.createTextNode(String(child)),
    );
  }
  return node;
}
export function setText(id, value) {
  document.getElementById(id).textContent = value;
}
export function replace(id, ...nodes) {
  document.getElementById(id).replaceChildren(...nodes.flat());
}
export function percent(value) {
  return value === null || value === undefined
    ? "Unavailable"
    : `${Math.round(value * 100)}%`;
}
export function date(value) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? value
    : parsed.toLocaleString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}
export function title(value) {
  return String(value || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (x) => x.toUpperCase());
}
export function badge(value) {
  return el(
    "span",
    { class: `severity ${String(value).toLowerCase()}` },
    title(value),
  );
}
let taxonomy = {};
export function setTaxonomy(value) {
  taxonomy = value;
}
export function riskName(label) {
  return taxonomy[label]?.display_name || title(label);
}
export function modeName(value) {
  return value === "hybrid"
    ? "Hybrid AI + Rules"
    : value === "legacy_unverified"
      ? "Historical / unverified"
      : "Rule-only analysis";
}
export function empty(heading, message) {
  return el(
    "div",
    { class: "empty-state" },
    el("span", { class: "empty-symbol", "aria-hidden": "true" }, "⌕"),
    el("h2", {}, heading),
    el("p", {}, message),
  );
}
