import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import "./Home.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export default function Home() {
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [history, setHistory] = useState([]);
  const [health, setHealth] = useState("unknown"); // ok | fail | unknown

  // Pull metrics/alerts and a small rolling history used only for the tiny sparkline
  useEffect(() => {
    let alive = true;

    const ping = async () => {
      try {
        const r = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (!alive) return;
        setHealth(r.ok ? "ok" : "fail");
      } catch {
        if (alive) setHealth("fail");
      }
    };

    const pullMetrics = async () => {
      try {
        const r = await fetch(`${API_BASE}/metrics`);
        if (!alive) return;
        if (!r.ok) throw new Error("metrics");
        const data = await r.json();
        setMetrics(data);
        setHistory((prev) => [
          ...prev.slice(-29),
          {
            t: new Date().toLocaleTimeString(),
            cpu: data.cpu_usage,
            ram: data.ram_usage,
          },
        ]);
      } catch {}
    };

    const pullAlerts = async () => {
      try {
        const r = await fetch(`${API_BASE}/alerts`);
        if (!alive) return;
        if (!r.ok) throw new Error("alerts");
        const data = await r.json();
        setAlerts(Array.isArray(data) ? data.slice(-5).reverse() : []);
      } catch {}
    };

    ping(); pullMetrics(); pullAlerts();
    const idH = setInterval(ping, 10000);
    const idM = setInterval(pullMetrics, 5000);
    const idA = setInterval(pullAlerts, 8000);
    return () => { alive = false; clearInterval(idH); clearInterval(idM); clearInterval(idA); };
  }, []);

  const statusDot = useMemo(
    () => <span className={`home-health ${health}`} />,
    [health]
  );

  return (
    <div className="home-wrap">
      {/* header */}
      <div className="home-header">
        <h1 className="home-title">Operational Overview</h1>
        <div className="home-right">
          {statusDot}
          <span className="home-health-text">
            {health === "ok" ? "Backend online" : health === "fail" ? "Backend offline" : "—"}
          </span>
        </div>
      </div>

      {/* tiles */}
      <div className="home-tiles">
        <Tile label="CPU Usage" icon="⚡" value={metrics ? `${metrics.cpu_usage}%` : "—"} />
        <Tile label="RAM Usage" icon="💾" value={metrics ? `${metrics.ram_usage}%` : "—"} />
        <Tile label="Temperature" icon="🌡️" value={metrics ? `${metrics.temperature}°C` : "—"} />
        <Tile label="Network Packets" icon="📡" value={metrics ? metrics.packet_count : "—"} />
      </div>

      {/* middle row: sparkline + recent alerts */}
      <div className="home-row">
        <div className="home-card">
          <div className="home-card-head">
            <h3>System Trend (CPU & RAM)</h3>
            <Link className="home-link" to="/data">Open Data Collection →</Link>
          </div>
          <div className="home-chart">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="t" minTickGap={28} />
                <YAxis domain={[0, 100]} hide />
                <Tooltip />
                <Line type="monotone" dataKey="cpu" name="CPU (%)" stroke="#f59e0b" dot={false} />
                <Line type="monotone" dataKey="ram" name="RAM (%)" stroke="#ef4444" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="home-card">
          <div className="home-card-head">
            <h3>Recent Alerts</h3>
            <Link className="home-link" to="/compliance">Compliance Logs →</Link>
          </div>
          <ul className="home-alerts">
            {alerts.length === 0 && <li className="home-empty">No recent alerts.</li>}
            {alerts.map((a, i) => (
              <li key={i}>
                <span className={`tag tag-${(a.level || "info").toLowerCase()}`}>{a.level}</span>
                <span className="msg">{a.message}</span>
                <span className="ts">{a.timestamp}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* quick actions */}
      <div className="home-actions">
        <Link className="btn btn-primary" to="/settings">Configure Agent</Link>
        <Link className="btn btn-light" to="/incidents">Open Incident Response</Link>
        <Link className="btn btn-light" to="/backups">Backups</Link>
      </div>
    </div>
  );
}

function Tile({ label, value, icon }) {
  return (
    <div className="home-tile">
      <div className="tile-icon">{icon}</div>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
    </div>
  );
}
