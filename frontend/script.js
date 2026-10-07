/* =========================================================
   DASHBOARD ANALYSIS
   ========================================================= */


/* ---------------------------------------------------------
   LOAD DASHBOARD
   --------------------------------------------------------- */

async function loadDashboard() {

    try {

        const response = await fetch("/api/dashboard");

        if (!response.ok) {
            throw new Error(
                `Dashboard request failed: ${response.status}`
            );
        }

        const data = await response.json();

        console.log("DASHBOARD DATA:", data);

        renderDashboard(data);

    } catch (error) {

        console.error(
            "Dashboard loading error:",
            error
        );

        // Keep existing localStorage fallback
        if (
            typeof state !== "undefined" &&
            Array.isArray(state.reviews)
        ) {

            renderDashboard({
                statistics: {
                    total_documents:
                        state.reviews.length,

                    high_risk: 0,
                    medium_risk: 0,
                    low_risk: 0,
                    average_risk_score: 0
                },

                recent_analyses:
                    state.reviews
            });
        }
    }
}


/* ---------------------------------------------------------
   RENDER DASHBOARD
   --------------------------------------------------------- */

function renderDashboard(data) {

    console.log(
        "Rendering dashboard:",
        data
    );


    const stats =
        data.statistics || {};


    /* ---------------------------------------------
       STATISTICS
       --------------------------------------------- */

    const totalDocuments =
        Number(
            stats.total_documents ??
            stats.total_reviews ??
            stats.documents_count ??
            0
        );


    const highRisk =
        Number(
            stats.high_risk ??
            stats.high ??
            stats.high_risk_count ??
            0
        );


    const mediumRisk =
        Number(
            stats.medium_risk ??
            stats.medium ??
            stats.medium_risk_count ??
            0
        );


    const lowRisk =
        Number(
            stats.low_risk ??
            stats.low ??
            stats.low_risk_count ??
            0
        );


    const averageRisk =
        Number(
            stats.average_risk_score ??
            stats.average_score ??
            0
        );


    const totalClauses =
        Number(
            stats.total_clauses ??
            stats.clauses_analyzed ??
            stats.clauses ??
            0
        );


    /* ---------------------------------------------
       DISPLAY DASHBOARD STATS
       --------------------------------------------- */

    renderDashboardStats({

        totalDocuments,
        highRisk,
        mediumRisk,
        lowRisk,
        averageRisk,
        totalClauses

    });


    /* ---------------------------------------------
       IMPORTANT:
       BACKEND RETURNS recent_analyses
       --------------------------------------------- */

    const recent =
        Array.isArray(data.recent_analyses)
            ? data.recent_analyses

            : Array.isArray(data.recent_reviews)
                ? data.recent_reviews

                : Array.isArray(data.recent_documents)
                    ? data.recent_documents

                    : Array.isArray(data.documents)
                        ? data.documents

                        : [];


    console.log(
        "RECENT ANALYSES:",
        recent
    );


    renderRecentReviews(recent);
}


/* ---------------------------------------------------------
   DASHBOARD STATISTICS
   --------------------------------------------------------- */

function renderDashboardStats(stats) {

    const dashboard =
        document.getElementById("dashboard");

    if (!dashboard) {
        return;
    }


    let statsContainer =
        document.getElementById("dashboardStats");


    if (!statsContainer) {

        statsContainer =
            document.createElement("div");

        statsContainer.id =
            "dashboardStats";


        const sectionHead =
            dashboard.querySelector(".section-head");


        if (sectionHead) {

            sectionHead.parentNode.insertBefore(
                statsContainer,
                sectionHead
            );

        } else {

            dashboard.prepend(
                statsContainer
            );
        }
    }


    statsContainer.innerHTML = `

        <div class="dashboard-stats-grid">

            <div class="stat-card">

                <span class="stat-label">
                    TOTAL DOCUMENTS
                </span>

                <strong>
                    ${stats.totalDocuments}
                </strong>

            </div>


            <div class="stat-card">

                <span class="stat-label">
                    HIGH RISK
                </span>

                <strong>
                    ${stats.highRisk}
                </strong>

            </div>


            <div class="stat-card">

                <span class="stat-label">
                    MEDIUM RISK
                </span>

                <strong>
                    ${stats.mediumRisk}
                </strong>

            </div>


            <div class="stat-card">

                <span class="stat-label">
                    LOW RISK
                </span>

                <strong>
                    ${stats.lowRisk}
                </strong>

            </div>


            <div class="stat-card">

                <span class="stat-label">
                    AVG RISK SCORE
                </span>

                <strong>
                    ${stats.averageRisk.toFixed(1)}
                </strong>

                <small>
                    /100
                </small>

            </div>


            <div class="stat-card">

                <span class="stat-label">
                    CLAUSES ANALYSED
                </span>

                <strong>
                    ${stats.totalClauses}
                </strong>

            </div>

        </div>
    `;
}


