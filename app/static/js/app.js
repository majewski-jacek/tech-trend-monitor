/**
 * TechTrend Monitor - Interactive Client Application
 * Handles Real-time WebSockets, Chart.js Visualizations, Auth & Live Data Ingestion
 */

// Application State
const state = {
    token: localStorage.getItem("token") || null,
    currentUser: null,
    page: 1,
    pageSize: 12,
    totalPages: 1,
    search: "",
    tag: "",
    sentiment: "",
    sortBy: "created_at",
    isSyncing: false,
    ws: null,
    wsConnected: false,
    wsReconnectTimeout: null,
    charts: {
        techTags: null,
        sentimentDist: null,
        sentimentTimeline: null
    }
};

/* =========================================================================
   DATE & TIMEZONE UTILITIES (UTC -> Local Browser Timezone)
   ========================================================================= */

function parseUtcDate(dateString) {
    if (!dateString) return null;
    let s = String(dateString).trim();
    // Ensure string ending with 'Z' is treated as UTC
    if (!s.endsWith("Z") && !s.includes("+") && s.includes("T")) {
        s += "Z";
    }
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
}

function formatLocalTime(dateString) {
    const d = parseUtcDate(dateString);
    if (!d) return "Brak";
    return d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

function formatLocalDateTime(dateString) {
    const d = parseUtcDate(dateString);
    if (!d) return `<span class="text-xs text-slate-500">Niedawno</span>`;

    // Format date without commas, e.g. "22 paź"
    const datePart = d.toLocaleDateString("pl-PL", {
        day: "numeric",
        month: "short"
    }).replace(".", "");

    // Format time, e.g. "13:30"
    const timePart = d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });

    return `
        <div class="flex flex-col items-end leading-tight">
            <span class="text-xs font-medium text-slate-200">${datePart}</span>
            <span class="text-[11px] text-slate-500 font-mono tracking-tight mt-0.5">${timePart}</span>
        </div>
    `;
}

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    initWebSocket();
    checkAuthStatus();
    loadDashboardData();

    // Setup search debounce
    const searchInput = document.getElementById("input-search");
    let debounceTimer;
    searchInput.addEventListener("input", (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.search = e.target.value.trim();
            state.page = 1;
            fetchArticles();
        }, 350);
    });
});

/* =========================================================================
   1. WEBSOCKET REAL-TIME CLIENT
   ========================================================================= */

function initWebSocket() {
    if (state.ws) {
        state.ws.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    updateWsStatus(false);

    try {
        state.ws = new WebSocket(wsUrl);

        state.ws.onopen = () => {
            console.log("[WebSocket] Connected to live telemetry feed.");
            updateWsStatus(true);
            showToast("Połączono z serwerem WebSocket (Live Telemetry)", "success");
        };

        state.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleWebSocketMessage(msg);
            } catch (err) {
                console.error("[WebSocket] Error parsing message:", err);
            }
        };

        state.ws.onclose = () => {
            console.warn("[WebSocket] Disconnected. Reconnecting in 3s...");
            updateWsStatus(false);
            clearTimeout(state.wsReconnectTimeout);
            state.wsReconnectTimeout = setTimeout(initWebSocket, 3000);
        };

        state.ws.onerror = (err) => {
            console.error("[WebSocket] Connection error:", err);
            state.ws.close();
        };
    } catch (e) {
        console.error("[WebSocket] Initialization exception:", e);
        setTimeout(initWebSocket, 4000);
    }
}

function updateWsStatus(connected) {
    state.wsConnected = connected;
    const badge = document.getElementById("ws-status-badge");
    const dot = document.getElementById("ws-status-dot");
    const text = document.getElementById("ws-status-text");

    if (connected) {
        badge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full border text-xs font-medium transition-all bg-emerald-950/40 border-emerald-800/60 text-emerald-400";
        dot.className = "w-2 h-2 rounded-full bg-emerald-400 pulse-dot";
        text.textContent = "LIVE (WebSocket)";
    } else {
        badge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full border text-xs font-medium transition-all bg-rose-950/40 border-rose-800/60 text-rose-400";
        dot.className = "w-2 h-2 rounded-full bg-rose-400";
        text.textContent = "Rozłączono (Wznawianie...)";
    }
}

