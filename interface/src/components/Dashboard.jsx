import React, { useEffect, useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Dashboard.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export default function Dashboard() {
  const nav = useNavigate();

  // live data
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [health, setHealth] = useState("unknown"); // ok | fail | unknown
  const [cfg, setCfg] = useState(null);

  // lightweight polling
  useEffect(() => {
    let alive = true;

    const pullHealth = async () => {
      try {
        const r = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (!alive) return;
        setHealth(r.ok ? "ok" : "fail");
      } catch {
        if (!alive) return;
        setHealth("fail");
      }
    };

    const pullMetrics = async () => {
      try {
        const r = await fetch(`${API_BASE}/metrics`);
        if (!alive) return;
        if (!r.ok) throw new Error("metrics");
        setMetrics(await r.json());
      } catch {
        if (!alive) return;
        setMetrics(null);
      }
    };

    const pullAlerts = async () => {
      try {
        const r = await fetch(`${API_BASE}/alerts`);
        if (!alive) return;
        if (!r.ok) throw new Error("alerts");
        const data = await r.json();
        setAlerts(Array.isArray(data) ? data.slice(-20) : []);
      } catch {
        if (!alive) return;
        setAlerts([]);
      }
    };

    const pullConfig = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/config`);
        if (!alive) return;
        if (!r.ok) throw new Error("config");
        setCfg(await r.json());
      } catch {
        if (!alive) return;
        setCfg(null);
      }
    };

    // initial
    pullHealth();
    pullMetrics();
    pullAlerts();
    pullConfig();

    // intervals (gentle)
    const hi = setInterval(pullHealth, 10000);
    const mi = setInterval(pullMetrics, 10000);
    const ai = setInterval(pullAlerts, 12000);
    const ci = setInterval(pullConfig, 30000);

    return () => {
      alive = false;
      clearInterval(hi);
      clearInterval(mi);
      clearInterval(ai);
      clearInterval(ci);
    };
  }, []);

  const recentAlerts = useMemo(
    () => alerts.slice(-5).reverse(),
    [alerts]
  );

  const agentId = cfg?.agent?.id || "—";
  const agentName = cfg?.agent?.name || "—";
  const outboundMode = cfg?.outbound?.mode || "https";

  return (
    <div className="dash-wrap">
      <main className="dash-main">
        {/* Header / welcome */}
        <div className="dash-header">
          <div>
            <h1 className="dash-title">Welcome to SecureScape</h1>
            <p className="dash-sub">
              Real Time OT Protection • Automated response • Compliance ready
            </p>
          </div>
          <div className="right-actions">
            <button className="btn primary" onClick={() => nav("/data-collection")}>
              View Live Data
            </button>
            <button className="btn ghost" onClick={() => nav("/compliance-logs")}>
              Compliance Logs
            </button>
          </div>
        </div>

        {/* Status strip */}
        <section className="status-strip">
          <div className="status-item">
            <span className={`dot ${health}`} />
            <div>
              <div className="label">Backend</div>
              <div className="value">{health === "ok" ? "Online" : health === "fail" ? "Offline" : "—"}</div>
            </div>
          </div>
          <div className="status-item">
            <div className="emoji">🖥️</div>
            <div>
              <div className="label">Agent</div>
              <div className="value">{agentName} <span className="muted">({agentId})</span></div>
            </div>
          </div>
          <div className="status-item">
            <div className="emoji">📤</div>
            <div>
              <div className="label">Outbound</div>
              <div className="value">{outboundMode.toUpperCase()}</div>
            </div>
          </div>
          <div className="status-item">
            <div className="emoji">🔔</div>
            <div>
              <div className="label">Alerts (24h)</div>
              <div className="value">{alerts.length}</div>
            </div>
          </div>
        </section>

        {/* KPIs */}
        <section className="kpis">
          <div className="kpi">
            <div className="kpi-icon">⚡</div>
            <div className="kpi-label">CPU Usage</div>
            <div className="kpi-value">{metrics ? `${metrics.cpu_usage}%` : "—"}</div>
          </div>
          <div className="kpi">
            <div className="kpi-icon">💾</div>
            <div className="kpi-label">RAM Usage</div>
            <div className="kpi-value">{metrics ? `${metrics.ram_usage}%` : "—"}</div>
          </div>
          <div className="kpi">
            <div className="kpi-icon">🌡️</div>
            <div className="kpi-label">Temperature</div>
            <div className="kpi-value">{metrics ? `${metrics.temperature}°C` : "—"}</div>
          </div>
          <div className="kpi">
            <div className="kpi-icon">📡</div>
            <div className="kpi-label">Packet Count</div>
            <div className="kpi-value">{metrics ? metrics.packet_count : "—"}</div>
          </div>
        </section>

        {/* Middle grid */}
        <section className="grid-2">
          {/* Quick actions / shortcuts */}
          <div className="card quick">
            <h3 className="card-title">Quick Actions</h3>
            <div className="qa-grid">
              <Link className="qa" to="/data-collection">
                <span>📈</span>
                <div>
                  <div className="qa-title">Open Live Metrics</div>
                  <div className="qa-sub">CPU / RAM trends & full alerts table</div>
                </div>
              </Link>
              <Link className="qa" to="/compliance-logs">
                <span>📑</span>
                <div>
                  <div className="qa-title">Export Compliance Logs</div>
                  <div className="qa-sub">Audit friendly CSV for regulators</div>
                </div>
              </Link>
              <Link className="qa" to="/settings">
                <span>⚙️</span>
                <div>
                  <div className="qa-title">Tune Thresholds</div>
                  <div className="qa-sub">Burst / CPU / Disk write limits</div>
                </div>
              </Link>
              <Link className="qa" to="/backups">
                <span>🛡️</span>
                <div>
                  <div className="qa-title">Backups & Recovery</div>
                  <div className="qa-sub">Immutable snapshots & test restores</div>
                </div>
              </Link>
            </div>
          </div>

          {/* Recent alerts */}
          <div className="card alerts">
            <h3 className="card-title">Recent Alerts</h3>
            {recentAlerts.length === 0 ? (
              <div className="empty">No recent alerts.</div>
            ) : (
              <ul className="alert-list">
                {recentAlerts.map((a, i) => (
                  <li key={i}>
                    <span className={`badge ${String(a.level || "INFO").toLowerCase()}`}>{a.level}</span>
                    <span className="ts">{a.timestamp}</span>
                    <span className="msg">{a.message}</span>
                  </li>
                ))}
              </ul>
            )}
            <div className="card-actions">
              <button className="btn primary" onClick={() => nav("/data-collection")}>
                View All Alerts
              </button>
            </div>
          </div>
        </section>

        {/* Lower grid */}
        <section className="grid-3">
          {/* Backup snapshot */}
          <div className="card mini">
            <h3 className="card-title">Backup Status</h3>
            <div className="mini-row">
              <div className="mini-icon">💽</div>
              <div>
                <div className="mini-label">Immutable storage</div>
                <div className="mini-value">Configured</div>
              </div>
            </div>
            <div className="mini-row">
              <div className="mini-icon">⏱️</div>
              <div>
                <div className="mini-label">Last test restore</div>
                <div className="mini-value">— (run from Backups)</div>
              </div>
            </div>
            <div className="card-actions">
              <Link className="btn ghost" to="/backups">Open Backups</Link>
            </div>
          </div>

          {/* Compliance snapshot */}
          <div className="card mini">
            <h3 className="card-title">Compliance</h3>
            <div className="mini-row">
              <div className="mini-icon">📜</div>
              <div>
                <div className="mini-label">Audit trail</div>
                <div className="mini-value">Enabled</div>
              </div>
            </div>
            <div className="mini-row">
              <div className="mini-icon">✅</div>
              <div>
                <div className="mini-label">Export readiness</div>
                <div className="mini-value">CSV available</div>
              </div>
            </div>
            <div className="card-actions">
              <Link className="btn ghost" to="/compliance-logs">Open Logs</Link>
            </div>
          </div>

          {/* Account / Auth hooks */}
          <div className="card mini">
            <h3 className="card-title">Account</h3>
            <p className="mini-note">
              Sign in or Create an Account.
            </p>
            <div className="row-gap">
              <Link className="btn primary block" to="/login">Log in</Link>
              <Link className="btn ghost block" to="/signup">Sign up</Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