/* ---------------------------------------------------------
   RECENT ANALYSES
   --------------------------------------------------------- */

function renderRecentReviews(items) {

    const container =
        document.getElementById("recentReviews");


    if (!container) {

        console.error(
            "recentReviews element not found"
        );

        return;
    }


    if (
        !Array.isArray(items) ||
        items.length === 0
    ) {

        container.innerHTML = `

            <div class="dashboard-no-clauses">

                No document analyses available yet.

            </div>

        `;

        return;
    }


    container.innerHTML = `

        <div class="dashboard-analysis-list">

            ${items.map((item, index) => {

                const id =
                    item.id ??
                    item.document_id ??
                    index;


                const filename =
                    item.filename ||
                    "Unnamed Document";


                const documentType =
                    item.document_type ||
                    "Financial Agreement";


                const score =
                    Number(
                        item.risk_score || 0
                    );


                const overallRisk =
                    String(
                        item.overall_risk ||
                        "Pending"
                    );


                const high =
                    Number(
                        item.high_risk_count ||
                        item.high ||
                        0
                    );


                const medium =
                    Number(
                        item.medium_risk_count ||
                        item.medium ||
                        0
                    );


                const low =
                    Number(
                        item.low_risk_count ||
                        item.low ||
                        0
                    );


                const clauseCount =
                    Number(
                        item.clause_count ||
                        item.total_clauses ||
                        item.clauses_analyzed ||
                        0
                    );


                const riskClass =
                    overallRisk
                        .toLowerCase()
                        .replace(/\s+/g, "-");


                return `

                    <div
                        class="dashboard-analysis-card"
                        data-document-id="${id}"
                    >

                        <!-- TOP -->

                        <div
                            class="dashboard-analysis-top"
                        >

                            <div
                                class="dashboard-analysis-file"
                            >

                                <div class="pdf-badge">
                                    PDF
                                </div>


                                <div>

                                    <strong>
                                        ${escapeHTML(
                                            filename
                                        )}
                                    </strong>


                                    <small>
                                        ${escapeHTML(
                                            documentType
                                        )}
                                    </small>

                                </div>

                            </div>


                            <div
                                class="
                                    dashboard-analysis-score
                                    ${riskClass}
                                "
                            >

                                <strong>
                                    ${score}
                                </strong>

                                <span>
                                    /100
                                </span>

                                <em>
                                    ${escapeHTML(
                                        overallRisk
                                    )}
                                </em>

                            </div>

                        </div>


                        <!-- RISK SUMMARY -->

                        <div
                            class="
                                dashboard-analysis-summary
                            "
                        >

                            <div>

                                <span>
                                    HIGH RISK
                                </span>

                                <strong>
                                    ${high}
                                </strong>

                            </div>


                            <div>

                                <span>
                                    MEDIUM RISK
                                </span>

                                <strong>
                                    ${medium}
                                </strong>

                            </div>


                            <div>

                                <span>
                                    LOW RISK
                                </span>

                                <strong>
                                    ${low}
                                </strong>

                            </div>


                            <div>

                                <span>
                                    CLAUSES
                                </span>

                                <strong>
                                    ${clauseCount}
                                </strong>

                            </div>

                        </div>


                        <!-- DETAILS BUTTON -->

                        <button
                            type="button"
                            class="dashboard-details-btn"
                            onclick="
                                toggleDashboardDetails(
                                    ${id},
                                    this
                                )
                            "
                        >

                            View Analysis Details ↓

                        </button>


                        <!-- DETAILS CONTAINER -->

                        <div
                            id="dashboard-details-${id}"
                            class="
                                dashboard-document-details
                            "
                            style="display:none;"
                        >

                        </div>

                    </div>

                `;

            }).join("")}

        </div>
    `;
}