function handleWebSocketMessage(msg) {
    const type = msg.type;
    if (type === "CONNECTED") {
        console.log("[WebSocket]", msg.message);
    } else if (type === "SYNC_STATUS") {
        if (msg.status === "started") {
            setSyncLoading(true);
        } else if (msg.status === "failed") {
            setSyncLoading(false);
            if (!state.isSyncing) {
                showToast(msg.error || "Brak połączenia z zewnętrznym API Hacker News. Sprawdź połączenie z internetem.", "error");
            }
        } else if (msg.status === "completed") {
            setSyncLoading(false);
            if (msg.last_sync_time) {
                const lastSyncEl = document.getElementById("stat-last-sync");
                if (lastSyncEl) {
                    lastSyncEl.textContent = formatLocalTime(msg.last_sync_time);
                }
            }
            // If the user triggered manual sync, handleManualSync shows the single toast.
            // If sync ran automatically in background worker, notify only when new posts arrived.
            if (!state.isSyncing && msg.new_count && msg.new_count > 0) {
                showToast(`Aktualizacja w tle: Pobrano ${msg.new_count} nowych artykułów!`, "info");
            }
            refreshData();
        }
    } else if (type === "NEW_ARTICLES") {
        if (msg.new_count && msg.new_count > 0) {
            const alertEl = document.getElementById("live-new-alert");
            const alertText = document.getElementById("live-new-text");
            if (alertEl && alertText) {
                alertText.textContent = `Wykryto i przetworzono na żywo nowe wpisy (+${msg.new_count})!`;
                alertEl.classList.remove("hidden");
            }
            if (msg.last_sync_time) {
                const lastSyncEl = document.getElementById("stat-last-sync");
                if (lastSyncEl) {
                    lastSyncEl.textContent = formatLocalTime(msg.last_sync_time);
                }
            }
            // Display toast only if not in manual sync flow (manual sync displays its own summary)
            if (!state.isSyncing) {
                showToast(`Na żywo: Pobrano ${msg.new_count} nowych artykułów!`, "success");
            }
            loadDashboardData();
        }
    }
}

/* =========================================================================
   2. DATA FETCHING & DASHBOARD METRICS
   ========================================================================= */

async function loadDashboardData() {
    await Promise.all([fetchTrendsSummary(), fetchArticles()]);
}

async function refreshData() {
    const alertEl = document.getElementById("live-new-alert");
    if (alertEl) alertEl.classList.add("hidden");
    await loadDashboardData();
}

async function fetchTrendsSummary() {
    try {
        const res = await fetch("/api/v1/trends/summary");
        if (!res.ok) throw new Error("Failed to load trends summary");
        const data = await res.json();
        renderSummaryKPIs(data);
        renderCharts(data);
    } catch (err) {
        console.error("fetchTrendsSummary error:", err);
    }
}

function renderSummaryKPIs(data) {
    // 1. Total articles
    document.getElementById("stat-total-articles").textContent = data.total_articles.toLocaleString();

    // 2. Global sentiment score & label
    const sent = data.sentiment || { overall_score: 0.0, overall_label: "Neutral", positive: 0, neutral: 0, negative: 0 };
    const scoreEl = document.getElementById("stat-sentiment-score");
    const badgeEl = document.getElementById("stat-sentiment-badge");
    const barEl = document.getElementById("stat-sentiment-bar");
    const iconContainer = document.getElementById("stat-sentiment-icon-container");

    const sign = sent.overall_score > 0 ? "+" : "";
    scoreEl.textContent = `${sign}${sent.overall_score.toFixed(2)}`;
    badgeEl.textContent = sent.overall_label;

    // Normalizing -1..1 to 0..100%
    const normalizedPercent = Math.max(0, Math.min(100, ((sent.overall_score + 1) / 2) * 100));
    barEl.style.width = `${normalizedPercent}%`;

    if (sent.overall_score >= 0.05) {
        badgeEl.className = "text-xs px-2 py-0.5 rounded-full font-semibold bg-emerald-500/20 text-emerald-300";
        barEl.className = "h-full bg-emerald-400 transition-all duration-500";
        iconContainer.className = "p-2 rounded-xl bg-emerald-500/10 text-emerald-400";
    } else if (sent.overall_score <= -0.05) {
        badgeEl.className = "text-xs px-2 py-0.5 rounded-full font-semibold bg-rose-500/20 text-rose-300";
        barEl.className = "h-full bg-rose-400 transition-all duration-500";
        iconContainer.className = "p-2 rounded-xl bg-rose-500/10 text-rose-400";
    } else {
        badgeEl.className = "text-xs px-2 py-0.5 rounded-full font-semibold bg-amber-500/20 text-amber-300";
        barEl.className = "h-full bg-amber-400 transition-all duration-500";
        iconContainer.className = "p-2 rounded-xl bg-amber-500/10 text-amber-400";
    }

    // 3. Top Tag
    const topTagEl = document.getElementById("stat-top-tag");
    const topTagCountEl = document.getElementById("stat-top-tag-count");
    if (data.top_tags && data.top_tags.length > 0) {
        const top = data.top_tags[0];
        topTagEl.textContent = top.tag;
        topTagCountEl.textContent = `${top.count} artykułów (${top.sentiment_label})`;
    } else {
        topTagEl.textContent = "Brak danych";
        topTagCountEl.textContent = "Uruchom synchronizację";
    }

    // 4. Last sync timestamp from metadata, formatted to client's local timezone
    const lastSyncEl = document.getElementById("stat-last-sync");
    if (data.last_sync_time) {
        lastSyncEl.textContent = formatLocalTime(data.last_sync_time);
    } else {
        lastSyncEl.textContent = "Brak";
    }

    // Legend counts
    document.getElementById("leg-pos-count").textContent = sent.positive;
    document.getElementById("leg-neu-count").textContent = sent.neutral;
    document.getElementById("leg-neg-count").textContent = sent.negative;
}

