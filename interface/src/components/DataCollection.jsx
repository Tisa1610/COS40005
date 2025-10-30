import React, { useEffect, useState, useRef, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "./DataCollection.css";

const API_BASE = (process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

/* -------------------- Shared-ish logic (mirrors Compliance Logs) -------------------- */
function getLevel(ev = {}) {
  const explicit = (ev.level || "").toString().toUpperCase();
  if (["INFO", "WARNING", "ERROR", "CRITICAL"].includes(explicit)) return explicit;

  const sev = Number(ev.severity || ev.sev || 0);
  let score = Number(ev.score || 0);
  if (!score) score = Number(ev.signals?.score || 0);
  const subtype = (ev.subtype || "").toLowerCase();
  const etype = (ev.type || "").toLowerCase();

  if (sev <= 1 && score < 20) return "INFO";
  if (etype === "resource" || subtype.includes("cpu") || subtype.includes("disk"))
    return "ERROR"; // suspicious system/resource
  if (
    score >= 70 ||
    sev >= 3 ||
    subtype.includes("service_install") ||
    subtype.includes("vss_delete")
  )
    return "WARNING"; // strong ransomware indicators

  return sev >= 2 ? "ERROR" : "INFO";
}

function buildMessage(a = {}) {
  // Prefer any explicit message fields, otherwise synthesize something readable
  const first =
    a.message ||
    a.msg ||
    a.text ||
    a.data?.message ||
    a.data?.msg ||
    a.description;

  if (first && String(first).trim()) return String(first);

  const name = a.name || "Windows-Ransomware-Defense";
  const type = a.type || "event";
  const sub = a.subtype || "log";
  const sev = a.severity ?? a.sev ?? 0;
  const score = a.score ?? a.signals?.score ?? 0;
  return `${name}: ${type}/${sub} (sev=${sev}, score=${score})`;
}

/** Normalize any backend alert into a consistent shape for this page */
function normalizeAlert(a = {}) {
  const ts = a.timestamp || a.time || a.when || a.created_at || a.date || a.dt || "";
  const level = getLevel(a);
  const message = buildMessage(a);
  const source = a.source || a.host?.name || a.host?.id || a.origin || a.name || "agent";
  return { timestamp: ts, level, message, source };
}

function fmtTime(t) {
  try {
    const d = new Date(t);
    if (!isNaN(d)) return d.toLocaleString();
  } catch {}
  return String(t ?? "—");
}
/* ----------------------------------------------------------------------------------- */

function DataCollection() {
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [history, setHistory] = useState([]);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState(null);

  // UI polish
  const [health, setHealth] = useState("unknown");
  const [lastMetricsAt, setLastMetricsAt] = useState(null);
  const [lastAlertsAt, setLastAlertsAt] = useState(null);

  // Alerts UX
  const [levelFilter, setLevelFilter] = useState("ALL");
  const [query, setQuery] = useState("");
  const tableEndRef = useRef(null);

  // load saved trend
  useEffect(() => {
    const saved = localStorage.getItem("metricHistory");
    if (saved) {
      try {
        setHistory(JSON.parse(saved));
      } catch {}
    }
  }, []);

  // persist trend
  useEffect(() => {
    if (history.length) {
      localStorage.setItem("metricHistory", JSON.stringify(history));
    }
  }, [history]);

  // backend polling
  useEffect(() => {
    let alive = true;

    const pingHealth = async () => {
      try {
        const r = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        setHealth(r.ok ? "ok" : "fail");
      } catch {
        setHealth("fail");
      }
    };

    const fetchMetrics = async () => {
      try {
        const res = await fetch(`${API_BASE}/metrics`);
        if (!res.ok) throw new Error(`metrics ${res.status}`);
        const data = await res.json();
        if (!alive) return;

        setMetrics(data);
        setLastMetricsAt(new Date());

        if (!paused) {
          setHistory((prev) => [
            ...prev.slice(-59),
            {
              time: new Date().toLocaleTimeString(),
              cpu: data.cpu_usage,
              ram: data.ram_usage,
            },
          ]);
        }
        setError(null);
      } catch {
        setError("Could not load metrics");
      }
    };

    const fetchAlerts = async () => {
      try {
        const res = await fetch(`${API_BASE}/alerts`);
        if (!res.ok) throw new Error(`alerts ${res.status}`);
        const data = await res.json();
        if (!alive) return;

        // normalize + newest first + keep last 500
        const norm = (Array.isArray(data) ? data : []).map(normalizeAlert);
        norm.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        setAlerts(norm.slice(0, 500));
        setLastAlertsAt(new Date());
      } catch {
        /* keep previous alerts on transient failures */
      }
    };

    pingHealth();
    fetchMetrics();
    fetchAlerts();

    const healthId = setInterval(pingHealth, 10000);
    const metricId = setInterval(fetchMetrics, 5000);
    const alertsId = setInterval(fetchAlerts, 7000);

    return () => {
      alive = false;
      clearInterval(healthId);
      clearInterval(metricId);
      clearInterval(alertsId);
    };
  }, [paused]);

  // filter alerts
  const visibleAlerts = useMemo(() => {
    const q = query.trim().toLowerCase();
    return alerts.filter((a) => {
      const levelOk = levelFilter === "ALL" || a.level === levelFilter;
      if (!levelOk) return false;
      if (!q) return true;
      return (
        (a.message || "").toLowerCase().includes(q) ||
        (String(a.timestamp) || "").toLowerCase().includes(q) ||
        (a.source || "").toLowerCase().includes(q)
      );
    });
  }, [alerts, levelFilter, query]);

  // CSV exports
  const exportAlertsToCSV = () => {
    if (!visibleAlerts.length) return;
    const headers = ["Timestamp", "Level", "Message", "Source"];
    const rows = visibleAlerts.map((a) => [
      fmtTime(a.timestamp),
      a.level,
      (a.message || "").replace(/"/g, '""'),
      a.source || "",
    ]);
    const csv = [headers.join(","), ...rows.map((r) => `${r[0]},${r[1]},"${r[2]}",${r[3]}`)].join(
      "\n"
    );
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "system_alerts.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Alerts CSV downloaded");
  };

  const exportMetricsToCSV = () => {
    if (!metrics) return;
    const headers = ["CPU Usage (%)", "RAM Usage (%)", "Temperature (°C)", "Packet Count"];
    const row = `${metrics.cpu_usage},${metrics.ram_usage},${metrics.temperature},${metrics.packet_count}`;
    const csv = [headers.join(","), row].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "current_metrics.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Current metrics CSV downloaded");
  };

  const exportMetricHistoryToCSV = () => {
    if (!history.length) return;
    const headers = ["Time", "CPU Usage (%)", "RAM Usage (%)"];
    const rows = history.map((r) => `${r.time},${r.cpu},${r.ram}`);
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "metric_history.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Metric history CSV downloaded");
  };

  return (
    <div className="data-layout">
      <main className="data-main">
        <div className="page-title-row">
          <h2 className="page-title">Data Collection</h2>
          <div className="status-right">
            <span className={`health-dot ${health}`} />
            <span className="health-text">
              {health === "ok"
                ? "Backend online"
                : health === "fail"
                ? "Backend offline"
                : "—"}
            </span>
          </div>
        </div>

        {error && <div className="error-banner">API error: {error}</div>}

        {/* Metrics cards */}
        <div className="data-cards">
          {/* CPU */}
          <div className="card voltage-card">
            <div className="card-icon">⚡</div>
            <div className="card-label">CPU Usage</div>
            <div className="card-value">
              {metrics ? `${metrics.cpu_usage}%` : "Loading..."}
            </div>
            <div className="subtle">
              {lastMetricsAt ? `Updated ${lastMetricsAt.toLocaleTimeString()}` : "—"}
            </div>
            <button className="export-btn small" onClick={exportMetricsToCSV}>
              Export Metrics CSV
            </button>
          </div>

          {/* RAM */}
          <div className="card current-card">
            <div className="card-icon">💾</div>
            <div className="card-label">RAM Usage</div>
            <div className="card-value">
              {metrics ? `${metrics.ram_usage}%` : "Loading..."}
            </div>
            <div className="subtle">&nbsp;</div>
          </div>

          {/* Temp */}
          <div className="card network-card">
            <div className="card-icon">🌡️</div>
            <div className="card-label">Temperature</div>
            <div className="card-value">
              {metrics ? `${metrics.temperature}°C` : "Loading..."}
            </div>
            <div className="subtle">&nbsp;</div>
          </div>

          {/* Packets */}
          <div className="card network-card">
            <div className="card-icon">📡</div>
            <div className="card-label">Packet Count</div>
            <div className="card-value">
              {metrics ? metrics.packet_count : "Loading..."}
            </div>
            <div className="subtle">&nbsp;</div>
          </div>
        </div>

        {/* Trends */}
        <div className="metric-section">
          <div className="metric-header">
            <h3 className="metric-title">Metric Trends (CPU & RAM)</h3>
            <div className="metric-controls">
              <button
                className="export-btn small secondary"
                onClick={() => setPaused((p) => !p)}
              >
                {paused ? "Resume Live" : "Pause Live"}
              </button>
              <button className="export-btn small" onClick={exportMetricHistoryToCSV}>
                Export Trend CSV
              </button>
            </div>
          </div>

          <div className="metric-chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" minTickGap={40} />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={(v, name) => [`${v}%`, name]} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="cpu"
                  stroke="#facc15"
                  name="CPU Usage (%)"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="ram"
                  stroke="#f87171"
                  name="RAM Usage (%)"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Alerts */}
        <div className="alert-section">
          <div className="alert-header">
            <h3 className="alert-title">System Alerts</h3>

            <div className="alert-actions">
              <label className="field">
                <span className="label">Level</span>
                <select
                  value={levelFilter}
                  onChange={(e) => setLevelFilter(e.target.value)}
                >
                  <option value="ALL">All</option>
                  <option value="INFO">Info</option>
                  <option value="WARNING">Warning</option>
                  <option value="ERROR">Error</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </label>

              <label className="field">
                <span className="label">Search</span>
                <input
                  type="text"
                  placeholder="message or timestamp…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>

              <button className="export-btn" onClick={exportAlertsToCSV}>
                Export Visible CSV
              </button>
            </div>
          </div>

          <div className="subtle mb8">
            {lastAlertsAt ? `Last update ${lastAlertsAt.toLocaleTimeString()}` : "—"}
          </div>

          <div className="table-wrap">
            <table className="alert-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Level</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {visibleAlerts.length === 0 ? (
                  <tr className="empty-row">
                    <td colSpan="3">No alerts match your filters.</td>
                  </tr>
                ) : (
                  visibleAlerts.map((alert, i) => (
                    <tr
                      key={`${alert.timestamp}-${i}`}
                      className={`row-${(alert.level || "").toLowerCase()}`}
                    >
                      <td>{fmtTime(alert.timestamp)}</td>
                      <td>
                        <span
                          className={`badge badge-${(alert.level || "")
                            .toLowerCase()}`}
                        >
                          {alert.level}
                        </span>
                      </td>
                      <td style={{ fontFamily: "monospace" }}>{alert.message}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <div ref={tableEndRef} />
          </div>
        </div>

        <ToastContainer position="bottom-right" />
      </main>
    </div>
  );
}

export default DataCollection;
