// src/components/ComplianceLogs.jsx
import React, { useEffect, useMemo, useState } from "react";
import { FaShieldAlt } from "react-icons/fa";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "./ComplianceLogs.css";

const API_BASE =
  process.env.REACT_APP_API_BASE?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export default function ComplianceLogs() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [severity, setSeverity] = useState("ALL"); // ALL | INFO | WARNING | ERROR
  const [q, setQ] = useState("");

  // pull alerts periodically (light polling)
  useEffect(() => {
    let alive = true;

    const fetchAlerts = async () => {
      try {
        const r = await fetch(`${API_BASE}/alerts`);
        if (!r.ok) throw new Error(`alerts ${r.status}`);
        const data = await r.json();
        if (!alive) return;
        setAlerts(Array.isArray(data) ? data : []);
        setLoading(false);
      } catch (e) {
        console.error(e);
        if (alive) setLoading(false);
      }
    };

    fetchAlerts();
    const id = setInterval(fetchAlerts, 8000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // derived, filtered “compliance logs”
  const logs = useMemo(() => {
    const s = severity.toUpperCase();
    const qn = q.trim().toLowerCase();

    return alerts.filter((a) => {
      const level = (a.level || "").toUpperCase();
      if (s !== "ALL" && level !== s) return false;

      if (qn) {
        const msg = `${a.timestamp} ${a.level} ${a.message ?? ""} ${a.source ?? ""}`.toLowerCase();
        if (!msg.includes(qn)) return false;
      }
      return true;
    });
  }, [alerts, severity, q]);

  const exportCSV = () => {
    if (!logs.length) {
      toast.info("No logs to export.");
      return;
    }
    const header = ["Timestamp", "Level", "Message", "Source"].join(",");
    const rows = logs.map((a) =>
      [
        a.timestamp,
        a.level,
        String(a.message ?? "").replace(/,/g, ";"),
        a.source || "backend",
      ].join(",")
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "compliance_logs.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Compliance logs exported.");
  };

  return (
    <div className="compliance-wrap">
      {/* IMPORTANT: this page provides only main content.
          The sidebar comes from your shared Layout, so we never touch .sidebar sizes here. */}
      <main className="compliance-main">
        <h1 className="c-title">Compliance</h1>

        {/* hero card */}
        <section className="c-hero">
          <FaShieldAlt className="c-hero-icon" />
          <div className="c-hero-text">
            <h2 className="c-hero-title">Compliance Logs</h2>
            <p className="c-hero-sub">Audit friendly activity derived from system alerts.</p>
          </div>
          <button className="c-btn c-btn-primary" onClick={exportCSV}>
            Export Logs
          </button>
        </section>

        {/* controls */}
        <section className="c-controls">
          <label className="c-field">
            <span>Severity</span>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="c-select"
            >
              <option value="ALL">All</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
            </select>
          </label>

          <label className="c-field c-field-grow">
            <span>Search</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Filter by message, time, or source…"
              className="c-input"
            />
          </label>

          <div className="c-count">
            {loading ? "Loading…" : `${logs.length} log${logs.length === 1 ? "" : "s"}`}
          </div>
        </section>

        {/* table */}
        <section className="c-table-card">
          {loading ? (
            <div className="c-loading">Fetching logs…</div>
          ) : logs.length === 0 ? (
            <div className="c-empty">No logs match your filters.</div>
          ) : (
            <div className="c-table-scroll">
              <table className="c-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Level</th>
                    <th>Message</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {logs
                    .slice()
                    .reverse()
                    .map((a, i) => (
                      <tr key={`${a.timestamp}-${i}`}>
                        <td className="c-col-time">{a.timestamp}</td>
                        <td className="c-col-level">
                          <span className={`c-badge c-badge-${(a.level || "info").toLowerCase()}`}>
                            {a.level}
                          </span>
                        </td>
                        <td className="c-col-msg">{a.message}</td>
                        <td className="c-col-source">{a.source || "backend"}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <ToastContainer position="bottom-right" />
      </main>
    </div>
  );
}