/* =========================================================================
   3. CHART.JS VISUALIZATIONS
   ========================================================================= */

function renderCharts(data) {
    renderTechTagsChart(data.top_tags || []);
    renderSentimentDistChart(data.sentiment || { positive: 0, neutral: 0, negative: 0 });
    renderTimelineChart(data.timeline || []);
}

function renderTechTagsChart(tags) {
    const ctx = document.getElementById("chart-tech-tags").getContext("2d");
    if (state.charts.techTags) {
        state.charts.techTags.destroy();
    }

    const labels = tags.map(t => t.tag);
    const counts = tags.map(t => t.count);

    state.charts.techTags = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels.length ? labels : ["Brak danych"],
            datasets: [{
                label: "Wzmianki w feedzie",
                data: counts.length ? counts : [0],
                backgroundColor: "rgba(99, 102, 241, 0.75)",
                borderColor: "rgba(99, 102, 241, 1)",
                borderWidth: 1.5,
                borderRadius: 8,
                hoverBackgroundColor: "rgba(129, 140, 248, 0.9)"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#1e293b",
                    titleColor: "#f8fafc",
                    bodyColor: "#cbd5e1",
                    borderColor: "#334155",
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: "#94a3b8", font: { size: 11, family: "Inter" } }
                },
                y: {
                    grid: { color: "rgba(51, 65, 85, 0.3)" },
                    ticks: { color: "#94a3b8", precision: 0, font: { size: 11, family: "Inter" } },
                    beginAtZero: true
                }
            }
        }
    });
}

function renderSentimentDistChart(sentiment) {
    const ctx = document.getElementById("chart-sentiment-distribution").getContext("2d");
    if (state.charts.sentimentDist) {
        state.charts.sentimentDist.destroy();
    }

    state.charts.sentimentDist = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Pozytywne", "Neutralne", "Negatywne"],
            datasets: [{
                data: [sentiment.positive, sentiment.neutral, sentiment.negative],
                backgroundColor: [
                    "rgba(16, 185, 129, 0.85)", // Emerald
                    "rgba(148, 163, 184, 0.65)", // Slate
                    "rgba(244, 63, 94, 0.85)"    // Rose
                ],
                borderColor: "#0f172a",
                borderWidth: 3,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "70%",
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#1e293b",
                    titleColor: "#f8fafc",
                    bodyColor: "#cbd5e1",
                    borderColor: "#334155",
                    borderWidth: 1
                }
            }
        }
    });
}

