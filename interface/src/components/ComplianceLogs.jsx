// src/components/ComplianceLogs.jsx
import React, { useEffect, useMemo, useState } from "react";
import { FaShieldAlt } from "react-icons/fa";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "./ComplianceLogs.css";

import { Chart, registerables } from "chart.js";
Chart.register(...registerables);

// Chart.js global defaults (fixed-size rendering, no responsive reflow)
Chart.defaults.responsive = false;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.devicePixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);

const API_BASE =
  (process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

// ---------- helpers ----------
function toLocal(ts) {
  try {
    if (!ts) return "";
    const d = new Date(ts);
    return Number.isNaN(d.getTime()) ? String(ts) : d.toLocaleString();
  } catch {
    return String(ts || "");
  }
}

function safeTime(ev) {
  // Try common fields: time (ISO), timestamp, fallback to now
  const raw = ev?.time || ev?.timestamp || ev?.date || null;
  const d = raw ? new Date(raw) : new Date();
  return Number.isNaN(d.getTime()) ? new Date() : d;
}

function minuteStampLocal(ts) {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : Math.floor(d.getTime() / 60000);
}

function formatMinuteStamp(minStamp) {
  const d = new Date(minStamp * 60000);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const HH = String(d.getHours()).padStart(2, "0");
  const MM = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${HH}:${MM}`;
}

// Severity logic
function getLevel(ev) {
  const explicit = (ev?.level || "").toString().toUpperCase();
  if (["INFO", "WARNING", "ERROR", "CRITICAL"].includes(explicit)) return explicit;

  const sev = Number(ev?.severity || 0);
  let score = Number(ev?.score || 0);
  if (!score) score = Number(ev?.signals?.score || 0);
  const subtype = (ev?.subtype || "").toLowerCase();
  const etype = (ev?.type || "").toLowerCase();

  if (sev <= 1 && score < 20) return "INFO";
  if (etype === "resource" || subtype.includes("cpu") || subtype.includes("disk"))
    return "ERROR";
  if (
    score >= 70 ||
    sev >= 3 ||
    subtype.includes("service_install") ||
    subtype.includes("vss_delete")
  )
    return "WARNING";
  return sev >= 2 ? "ERROR" : "INFO";
}

// For table “Message” column
function makeMessage(ev) {
  return [
    ev?.name || "Windows-Ransomware-Defense",
    ": ",
    ev?.type || "event",
    "/",
    ev?.subtype || "log",
    ` (sev=${ev?.severity ?? 0}, score=${ev?.score ?? ev?.signals?.score ?? 0})`,
  ].join("");
}

const LEVEL_COLORS = {
  INFO: "#3b82f6",     // blue
  WARNING: "#ef4444",  // red
  ERROR: "#f97316",    // orange
  CRITICAL: "#fbbf24", // yellow
};

const PAGE_SIZE = 200;
const CHART_SAMPLE = 1000;

export default function ComplianceLogs() {
  const [alertsRaw, setAlertsRaw] = useState([]);
  const [levelFilter, setLevelFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);

  const [, setWarningsChart] = useState(null);
  const [, setSeverityChart] = useState(null);

  // debounce search
  useEffect(() => {
    const id = setTimeout(() => setDebouncedQuery(query.trim().toLowerCase()), 250);
    return () => clearTimeout(id);
  }, [query]);

  // poll alerts
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/alerts`, { cache: "no-store" });
        if (!res.ok) throw new Error(`GET /alerts ${res.status}`);
        const data = await res.json();
        if (!alive) return;
        const arr = Array.isArray(data) ? data : [];
        arr.sort((a, b) => safeTime(b) - safeTime(a)); // newest first
        setAlertsRaw(arr);
      } catch (e) {
        console.error("[ComplianceLogs] fetch /alerts:", e);
        toast.error("Failed to load alerts from backend.");
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const baseList = useMemo(() => alertsRaw, [alertsRaw]);

  const levelFiltered = useMemo(() => {
    if (levelFilter === "All") return baseList;
    const want = levelFilter.toUpperCase();
    return baseList.filter((a) => getLevel(a) === want);
  }, [baseList, levelFilter]);

  const filtered = useMemo(() => {
    if (!debouncedQuery) return levelFiltered;
    return levelFiltered.filter((a) =>
      JSON.stringify(a).toLowerCase().includes(debouncedQuery)
    );
  }, [levelFiltered, debouncedQuery]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageSafe = Math.min(Math.max(1, page), totalPages);
  const pageSlice = useMemo(() => {
    const start = (pageSafe - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, pageSafe]);

  const chartRows = useMemo(() => filtered.slice(0, CHART_SAMPLE), [filtered]);

  const chartData = useMemo(() => {
    const warnBuckets = Object.create(null);
    for (const a of chartRows) {
      if (getLevel(a) !== "WARNING") continue;
      const ms = minuteStampLocal(a?.time || a?.timestamp || Date.now());
      if (ms == null) continue;
      warnBuckets[ms] = (warnBuckets[ms] || 0) + 1;
    }
    const minuteKeys = Object.keys(warnBuckets)
      .map(Number)
      .sort((a, b) => a - b);
    const labels = minuteKeys.map((k) => formatMinuteStamp(k));
    const counts = minuteKeys.map((k) => warnBuckets[k]); // <-- fixed

    const levelCounts = { INFO: 0, WARNING: 0, ERROR: 0, CRITICAL: 0 };
    for (const a of chartRows) {
      const L = getLevel(a);
      if (L in levelCounts) levelCounts[L]++;
    }
    return {
      labels,
      counts,
      sevLabels: Object.keys(levelCounts),
      sevCounts: Object.values(levelCounts),
    };
  }, [chartRows]);

  // charts
  useEffect(() => {
    const lineCanvas = document.getElementById("warningsChart");
    const pieCanvas = document.getElementById("severityChart");

    try {
      const e1 = lineCanvas && Chart.getChart(lineCanvas);
      if (e1) e1.destroy();
      const e2 = pieCanvas && Chart.getChart(pieCanvas);
      if (e2) e2.destroy();
    } catch {}

    if (!lineCanvas || !pieCanvas) return;

    const DPR = Chart.defaults.devicePixelRatio || 1;
    const sizeToParent = (canvas) => {
      const p = canvas.parentElement;
      if (!p) return false;
      const w = Math.max(100, Math.floor(p.clientWidth));
      const h = Math.max(100, Math.floor(p.clientHeight));
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      canvas.width = Math.floor(w * DPR);
      canvas.height = Math.floor(h * DPR);
      return true;
    };

    sizeToParent(lineCanvas);
    sizeToParent(pieCanvas);

    const lineCtx = lineCanvas.getContext("2d");
    const pieCtx = pieCanvas.getContext("2d");

    let inst1 = null;
    let inst2 = null;

    if (lineCtx) {
      inst1 = new Chart(lineCtx, {
        type: "line",
        data: {
          labels: chartData.labels,
          datasets: [
            {
              label: "Warnings / minute",
              data: chartData.counts,
              borderWidth: 2,
              borderColor: LEVEL_COLORS.WARNING,
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              pointRadius: 2,
              fill: true,
              tension: 0.2,
            },
          ],
        },
        options: {
          animation: false,
          plugins: {
            tooltip: { callbacks: { title: (items) => items?.[0]?.label || "" } },
            legend: { display: true },
          },
          scales: {
            x: { title: { display: true, text: "Time (local)" } },
            y: {
              title: { display: true, text: "Count" },
              beginAtZero: true,
              ticks: { precision: 0 },
            },
          },
        },
      });
      setWarningsChart(inst1);
    }

    if (pieCtx) {
      inst2 = new Chart(pieCtx, {
        type: "pie",
        data: {
          labels: chartData.sevLabels,
          datasets: [
            {
              data: chartData.sevCounts,
              backgroundColor: chartData.sevLabels.map(
                (l) => LEVEL_COLORS[l] || "#94a3b8"
              ),
              borderWidth: 0,
            },
          ],
        },
        options: { animation: false, plugins: { legend: { position: "top" } } },
      });
      setSeverityChart(inst2);
    }

    return () => {
      try {
        inst1 && inst1.destroy();
        inst2 && inst2.destroy();
      } catch {}
      setWarningsChart(null);
      setSeverityChart(null);
    };
  }, [chartData]);

  // export CSV of current filtered list
  const handleExportCSV = () => {
    const rowsToExport = filtered;
    if (!rowsToExport?.length) return;

    const headers = ["timestamp", "level", "message", "source"];
    const lines = rowsToExport.map((ev) => {
      const ts = ev.time || ev.timestamp || "";
      const lvl = getLevel(ev);
      const msg = (makeMessage(ev) || "").replace(/"/g, '""');
      const src =
        (ev?.host && (ev.host.name || ev.host.id)) || ev?.name || "agent";
      return [ts, lvl, `"${msg}"`, src].join(",");
    });

    const csv = [headers.join(","), ...lines].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "compliance_logs.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  // UI
  return (
    <div className="compliance-theme">
      <ToastContainer position="bottom-right" />

      {/* Yellow hero header */}
      <div className="c-hero">
        <div className="c-hero-left">
          <div className="c-hero-shield">
            <FaShieldAlt />
          </div>
          <div>
            <h3 className="c-hero-title">Compliance Logs</h3>
            <p className="c-hero-sub">
              Audit-friendly activity derived from system alerts.
            </p>
          </div>
        </div>

        <button className="c-btn-primary" onClick={handleExportCSV}>
          Export Logs
        </button>
      </div>

      {/* Badges + count */}
      <div
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          margin: "0 0 12px 0",
          fontSize: 13,
          color: "#475569",
        }}
      >
        <span>
          <span className="c-badge c-badge-info">INFO</span> Normal activity
        </span>
        <span>
          <span className="c-badge c-badge-error">ERROR</span> Suspicious
          system/resource activity
        </span>
        <span>
          <span className="c-badge c-badge-warning">WARNING</span> Strong
          ransomware indicators
        </span>
        <span style={{ marginLeft: "auto", fontWeight: 700 }}>
          {filtered.length.toLocaleString()} logs
        </span>
      </div>

      {/* Filters */}
      <div className="c-controls">
        <label className="c-field">
          <span>Severity</span>
          <select
            className="c-select"
            value={levelFilter}
            onChange={(e) => {
              setLevelFilter(e.target.value);
              setPage(1);
            }}
          >
            <option>All</option>
            <option>Info</option>
            <option>Warning</option>
            <option>Error</option>
            <option>Critical</option>
          </select>
        </label>

        <label className="c-field c-field-grow">
          <span>Search</span>
          <input
            className="c-input"
            placeholder="Filter by message, time, or source…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>

      {/* Charts */}
      <div className="c-charts">
        <div className="c-chart-card">
          <canvas id="warningsChart" />
        </div>
        <div className="c-chart-card">
          <canvas id="severityChart" />
        </div>
      </div>

      {/* Table */}
      <div className="card c-table-card">
        <div className="c-table-scroll">
          <table className="c-table">
            <thead>
              <tr>
                <th className="c-col-time">Timestamp</th>
                <th className="c-col-level">Level</th>
                <th>Message</th>
                <th className="c-col-source">Source</th>
              </tr>
            </thead>
            <tbody>
              {pageSlice.length === 0 ? (
                <tr className="c-empty">
                  <td colSpan={4}>No logs match your filters.</td>
                </tr>
              ) : (
                pageSlice.map((row, idx) => {
                  const lvl = getLevel(row);
                  let badgeClass = "c-badge c-badge-info";
                  if (lvl === "WARNING") badgeClass = "c-badge c-badge-warning";
                  else if (lvl === "ERROR") badgeClass = "c-badge c-badge-error";

                  const sourceName =
                    (row?.host && (row.host.name || row.host.id)) ||
                    row?.name ||
                    "agent";

                  return (
                    <tr key={idx}>
                      <td>{toLocal(row?.time || row?.timestamp)}</td>
                      <td>
                        <span className={badgeClass}>{lvl}</span>
                      </td>
                      <td style={{ fontFamily: "monospace" }}>
                        {makeMessage(row)}
                      </td>
                      <td>{sourceName}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            justifyContent: "flex-end",
            padding: "10px 14px",
          }}
        >
          <button
            className="c-btn c-btn-primary"
            disabled={pageSafe <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            style={{ opacity: pageSafe <= 1 ? 0.5 : 1 }}
          >
            Prev
          </button>
          <div style={{ minWidth: 120, textAlign: "center" }}>
            Page {pageSafe} / {totalPages}
          </div>
          <button
            className="c-btn c-btn-primary"
            disabled={pageSafe >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            style={{ opacity: pageSafe >= totalPages ? 0.5 : 1 }}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
