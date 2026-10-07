import {
  el,
  replace,
  setText,
  title,
  badge,
  percent,
  riskName,
  modeName,
  empty,
  date,
} from "./utils.js";
import { bars, gauge } from "./charts.js";
let current = null;
const labels = {
  clause_coverage: [
    "Clause coverage",
    "Clauses with completed analysis / extracted clauses",
  ],
  model_coverage: [
    "Model coverage",
    "Clauses with valid model inference / analyzed clauses",
  ],
  evidence_coverage: [
    "Evidence coverage",
    "Material findings with explicit support / material findings",
  ],
  high_risk_density: [
    "High-risk density",
    "High or critical clauses / analyzed clauses",
  ],
  safe_clause_ratio: [
    "No-finding ratio",
    "Clauses without material findings / analyzed clauses; not a guarantee of safety",
  ],
  extraction_quality: [
    "Extraction quality",
    "Text-bearing pages / total pages; not a measure of extraction accuracy",
  ],
  classification_strength: [
    "Classification strength",
    "Matched winning-family signals / all matched signals; not a probability",
  ],
};
function fact(name, value) {
  return el("div", {}, el("small", {}, name), el("strong", {}, value));
}
function intelligence(name, value) {
  return el(
    "div",
    { class: "intelligence-row" },
    el("span", {}, name),
    el("strong", {}, value),
  );
}
export function renderAnalysis(result) {
  current = result;
  document.getElementById("analysis-empty").hidden = true;
  document.getElementById("analysis-content").hidden = false;
  setText("analysis-title", result.filename);
  setText(
    "analysis-subtitle",
    `${title(result.classification.document_type)} · ${result.clause_count} clauses · ${result.page_count || "Unknown"} pages · ${date(result.created_at)}`,
  );
  const status = result.model_status;
  replace(
    "analysis-hero",
    gauge(result.risk_score, result.overall_risk),
    el(
      "div",
      { class: "hero-copy" },
      el("span", { class: "eyebrow" }, "OVERALL TRIAGE ASSESSMENT"),
      el("h2", {}, `${result.overall_risk} risk · review the evidence`),
      badge(result.overall_risk),
      el(
        "p",
        { class: status.model_loaded ? "tiny" : "model-warning" },
        status.model_loaded
          ? modeName(result.mode)
          : result.legacy_unverified
            ? "Historical evidence is unverified — reanalyze the source PDF."
            : "AI classifier unavailable — this analysis uses transparent rules.",
      ),
      el(
        "div",
        { class: "hero-facts" },
        fact("Analysis mode", modeName(result.mode)),
        fact("Model version", status.version || "Not deployed"),
        fact(
          "Classification strength",
          percent(result.classification.classification_strength),
        ),
        fact("Document type", title(result.classification.document_type)),
        fact(
          "Material clauses",
          result.clauses.filter((c) => c.findings.length || (result.legacy_unverified && c.predicted_label !== "no_risk")).length,
        ),
        fact(
          "Model device",
          status.model_loaded ? status.device : "Not applicable",
        ),
      ),
    ),
  );
  setText("executive-summary", result.executive_summary);
  replace(
    "recommended-actions",
    el("h3", {}, "Recommended review actions"),
    result.recommended_actions.length
      ? el(
          "ol",
          { class: "actions-list" },
          result.recommended_actions.map((action) => el("li", {}, action)),
        )
      : el(
          "p",
          { class: "tiny" },
          "No configured material risk detected. Verify the original agreement and terms you rely on.",
        ),
  );
  replace(
    "severity-chart",
    el("p", { class: "chart-heading" }, "CLAUSE SEVERITY"),
    bars(result.severity_distribution),
  );
  replace(
    "category-chart",
    el("p", { class: "chart-heading" }, "MATERIAL CATEGORY FINDINGS"),
    bars(result.category_distribution, riskName),
  );
  setText(
    "safe-ratio",
    `${percent(result.health.safe_clause_ratio)} of clauses have no material finding. These clauses are not certified safe.`,
  );
  const categories = Object.entries(result.category_distribution);
  setText("risk-card-count", `${categories.length} detected categories`);
  replace(
    "risk-cards",
    categories.length
      ? categories.map(([category, count]) => {
          const support = result.clauses.filter((c) =>
            c.findings.some((f) => f.category === category) || (result.legacy_unverified && c.predicted_label === category),
          );
          const finding = support
            .flatMap((c) => c.findings)
            .find((f) => f.category === category);
          const models = support.filter(
            (c) => c.model_label === category && c.model_confidence !== null,
          );
          const confidence = models.length
            ? `Top model confidence: ${percent(Math.max(...models.map((c) => c.model_confidence)))}`
            : "No model confidence — rule evidence";
          const method = [
            ...new Set(
              support.flatMap((c) =>
                c.findings
                  .filter((f) => f.category === category)
                  .map((f) => f.detection_method),
              ),
            ),
          ].join(" / ");
          return el(
            "article",
            { class: `risk-card ${finding?.severity || support[0]?.severity || "low"}` },
            badge(finding?.severity || support[0]?.severity || "low"),
            el("h3", {}, riskName(category)),
            el(
              "p",
              {},
              finding?.explanation ||
                "Historical finding — evidence unverified.",
            ),
            el(
              "p",
              { class: "recommendation" },
              finding?.recommendation || "Reanalyze the original PDF.",
            ),
            el(
              "span",
              { class: "tiny" },
              `${count} supporting findings · ${method || "unverified"}`,
            ),
            el("span", { class: "tiny" }, confidence),
          );
        })
      : empty(
          "No material risk categories detected",
          "This reflects the available model and configured rules, not a certification that the agreement is safe.",
        ),
  );
  setText("clause-count", `${result.clause_count} CLAUSES`);
  document.getElementById("clause-search").value = "";
  document.getElementById("severity-filter").value = "";
  document.getElementById("method-filter").value = "";
  renderClauses();
  replace(
    "health-indicators",
    Object.entries(result.health).map(([key, value]) =>
      el(
        "div",
        { class: "health-row" },
        el(
          "div",
          {},
          labels[key]?.[0] || title(key),
          el("small", {}, labels[key]?.[1] || ""),
        ),
        el("strong", {}, percent(value)),
      ),
    ),
  );
  const inferred = result.clauses.filter((c) => c.model_confidence !== null);
  const agreed = inferred.filter((c) =>
    c.findings.some((f) => f.detection_method === "hybrid"),
  ).length;
  const top = inferred.reduce(
    (best, c) =>
      !best || c.model_confidence > best.model_confidence ? c : best,
    null,
  );
  replace(
    "model-intelligence",
    intelligence("Analysis mode", modeName(result.mode)),
    intelligence(
      "Classifier",
      status.model_loaded ? "Loaded" : "AI classifier unavailable",
    ),
    intelligence("Model version", status.version || "Not deployed"),
    intelligence("Base checkpoint", status.base_model),
    intelligence(
      "Top prediction",
      top
        ? `${riskName(top.model_label)} (${percent(top.model_confidence)})`
        : "No model predictions",
    ),
    intelligence(
      "Rule/model agreement",
      inferred.length
        ? `${agreed} clauses (${percent(agreed / inferred.length)})`
        : "Not applicable",
    ),
    intelligence(
      "Classifier signal",
      status.load_error || "Domain labels validated",
    ),
    el(
      "p",
      { class: "tiny" },
      "Agreement ratio is descriptive, not model accuracy. Open any clause to see its complete probability distribution and rule evidence.",
    ),
  );
  replace(
    "score-breakdown",
    el(
      "p",
      {},
      "0–100 triage heuristic, not a calibrated estimate of loss. Duplicate clauses do not add to the score.",
    ),
    intelligence("Formula", result.scoring.formula_version),
    intelligence(
      "Strongest weighted evidence",
      result.scoring.strongest_evidence.toFixed(3),
    ),
    intelligence(
      "Mean of top 3 categories",
      result.scoring.top_three_mean.toFixed(3),
    ),
    intelligence(
      "Category diversity",
      result.scoring.category_diversity.toFixed(3),
    ),
    el(
      "p",
      {},
      "Score = 100 × (0.65 × strongest + 0.25 × top-three mean + 0.10 × diversity). Rule strength is a scoring heuristic, never ML confidence.",
    ),
    ...Object.entries(result.scoring.category_contributions).map(
      ([key, value]) => intelligence(riskName(key), value.toFixed(3)),
    ),
  );
}
function expandedContent(clause) {
  const model = el(
    "div",
    {},
    el("h3", {}, "Model probability distribution"),
    Object.keys(clause.class_probabilities).length
      ? bars(clause.class_probabilities, riskName)
      : el("p", {}, "No model inference — no probability is available."),
  );
  const rules = el(
    "div",
    {},
    el("h3", {}, "Rule evidence"),
    clause.rule_matches.length
      ? clause.rule_matches.map((match) =>
          el(
            "p",
            {},
            `${match.rule}: “${match.matched_text}” (clause offsets ${match.start_offset}–${match.end_offset})`,
          ),
        )
      : el("p", {}, "No configured rule matched."),
  );
  return el(
    "div",
    {},
    clause.disagreement
      ? el(
          "p",
          { class: "disagreement" },
          `Model/rule disagreement: model suggests ${riskName(clause.model_label)}; rule evidence is retained for review.`,
        )
      : null,
    el("blockquote", {}, clause.text),
    el("div", { class: "expanded-grid" }, model, rules),
    el("h3", {}, "Explanation"),
    el("p", {}, clause.explanation),
    el("h3", {}, "Recommendation"),
    el("p", {}, clause.recommendation),
    ...clause.findings
      .filter((f) => f.category !== clause.predicted_label)
      .map((f) =>
        el(
          "p",
          {},
          `${riskName(f.category)}: ${f.explanation} ${f.recommendation}`,
        ),
      ),
  );
}
export function renderClauses() {
  if (!current) return;
  const query = document
    .getElementById("clause-search")
    .value.trim()
    .toLowerCase();
  const severity = document.getElementById("severity-filter").value;
  const method = document.getElementById("method-filter").value;
  const filtered = current.clauses.filter(
    (c) =>
      (!severity || c.severity === severity) &&
      (!method || c.detection_method === method) &&
      (!query ||
        [
          c.text,
          riskName(c.predicted_label),
          ...c.rule_matches.map((m) => m.matched_text),
        ]
          .join(" ")
          .toLowerCase()
          .includes(query)),
  );
  setText(
    "filter-status",
    `${filtered.length} of ${current.clauses.length} clauses shown`,
  );
  const rows = [];
  for (const clause of filtered) {
    const detailId = `clause-detail-${clause.clause_id}`;
    const button = el(
      "button",
      {
        class: "clause-preview",
        "aria-expanded": "false",
        "aria-controls": detailId,
      },
      clause.text.length > 170 ? clause.text.slice(0, 170) + "…" : clause.text,
      el("span", {}, "Expand evidence ↓"),
    );
    const confidence =
      clause.model_confidence === null
        ? "Not available"
        : `${percent(clause.model_confidence)} · ${riskName(clause.model_label)}`;
    const row = el(
      "tr",
      {},
      el("td", {}, clause.page_number ?? "Unknown"),
      el("td", {}, button),
      el("td", {}, clause.detection_method === "uncertain" ? "Uncertain prediction" : riskName(clause.predicted_label)),
      el("td", {}, badge(clause.severity)),
      el("td", {}, el("span", { class: "tiny" }, confidence)),
      el(
        "td",
        {},
        el(
          "span",
          { class: "tag" },
          clause.detection_method === "safe"
            ? "No finding"
            : clause.detection_method === "legacy_unverified" ? "Historical / unverified" : title(clause.detection_method),
        ),
      ),
      el(
        "td",
        {},
        clause.rule_matches.length
          ? clause.rule_matches.map((m) =>
              el("span", { class: "rule-token" }, m.matched_text),
            )
          : el(
              "span",
              { class: "tiny" },
              clause.class_probabilities &&
                Object.keys(clause.class_probabilities).length
                ? "Model distribution"
                : "No material evidence",
            ),
      ),
    );
    const details = el(
      "tr",
      { class: "expanded-row", id: detailId, hidden: "" },
      el("td", { colspan: 7 }, expandedContent(clause)),
    );
    button.addEventListener("click", () => {
      details.hidden = !details.hidden;
      button.setAttribute("aria-expanded", String(!details.hidden));
      button.lastChild.textContent = details.hidden
        ? "Expand evidence ↓"
        : "Collapse evidence ↑";
    });
    rows.push(row, details);
  }
  replace(
    "clause-rows",
    rows.length
      ? rows
      : [
          el(
            "tr",
            {},
            el("td", { colspan: 7 }, "No clauses match these filters."),
          ),
        ],
  );
}