/* =========================================================
   TOGGLE FULL ANALYSIS
   ========================================================= */

async function toggleDashboardDetails(
    documentId,
    button
) {

    const container =
        document.getElementById(
            `dashboard-details-${documentId}`
        );


    if (!container) {

        console.error(
            "Dashboard details container missing:",
            documentId
        );

        return;
    }


    /* ---------------------------------------------
       CLOSE
       --------------------------------------------- */

    if (
        container.style.display !== "none" &&
        container.innerHTML.trim() !== ""
    ) {

        container.style.display =
            "none";


        button.disabled =
            false;


        button.innerHTML =
            "View Analysis Details ↓";


        return;
    }


    /* ---------------------------------------------
       OPEN
       --------------------------------------------- */

    container.style.display =
        "block";


    container.innerHTML = `

        <div class="dashboard-details-loading">

            Loading complete analysis...

        </div>

    `;


    button.disabled =
        true;


    button.innerHTML =
        "Loading Analysis...";


    try {

        console.log(
            "Fetching document:",
            documentId
        );


        const response =
            await fetch(
                `/api/documents/${documentId}`
            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        console.log(
            "DOCUMENT ANALYSIS:",
            data
        );


        renderDashboardDocumentDetails(
            container,
            data
        );


        button.disabled =
            false;


        button.innerHTML =
            "Hide Analysis Details ↑";


    } catch (error) {

        console.error(
            "Failed to load analysis:",
            error
        );


        container.innerHTML = `

            <div
                class="dashboard-details-error"
            >

                <strong>
                    Unable to load analysis
                </strong>

                <br>

                <small>
                    ${escapeHTML(
                        error.message
                    )}
                </small>

            </div>

        `;


        button.disabled =
            false;


        button.innerHTML =
            "Retry Analysis Details";
    }
}


/* =========================================================
   FULL DOCUMENT ANALYSIS
   ========================================================= */

function renderDashboardDocumentDetails(
    container,
    data
) {

    const document =
        data.document || {};


    const report =
        data.report || {};


    const clauses =
        Array.isArray(data.clauses)
            ? data.clauses
            : [];


    const score =
        Math.round(
            Number(
                report.risk_score || 0
            )
        );


    const overallRisk =
        report.overall_risk ||
        "Low";


    const high =
        Number(
            report.high_risk_count || 0
        );


    const medium =
        Number(
            report.medium_risk_count || 0
        );


    const low =
        Number(
            report.low_risk_count || 0
        );


    const riskClass =
        String(
            overallRisk
        ).toLowerCase();


    /* ---------------------------------------------
       RISK LABEL
       --------------------------------------------- */

    function riskLabel(label) {

        const labels = {

            high_interest:
                "High Interest",

            hidden_charges:
                "Hidden Charges",

            penalty_clause:
                "Penalty Clause",

            automatic_renewal:
                "Automatic Renewal",

            unilateral_change:
                "Unilateral Change",

            foreclosure:
                "Foreclosure Risk",

            coverage_exclusion:
                "Coverage Exclusion",

            waiting_period:
                "Waiting Period",

            no_risk:
                "No Risk"

        };


        return (
            labels[label] ||

            String(
                label ||
                "No Risk"
            ).replaceAll(
                "_",
                " "
            )
        );
    }


    /* ---------------------------------------------
       SEVERITY
       --------------------------------------------- */

    function severityClass(label) {

        if (
            [
                "high_interest",
                "hidden_charges",
                "penalty_clause",
                "unilateral_change",
                "foreclosure",
                "coverage_exclusion"
            ].includes(label)
        ) {

            return "high";
        }


        if (
            [
                "automatic_renewal",
                "waiting_period"
            ].includes(label)
        ) {

            return "medium";
        }


        return "low";
    }


    /* ---------------------------------------------
       CLAUSE DETAILS
       --------------------------------------------- */

    const clauseHTML =
        clauses.length

            ? clauses.map(
                (clause, index) => {

                    const predictions =
                        Array.isArray(
                            clause.predictions
                        )
                            ? clause.predictions
                            : [];


                    const prediction =
                        predictions[0] || {};


                    const label =
                        prediction.risk_label ||
                        "no_risk";


                    const confidence =
                        Number(
                            prediction.confidence ||
                            0
                        );


                    const severity =
                        severityClass(label);


                    return `

                        <div
                            class="
                                dashboard-clause-row
                            "
                        >

                            <div
                                class="
                                    dashboard-clause-number
                                "
                            >
                                ${index + 1}
                            </div>


                            <div
                                class="
                                    dashboard-clause-content
                                "
                            >

                                <div
                                    class="
                                        dashboard-clause-heading
                                    "
                                >

                                    <strong>
                                        ${escapeHTML(
                                            riskLabel(
                                                label
                                            )
                                        )}
                                    </strong>


                                    <span
                                        class="
                                            severity
                                            ${severity}
                                        "
                                    >
                                        ${severity.toUpperCase()}
                                    </span>

                                </div>


                                <p>

                                    ${escapeHTML(
                                        clause.clause_text ||
                                        clause.text ||
                                        ""
                                    )}

                                </p>


                                <small>

                                    ${
                                        prediction.model_name

                                            ? `Model: ${escapeHTML(
                                                prediction.model_name
                                            )}`

                                            : "Model: Rule-based Risk Analyzer"
                                    }


                                    ${
                                        confidence > 0

                                            ? ` · Confidence: ${Math.round(
                                                confidence * 100
                                            )}%`

                                            : ""
                                    }

                                </small>

                            </div>

                        </div>

                    `;

                }
            ).join("")

            : `

                <div
                    class="
                        dashboard-no-clauses
                    "
                >

                    No clauses were extracted
                    from this document.

                </div>

            `;


    /* ---------------------------------------------
       FINAL DASHBOARD DETAIL
       --------------------------------------------- */

    container.innerHTML = `

        <div
            class="
                dashboard-detail-header
            "
        >

            <div>

                <p class="eyebrow">
                    FULL ANALYSIS
                </p>


                <h3>

                    ${escapeHTML(
                        document.filename ||
                        "Agreement"
                    )}

                </h3>


                <p>

                    ${escapeHTML(
                        document.document_type ||
                        "Financial Agreement"
                    )}

                </p>

            </div>


            <div
                class="
                    dashboard-detail-score
                    ${escapeHTML(
                        riskClass
                    )}
                "
            >

                <strong>
                    ${score}
                </strong>

                <span>
                    /100
                </span>

                <em>

                    ${escapeHTML(
                        overallRisk
                    )}

                </em>

            </div>

        </div>


        <!-- RISK COUNTS -->

        <div
            class="
                dashboard-detail-counts
            "
        >

            <div>

                <span>
                    HIGH RISK
                </span>

                <strong>
                    ${high}
                </strong>

            </div>


            <div>

                <span>
                    MEDIUM RISK
                </span>

                <strong>
                    ${medium}
                </strong>

            </div>


            <div>

                <span>
                    LOW RISK
                </span>

                <strong>
                    ${low}
                </strong>

            </div>


            <div>

                <span>
                    CLAUSES ANALYSED
                </span>

                <strong>
                    ${clauses.length}
                </strong>

            </div>

        </div>


        <!-- CLAUSE ANALYSIS -->

        <div
            class="
                dashboard-clause-section
            "
        >

            <div
                class="
                    dashboard-clause-section-head
                "
            >

                <div>

                    <p class="eyebrow">
                        CLAUSE-LEVEL ANALYSIS
                    </p>


                    <h4>
                        Detected Findings
                    </h4>

                </div>


                <span>
                    ${clauses.length} clauses
                </span>

            </div>


            <div
                class="
                    dashboard-clause-list
                "
            >

                ${clauseHTML}

            </div>

        </div>

    `;
}


/* =========================================================
   HTML ESCAPE
   ========================================================= */

function escapeHTML(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return "";
    }


    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}