import { api } from "./api.js";
import {
  el,
  replace,
  setText,
  setTaxonomy,
  empty,
  title,
  badge,
  date,
  modeName,
} from "./utils.js";
import { bars } from "./charts.js";
import { renderAnalysis, renderClauses } from "./analysis.js";
let selected = null,
  lastAnalysis = null,
  historyOffset = 0,
  historyTotal = 0,
  deletion = null,
  requestToken = 0,
  historyToken = 0;
function notice(message, kind = "") {
  const node = document.getElementById("notice");
  node.hidden = !message;
  node.className = `notice ${kind}`;
  node.textContent = message;
}
function stat(value, label) {
  return el(
    "div",
    { class: "stat" },
    el("strong", {}, value),
    el("small", {}, label),
  );
}
function register(documents) {
  if (!documents.length)
    return empty(
      "Your document register is empty",
      "Upload your first agreement to see actual risks, evidence and portfolio statistics.",
    );
  const body = el(
    "tbody",
    {},
    documents.map((doc) =>
      el(
        "tr",
        {},
        el(
          "td",
          {},
          el(
            "button",
            {
              class: "document-link",
              onclick: () => (location.hash = `document/${doc.document_id}`),
            },
            el("strong", {}, doc.filename),
            el(
              "small",
              {},
              `${title(doc.document_type)}${doc.legacy_unverified ? " · historical / unverified" : ""}`,
            ),
          ),
        ),
        el(
          "td",
          {},
          el("span", { class: "number" }, Number(doc.risk_score).toFixed(1)),
        ),
        el("td", {}, badge(doc.overall_risk)),
        el("td", { class: "tiny" }, date(doc.created_at)),
        el(
          "td",
          {},
          el(
            "button",
            {
              class: "delete-small",
              "aria-label": `Delete analysis of ${doc.filename}`,
              onclick: () => askDelete(doc),
            },
            "Delete",
          ),
        ),
      ),
    ),
  );
  return el(
    "div",
    { class: "table-scroll" },
    el(
      "table",
      { class: "register-table" },
      el("caption", { class: "sr-only" }, "Stored document analyses"),
      el(
        "thead",
        {},
        el(
          "tr",
          {},
          ["DOCUMENT", "SCORE / 100", "RISK LEVEL", "ANALYZED", "ACTIONS"].map(
            (value) => el("th", { scope: "col" }, value),
          ),
        ),
      ),
      body,
    ),
  );
}
async function dashboard() {
  const data = await api.dashboard();
  replace(
    "portfolio-stats",
    stat(data.total_documents, "Analyzed documents"),
    stat(data.verified_documents, "Verified current analyses"),
    stat(data.legacy_unverified_documents, "Historical / unverified"),
    stat(data.average_risk.toFixed(1), "Verified average risk / 100"),
    stat(data.high_risk_documents, "Verified high / critical"),
  );
  replace(
    "portfolio-chart",
    el("p", { class: "chart-heading" }, "RISK DISTRIBUTION"),
    data.verified_documents
      ? bars(data.risk_distribution)
      : el(
          "p",
          { class: "tiny" },
          "No verified analyses yet — historical records remain available but are excluded from current risk statistics.",
        ),
  );
  replace(
    "portfolio-types",
    el("p", { class: "chart-heading" }, "DOCUMENT FAMILIES"),
    data.verified_documents
      ? bars(data.document_type_distribution)
      : el(
          "p",
          { class: "tiny" },
          "No verified document families to summarize.",
        ),
  );
  replace("recent-list", register(data.recent_documents));
}
async function history() {
  const token = ++historyToken;
  const offset = historyOffset;
  const data = await api.documents(offset);
  if (token !== historyToken || location.hash !== "#history") return;
  historyTotal = data.total;
  replace("history-list", register(data.documents));
  setText(
    "history-count",
    historyTotal
      ? `${offset + 1}–${Math.min(offset + 20, historyTotal)} of ${historyTotal}`
      : "0 documents",
  );
  document.getElementById("history-previous").disabled = historyOffset === 0;
  document.getElementById("history-next").disabled =
    historyOffset + 20 >= historyTotal;
}
function show(view) {
  for (const name of ["overview", "history", "analysis"]) {
    document.getElementById(`${name}-view`).hidden = name !== view;
    const link = document.getElementById(`nav-${name}`);
    link.classList.toggle("active", name === view);
    if (name === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  setText("page-label", title(view));
}
async function route() {
  const token = ++requestToken;
  const hash = location.hash.slice(1) || "overview";
  notice("");
  try {
    if (/^document\/\d+$/.test(hash)) {
      show("analysis");
      notice("Loading stored analysis…", "loading");
      const result = await api.document(hash.split("/")[1]);
      if (token !== requestToken) return;
      lastAnalysis = result;
      renderAnalysis(result);
      notice("");
    } else if (hash === "history") {
      show("history");
      await history();
    } else if (hash === "analysis") {
      show("analysis");
      if (lastAnalysis) renderAnalysis(lastAnalysis);
    } else {
      show("overview");
      await dashboard();
    }
  } catch (error) {
    if (token === requestToken) notice(error.message, "error");
  }
}
function select(file) {
  selected = file;
  setText("file-label", file ? file.name : "Choose a PDF or drop it here");
}
document
  .getElementById("file-input")
  .addEventListener("change", (event) => select(event.target.files[0] || null));
const drop = document.getElementById("drop-zone");
for (const name of ["dragenter", "dragover"])
  drop.addEventListener(name, (event) => {
    event.preventDefault();
    drop.classList.add("dragging");
  });
for (const name of ["dragleave", "drop"])
  drop.addEventListener(name, (event) => {
    event.preventDefault();
    drop.classList.remove("dragging");
  });
drop.addEventListener("drop", (event) =>
  select(event.dataTransfer.files[0] || null),
);
document
  .getElementById("upload-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selected) {
      notice("Choose a PDF to analyze.", "error");
      return;
    }
    if (!selected.name.toLowerCase().endsWith(".pdf")) {
      notice("Only PDF files are supported.", "error");
      return;
    }
    if (selected.size > 20 * 1024 * 1024) {
      notice("PDF exceeds the 20 MiB upload limit.", "error");
      return;
    }
    const button = document.getElementById("analyze-button");
    button.disabled = true;
    button.textContent = "Analyzing document…";
    document.getElementById("upload-form").setAttribute("aria-busy", "true");
    notice(
      "Extracting pages and evaluating clause evidence. Larger agreements may take longer.",
      "loading",
    );
    try {
      const result = await api.analyze(selected);
      lastAnalysis = result;
      renderAnalysis(result);
      select(null);
      document.getElementById("file-input").value = "";
      location.hash = `document/${result.document_id}`;
    } catch (error) {
      notice(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = "Analyze agreement ↗";
      document.getElementById("upload-form").removeAttribute("aria-busy");
    }
  });
for (const id of ["clause-search", "severity-filter", "method-filter"])
  document.getElementById(id).addEventListener("input", renderClauses);
document
  .getElementById("history-previous")
  .addEventListener("click", async () => {
    historyOffset = Math.max(0, historyOffset - 20);
    try {
      await history();
    } catch (error) {
      notice(error.message, "error");
    }
  });
document.getElementById("history-next").addEventListener("click", async () => {
  historyOffset += 20;
  try {
    await history();
  } catch (error) {
    notice(error.message, "error");
  }
});
function askDelete(doc) {
  deletion = doc;
  setText("delete-name", doc.filename);
  document.getElementById("delete-dialog").showModal();
  document.getElementById("cancel-delete").focus();
}
document
  .getElementById("cancel-delete")
  .addEventListener("click", () =>
    document.getElementById("delete-dialog").close(),
  );
document
  .getElementById("confirm-delete")
  .addEventListener("click", async () => {
    if (!deletion) return;
    const target = deletion;
    const button = document.getElementById("confirm-delete");
    button.disabled = true;
    try {
      await api.remove(target.document_id);
      document.getElementById("delete-dialog").close();
      if (lastAnalysis?.document_id === target.document_id) {
        lastAnalysis = null;
        document.getElementById("analysis-empty").hidden = false;
        document.getElementById("analysis-content").hidden = true;
      }
      historyOffset = Math.max(
        0,
        Math.min(
          historyOffset,
          Math.floor(Math.max(0, historyTotal - 2) / 20) * 20,
        ),
      );
      await route();
      notice("Analysis deleted.");
    } catch (error) {
      document.getElementById("delete-dialog").close();
      notice(error.message, "error");
    } finally {
      button.disabled = false;
      if (deletion === target) deletion = null;
    }
  });
window.addEventListener("hashchange", route);
async function boot() {
  try {
    const [model, taxonomy] = await Promise.all([api.model(), api.taxonomy()]);
    setTaxonomy(taxonomy);
    setText("system-mode", modeName(model.mode));
    setText(
      "system-model",
      model.model_loaded
        ? `${model.model_name} · ${model.version}`
        : "AI classifier unavailable",
    );
    await route();
  } catch (error) {
    notice(`Could not connect to RiskLens: ${error.message}`, "error");
    setText("system-mode", "Connection unavailable");
    setText("system-model", "Check the backend service");
  }
}
boot();