function renderTimelineChart(timeline) {
    const ctx = document.getElementById("chart-sentiment-timeline").getContext("2d");
    if (state.charts.sentimentTimeline) {
        state.charts.sentimentTimeline.destroy();
        const oldTooltip = ctx.canvas.parentNode.querySelector(".chartjs-custom-tooltip");
        if (oldTooltip) oldTooltip.remove();
    }

    if (!timeline || timeline.length === 0) {
        timeline = [{
            timestamp: new Date().toISOString(),
            avg_sentiment: 0.0,
            active_sentiment: 0.0,
            article_count: 0
        }];
    }

    // Format timestamps dynamically to local time for labels
    const labels = timeline.map(p => {
        const d = parseUtcDate(p.timestamp);
        return d ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : p.timestamp;
    });

    // Extract active sentiment (excluding 0.00 neutral noise) and overall average
    const activeScores = timeline.map(p => p.active_sentiment !== undefined ? p.active_sentiment : p.avg_sentiment);
    const avgScores = timeline.map(p => p.avg_sentiment);

    // Dynamic auto-zoom scaling with generous safety padding/buffer
    const allVals = activeScores.concat(avgScores);
    let yMin = -0.3;
    let yMax = 0.3;
    if (allVals.length > 0) {
        const minVal = Math.min(...allVals);
        const maxVal = Math.max(...allVals);
        const span = Math.max(0.1, maxVal - minVal);
        const buffer = Math.max(0.12, span * 0.35);
        yMin = Math.max(-1.0, Number((minVal - buffer).toFixed(2)));
        yMax = Math.min(1.0, Number((maxVal + buffer + 0.05).toFixed(2)));
        if (yMin >= yMax) {
            yMin = Math.max(-1.0, yMin - 0.25);
            yMax = Math.min(1.0, yMax + 0.25);
        }
    }

    // Custom plugin to add breathing room (margin) between the legend and top data points
    const legendMarginPlugin = {
        id: "legendMargin",
        beforeInit(chart) {
            const fitValue = chart.legend.fit;
            chart.legend.fit = function fit() {
                fitValue.bind(chart.legend)();
                return (this.height += 20);
            };
        }
    };

    // Elegant custom HTML tooltip handler without raw emoji
    const customTimelineTooltip = (context) => {
        const { chart, tooltip } = context;
        let tooltipEl = chart.canvas.parentNode.querySelector(".chartjs-custom-tooltip");

        if (!tooltipEl) {
            tooltipEl = document.createElement("div");
            tooltipEl.className = "chartjs-custom-tooltip pointer-events-none absolute z-40 bg-slate-900/95 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs shadow-2xl backdrop-blur-md transition-opacity duration-150";
            chart.canvas.parentNode.appendChild(tooltipEl);
        }

        if (tooltip.opacity === 0) {
            tooltipEl.style.opacity = "0";
            return;
        }

        if (tooltip.body) {
            const index = tooltip.dataPoints && tooltip.dataPoints.length > 0 ? tooltip.dataPoints[0].dataIndex : -1;
            const point = (index >= 0 && timeline && timeline[index]) ? timeline[index] : null;

            // Header: "22 paź • 13:30" (clean separator, no comma, no seconds)
            let headerText = tooltip.title && tooltip.title[0] ? tooltip.title[0] : "";
            if (point) {
                const d = parseUtcDate(point.timestamp);
                if (d) {
                    const datePart = d.toLocaleDateString("pl-PL", { day: "numeric", month: "short" }).replace(".", "");
                    const timePart = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                    headerText = `${datePart} • ${timePart}`;
                }
            }

            let innerHtml = `
                <div class="font-semibold text-slate-100 border-b border-slate-800 pb-1.5 mb-2">
                    ${headerText}
                </div>
                <div class="space-y-1.5">
            `;

            tooltip.dataPoints.forEach(dp => {
                const color = dp.dataset.borderColor || "#38bdf8";
                const val = dp.parsed.y;
                const sign = val > 0 ? "+" : "";
                innerHtml += `
                    <div class="flex items-center space-x-2 text-slate-300">
                        <span class="inline-block w-2 h-2 rounded-full mr-2 flex-shrink-0" style="background-color: ${color};"></span>
                        <span class="text-slate-400 font-normal">${dp.dataset.label}:</span>
                        <span class="font-mono font-medium text-slate-100 ml-auto">${sign}${val.toFixed(3)}</span>
                    </div>
                `;
            });

            innerHtml += `</div>`;

            // Footer: clean muted volume text without emoji
            const count = point ? point.article_count : (tooltip.dataPoints[0] ? 1 : 0);
            innerHtml += `
                <div class="mt-2.5 pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                    <span>Wolumen wpisów:</span>
                    <span class="font-semibold text-slate-200 font-mono">${count}</span>
                </div>
            `;

            tooltipEl.innerHTML = innerHtml;
        }

        const { offsetLeft: positionX, offsetTop: positionY } = chart.canvas;
        tooltipEl.style.opacity = "1";

        const tooltipWidth = tooltipEl.offsetWidth || 220;
        const tooltipHeight = tooltipEl.offsetHeight || 100;
        const canvasWidth = chart.canvas.clientWidth;

        // Prevent horizontal clipping
        let left = positionX + tooltip.caretX + 12;
        if (left + tooltipWidth > canvasWidth) {
            left = positionX + tooltip.caretX - tooltipWidth - 12;
        }

        // Prevent vertical overlap with top legend
        let top = positionY + tooltip.caretY - (tooltipHeight / 2);
        if (top < positionY + 32) {
            top = positionY + tooltip.caretY + 16;
        }

        tooltipEl.style.left = Math.max(0, left) + "px";
        tooltipEl.style.top = Math.max(0, top) + "px";
    };

    state.charts.sentimentTimeline = new Chart(ctx, {
        type: "line",
        plugins: [legendMarginPlugin],
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Aktywny Sentyment (bez neutralnych)",
                    data: activeScores,
                    borderColor: "#38bdf8",
                    backgroundColor: "rgba(56, 189, 248, 0.15)",
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    pointBackgroundColor: "#0284c7",
                    pointBorderColor: "#fff",
                    pointRadius: 4,
                    pointHoverRadius: 7
                },
                {
                    label: "Średni Sentyment Całkowity",
                    data: avgScores,
                    borderColor: "#94a3b8",
                    borderDash: [4, 4],
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.35,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: "top",
                    align: "end",
                    labels: {
                        color: "#94a3b8",
                        font: { size: 11, family: "Inter", weight: 500 },
                        boxWidth: 8,
                        boxHeight: 8,
                        padding: 16,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    enabled: false,
                    external: customTimelineTooltip,
                    callbacks: {
                        title: function(items) {
                            if (!items.length) return "";
                            const index = items[0].dataIndex;
                            const point = timeline[index];
                            if (point) {
                                const d = parseUtcDate(point.timestamp);
                                if (d) {
                                    const datePart = d.toLocaleDateString("pl-PL", { day: "numeric", month: "short" }).replace(".", "");
                                    const timePart = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                                    return `${datePart} • ${timePart}`;
                                }
                            }
                            return items[0].label;
                        },
                        label: function(context) {
                            const val = context.parsed.y;
                            const sign = val > 0 ? "+" : "";
                            return ` ${context.dataset.label}: ${sign}${val.toFixed(3)}`;
                        },
                        afterBody: function(items) {
                            if (!items.length) return "";
                            const index = items[0].dataIndex;
                            const point = timeline[index];
                            const count = point ? point.article_count : 1;
                            return `Wolumen wpisów: ${count}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: "#94a3b8", maxRotation: 45, font: { size: 10, family: "Inter" } }
                },
                y: {
                    min: yMin,
                    max: yMax,
                    grid: { color: "rgba(51, 65, 85, 0.3)" },
                    ticks: {
                        color: "#94a3b8",
                        font: { size: 11, family: "Inter" },
                        callback: function(val) {
                            return (val > 0 ? "+" : "") + Number(val).toFixed(2);
                        }
                    }
                }
            }
        }
    });
}

/* =========================================================================
   4. ARTICLES TABLE, SEARCH & PAGINATION
   ========================================================================= */

async function fetchArticles() {
    const params = new URLSearchParams({
        page: state.page,
        size: state.pageSize,
        sort_by: state.sortBy,
        order: "desc"
    });

    if (state.search) params.append("search", state.search);
    if (state.tag) params.append("tag", state.tag);
    if (state.sentiment) params.append("sentiment", state.sentiment);

    try {
        const res = await fetch(`/api/v1/articles?${params.toString()}`);
        if (!res.ok) throw new Error("Failed to fetch articles");
        const data = await res.json();

        state.totalPages = data.total_pages;
        renderArticlesTable(data.items);
        renderPagination(data);
    } catch (err) {
        console.error("fetchArticles error:", err);
    }
}

function renderArticlesTable(articles) {
    const tbody = document.getElementById("articles-table-body");
    tbody.innerHTML = "";

    if (!articles || articles.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-12 text-slate-500">
                    <div class="flex flex-col items-center justify-center space-y-2">
                        <i data-lucide="inbox" class="w-8 h-8 text-slate-600"></i>
                        <span>Brak pasujących artykułów dla podanych filtrów.</span>
                    </div>
                </td>
            </tr>
        `;
        lucide.createIcons();
        return;
    }

    articles.forEach(art => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-800/40 transition-colors";

        // Sentiment badge
        let badgeColor = "bg-amber-500/10 text-amber-400 border-amber-500/20";
        if (art.sentiment_label === "Positive") {
            badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
        } else if (art.sentiment_label === "Negative") {
            badgeColor = "bg-rose-500/10 text-rose-400 border-rose-500/20";
        }

        // Tags badges
        const tagsHtml = (art.tags || []).map(t => `
            <span class="inline-block px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 text-[11px] font-medium border border-slate-700/60 mr-1 mb-1">
                ${t}
            </span>
        `).join("") || '<span class="text-slate-600 text-xs">Ogólne</span>';

        // Published date - formatted into user's local timezone
        const dateStr = formatLocalDateTime(art.created_at);

        const urlHtml = art.url ? `
            <a href="${art.url}" target="_blank" rel="noopener noreferrer" class="text-white hover:text-indigo-400 font-medium inline-flex items-center space-x-1 transition-colors">
                <span>${escapeHtml(art.title)}</span>
                <i data-lucide="external-link" class="w-3.5 h-3.5 text-slate-500 flex-shrink-0"></i>
            </a>
        ` : `<span class="text-white font-medium">${escapeHtml(art.title)}</span>`;

        tr.innerHTML = `
            <td class="px-4 py-3.5 max-w-md">
                ${urlHtml}
                <div class="text-xs text-slate-500 mt-1 flex items-center space-x-2">
                    <span>Autor: <strong class="text-slate-400">${escapeHtml(art.author || 'anon')}</strong></span>
                    <span>&bull;</span>
                    <span class="text-slate-500">${art.source}</span>
                </div>
            </td>
            <td class="px-4 py-3.5 whitespace-nowrap">
                <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${badgeColor}">
                    ${art.sentiment_label} (${art.sentiment_score > 0 ? "+" : ""}${art.sentiment_score.toFixed(2)})
                </span>
            </td>
            <td class="px-4 py-3.5">
                <div class="flex flex-wrap max-w-xs">${tagsHtml}</div>
            </td>
            <td class="px-4 py-3.5 whitespace-nowrap text-center">
                <div class="inline-flex items-center space-x-3 text-xs text-slate-400">
                    <span class="flex items-center text-amber-400" title="Wynik">
                        <i data-lucide="flame" class="w-3.5 h-3.5 mr-1"></i> ${art.score}
                    </span>
                    <span class="flex items-center text-slate-400" title="Komentarze">
                        <i data-lucide="message-square" class="w-3.5 h-3.5 mr-1"></i> ${art.comments_count}
                    </span>
                </div>
            </td>
            <td class="px-4 py-3.5 whitespace-nowrap text-right">
                ${dateStr}
            </td>
        `;

        tbody.appendChild(tr);
    });

    lucide.createIcons();
}

function renderPagination(data) {
    const info = document.getElementById("pagination-info");
    const pageDisplay = document.getElementById("current-page-display");
    const prevBtn = document.getElementById("btn-prev-page");
    const nextBtn = document.getElementById("btn-next-page");

    const start = data.total === 0 ? 0 : (data.page - 1) * data.size + 1;
    const end = Math.min(data.page * data.size, data.total);

    info.textContent = `Pokazywanie ${start}-${end} z ${data.total} wpisów`;
    pageDisplay.textContent = `Strona ${data.page} z ${data.total_pages || 1}`;

    prevBtn.disabled = data.page <= 1;
    nextBtn.disabled = data.page >= data.total_pages;
}

function changePage(delta) {
    const newPage = state.page + delta;
    if (newPage >= 1 && newPage <= state.totalPages) {
        state.page = newPage;
        fetchArticles();
    }
}

function handleFilterChange() {
    state.tag = document.getElementById("select-tag").value;
    state.sentiment = document.getElementById("select-sentiment").value;
    state.sortBy = document.getElementById("select-sort").value;
    state.page = 1;
    fetchArticles();
}

/* =========================================================================
   5. MANUAL SYNC TRIGGER
   ========================================================================= */

async function handleManualSync() {
    if (state.isSyncing) return;

    const headers = { "Content-Type": "application/json" };
    if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
    }

    setSyncLoading(true);

    try {
        const res = await fetch("/api/v1/sync", {
            method: "POST",
            headers: headers
        });

        if (res.status === 401) {
            setSyncLoading(false);
            showToast("Wymagana autoryzacja do uruchomienia synchronizacji. Zaloguj się!", "error");
            openAuthModal();
            return;
        }

        if (!res.ok) {
            let errorMsg = `Błąd synchronizacji (${res.status})`;
            try {
                const errData = await res.json();
                if (errData && errData.detail) {
                    errorMsg = errData.detail;
                } else if (errData && errData.message) {
                    errorMsg = errData.message;
                }
            } catch (_) {}
            throw new Error(errorMsg);
        }

        const data = await res.json();
        // Immediately update the last sync KPI tile with the exact action timestamp
        if (data.timestamp) {
            const lastSyncEl = document.getElementById("stat-last-sync");
            if (lastSyncEl) {
                lastSyncEl.textContent = formatLocalTime(data.timestamp);
            }
        }

        // Show single clear Polish notification
        if (data.new_articles_count > 0) {
            showToast(data.message || `Pobrano i przeanalizowano ${data.new_articles_count} nowych artykułów!`, "success");
        } else {
            showToast("Baza jest aktualna. Brak nowych wpisów w API.", "info");
        }

        await loadDashboardData();
    } catch (err) {
        console.error("Manual sync error:", err);
        showToast("Błąd synchronizacji feedu: " + err.message, "error");
    } finally {
        setSyncLoading(false);
    }
}

function setSyncLoading(loading) {
    state.isSyncing = loading;
    const btn = document.getElementById("btn-sync");
    const icon = document.getElementById("sync-icon");

    if (loading) {
        btn.classList.add("opacity-75", "pointer-events-none");
        if (icon) icon.classList.add("animate-spin");
    } else {
        btn.classList.remove("opacity-75", "pointer-events-none");
        if (icon) icon.classList.remove("animate-spin");
    }
}

/* =========================================================================
   6. AUTHENTICATION & SESSION MANAGEMENT
   ========================================================================= */

function openAuthModal() {
    document.getElementById("auth-modal").classList.remove("hidden");
    document.getElementById("auth-error-banner").classList.add("hidden");
}

function closeAuthModal() {
    document.getElementById("auth-modal").classList.add("hidden");
}

function switchAuthTab(tab) {
    const tabLogin = document.getElementById("tab-login");
    const tabRegister = document.getElementById("tab-register");
    const formLogin = document.getElementById("form-login");
    const formRegister = document.getElementById("form-register");
    const errorBanner = document.getElementById("auth-error-banner");

    errorBanner.classList.add("hidden");

    if (tab === "login") {
        tabLogin.className = "text-indigo-400 border-b-2 border-indigo-500 pb-2 transition-all";
        tabRegister.className = "text-slate-400 hover:text-slate-200 pb-2 transition-all";
        formLogin.classList.remove("hidden");
        formRegister.classList.add("hidden");
    } else {
        tabRegister.className = "text-indigo-400 border-b-2 border-indigo-500 pb-2 transition-all";
        tabLogin.className = "text-slate-400 hover:text-slate-200 pb-2 transition-all";
        formRegister.classList.remove("hidden");
        formLogin.classList.add("hidden");
    }
}

function fillDemoAdminCredentials() {
    document.getElementById("login-identifier").value = "admin";
    document.getElementById("login-password").value = "admin123";
}

async function handleLoginSubmit(event) {
    event.preventDefault();
    const identifier = document.getElementById("login-identifier").value;
    const password = document.getElementById("login-password").value;
    const errorBanner = document.getElementById("auth-error-banner");

    try {
        const res = await fetch("/api/v1/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username_or_email: identifier, password: password })
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Błędne dane logowania");
        }

        state.token = data.access_token;
        localStorage.setItem("token", state.token);
        state.currentUser = data.user;

        updateAuthUI();
        closeAuthModal();
        showToast(`Zalogowano pomyślnie jako ${data.user.username}!`, "success");
    } catch (err) {
        errorBanner.textContent = err.message;
        errorBanner.classList.remove("hidden");
    }
}

async function handleRegisterSubmit(event) {
    event.preventDefault();
    const username = document.getElementById("register-username").value;
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;
    const errorBanner = document.getElementById("auth-error-banner");

    try {
        const res = await fetch("/api/v1/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, email, password })
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Błąd podczas rejestracji");
        }

        showToast("Konto utworzone! Możesz się teraz zalogować.", "success");
        switchAuthTab("login");
        document.getElementById("login-identifier").value = username;
        document.getElementById("login-password").value = password;
    } catch (err) {
        errorBanner.textContent = err.message;
        errorBanner.classList.remove("hidden");
    }
}

async function checkAuthStatus() {
    if (!state.token) {
        updateAuthUI();
        return;
    }

    try {
        const res = await fetch("/api/v1/auth/me", {
            headers: { "Authorization": `Bearer ${state.token}` }
        });

        if (res.ok) {
            state.currentUser = await res.json();
        } else {
            state.token = null;
            state.currentUser = null;
            localStorage.removeItem("token");
        }
    } catch (e) {
        console.warn("Could not check auth status:", e);
    }
    updateAuthUI();
}

async function handleLogout() {
    const token = state.token;
    if (token) {
        try {
            await fetch("/api/v1/auth/logout", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                }
            });
        } catch (err) {
            console.error("Error communicating logout to server:", err);
        }
    }

    state.token = null;
    state.currentUser = null;
    localStorage.removeItem("token");
    updateAuthUI();
    showToast("Wylogowano pomyślnie. Sesja została unieważniona.", "info");
    openAuthModal();
}

function updateAuthUI() {
    const btnOpenAuth = document.getElementById("btn-open-auth");
    const userBadge = document.getElementById("user-profile-badge");
    const userName = document.getElementById("user-name");
    const userAvatar = document.getElementById("user-avatar");

    if (state.currentUser) {
        btnOpenAuth.classList.add("hidden");
        userBadge.classList.remove("hidden");
        userName.textContent = state.currentUser.username;
        userAvatar.textContent = state.currentUser.username.charAt(0).toUpperCase();
    } else {
        btnOpenAuth.classList.remove("hidden");
        userBadge.classList.add("hidden");
    }
}

/* =========================================================================
   7. TOAST NOTIFICATIONS HELPER (With Deduplication)
   ========================================================================= */

const activeToastTimestamps = new Map();

function getToastDedupeKey(message) {
    const text = String(message).trim();
    if (text.includes("Brak połączenia z zewnętrznym API")) {
        return "ERR_API_CONNECTION_LOST";
    }
    return text;
}

function showToast(message, type = "info") {
    if (!message) return;
    const cleanMsg = String(message).trim();
    const dedupeKey = getToastDedupeKey(cleanMsg);
    const now = Date.now();

    // 1. Time-based debounce: suppress identical key within 2000ms
    const lastShown = activeToastTimestamps.get(dedupeKey) || 0;
    if (now - lastShown < 2000) {
        return;
    }

    const container = document.getElementById("toast-container");
    if (!container) return;

    // 2. DOM-level deduplication: do not append if identical text or category is already displayed
    const alreadyVisible = Array.from(container.children).some(el => {
        const text = el.textContent || "";
        if (dedupeKey === "ERR_API_CONNECTION_LOST" && text.includes("Brak połączenia z zewnętrznym API")) {
            return true;
        }
        return text.trim().includes(cleanMsg);
    });
    if (alreadyVisible) {
        return;
    }

    activeToastTimestamps.set(dedupeKey, now);

    const toast = document.createElement("div");

    let colors = "bg-slate-900 border-slate-700 text-slate-200";
    let iconName = "info";

    if (type === "success") {
        colors = "bg-emerald-950/90 border-emerald-700/80 text-emerald-200";
        iconName = "check-circle";
    } else if (type === "error") {
        colors = "bg-rose-950/90 border-rose-700/80 text-rose-200";
        iconName = "alert-circle";
    }

    toast.className = `flex items-center space-x-2.5 px-4 py-3 rounded-xl border shadow-xl text-xs font-medium pointer-events-auto transition-all transform duration-300 translate-y-2 opacity-0 ${colors}`;
    toast.innerHTML = `
        <i data-lucide="${iconName}" class="w-4 h-4 flex-shrink-0"></i>
        <span>${escapeHtml(cleanMsg)}</span>
    `;

    container.appendChild(toast);
    lucide.createIcons();

    setTimeout(() => {
        toast.classList.remove("translate-y-2", "opacity-0");
    }, 10);

    setTimeout(() => {
        toast.classList.add("opacity-0", "translate-y-2");
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
