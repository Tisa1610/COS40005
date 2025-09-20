// src/components/Settings.jsx
import React, { useEffect, useMemo, useState } from "react";
import "./Settings.css";

const API = (process.env.REACT_APP_API_BASE?.replace(/\/$/, "")) || "http://127.0.0.1:8000";

const emptyConfig = {
  agent: {
    id: "",
    name: "",
    watch_paths: [""],
    ext_watchlist: [".lockbit", ".conti"],
    file_burst_threshold_per_sec: 120,
    cpu_usage_threshold: 80,
    io_write_threshold_bytes: 52428800,
  },
  outbound: {
    mode: "https",
    https: { url: "http://127.0.0.1:8000/ingest", cafile: "" },
    mqtt:  { host: "localhost", port: 8883, username: "", password: "", cafile: "" },
  },
};

export default function Settings() {
  const [cfg, setCfg] = useState(emptyConfig);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState({ kind: "idle", text: "" });
  const [status, setStatus] = useState({ health: null, metrics: null, alerts: null });

  // derived flags
  const canSave = useMemo(() => !loading && !saving, [loading, saving]);

  useEffect(() => { loadConfig(); /* eslint-disable-next-line */ }, []);

  async function loadConfig() {
    setLoading(true);
    setMsg({ kind: "info", text: "Loading config…" });
    try {
      const r = await fetch(`${API}/api/config`);
      if (!r.ok) throw new Error(`GET /api/config ${r.status}`);
      const data = await r.json();

      // Defensive merge
      const merged = structuredClone(emptyConfig);
      Object.assign(merged.agent, data.agent || {});
      Object.assign(merged.outbound.https, data?.outbound?.https || {});
      Object.assign(merged.outbound.mqtt,  data?.outbound?.mqtt  || {});
      merged.outbound.mode = data?.outbound?.mode || merged.outbound.mode;

      setCfg(merged);
      setMsg({ kind: "ok", text: "Config loaded." });
    } catch (e) {
      setMsg({ kind: "error", text: `Failed to load config: ${e.message}` });
    } finally {
      setLoading(false);
    }
  }

  function set(path, value) {
    setCfg(prev => {
      const copy = structuredClone(prev);
      let ref = copy;
      for (let i = 0; i < path.length - 1; i++) ref = ref[path[i]];
      ref[path[path.length - 1]] = value;
      return copy;
    });
  }

  function setList(path, idx, value) {
    setCfg(prev => {
      const copy = structuredClone(prev);
      let ref = copy;
      for (let i = 0; i < path.length; i++) ref = ref[path[i]];
      ref[idx] = value;
      return copy;
    });
  }

  function addList(path) {
    setCfg(prev => {
      const copy = structuredClone(prev);
      let ref = copy; for (let i = 0; i < path.length; i++) ref = ref[path[i]];
      ref.push("");
      return copy;
    });
  }

  function removeList(path, idx) {
    setCfg(prev => {
      const copy = structuredClone(prev);
      let ref = copy; for (let i = 0; i < path.length; i++) ref = ref[path[i]];
      ref.splice(idx, 1);
      if (ref.length === 0) ref.push("");
      return copy;
    });
  }

  function validate() {
    const a = cfg.agent;
    if (!a.id?.trim()) return "Agent ID is required.";
    if (!a.name?.trim()) return "Agent name is required.";
    if (!Array.isArray(a.watch_paths) || !a.watch_paths.some(p => p.trim()))
      return "At least one Watch Path is required.";
    if (+a.file_burst_threshold_per_sec <= 0) return "File burst threshold must be > 0.";
    if (+a.cpu_usage_threshold <= 0) return "CPU threshold must be > 0.";
    if (+a.io_write_threshold_bytes <= 0) return "Disk write threshold must be > 0.";

    if (cfg.outbound.mode === "https") {
      const url = cfg.outbound.https?.url || "";
      if (!/^https?:\/\//i.test(url)) return "Collector URL must start with http(s)://";
      if (!url.endsWith("/ingest")) return "Collector URL should end with /ingest";
    } else {
      const m = cfg.outbound.mqtt;
      if (!m?.host) return "MQTT host is required.";
      if (!m?.port) return "MQTT port is required.";
    }
    return null;
  }

  async function save() {
    const err = validate();
    if (err) { setMsg({ kind: "warn", text: err }); return; }
    setSaving(true);
    setMsg({ kind: "info", text: "Saving…" });
    try {
      const r = await fetch(`${API}/api/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      if (!r.ok) throw new Error(`PUT /api/config ${r.status}`);
      await r.json();
      setMsg({ kind: "ok", text: "Config saved." });
    } catch (e) {
      setMsg({ kind: "error", text: `Failed to save config: ${e.message}` });
    } finally {
      setSaving(false);
    }
  }

  async function reloadAgent() {
    try {
      const r = await fetch(`${API}/api/agent/reload`, { method: "POST" });
      setMsg(r.ok ? { kind: "ok", text: "Reload signalled." }
                  : { kind: "error", text: `Reload failed: ${r.status}` });
    } catch (e) {
      setMsg({ kind: "error", text: `Reload failed: ${e.message}` });
    }
  }

  async function test(kind) {
    try {
      const r = await fetch(`${API}/${kind}`, { cache: "no-store" });
      setStatus(s => ({ ...s, [kind]: r.ok ? "ok" : "fail" }));
    } catch {
      setStatus(s => ({ ...s, [kind]: "fail" }));
    }
  }

  const chip = (v) =>
    v === "ok"   ? <span className="chip ok">OK</span> :
    v === "fail" ? <span className="chip bad">FAIL</span> :
                   <span className="chip">—</span>;

  return (
    <div className="settings-page">
      {/* Sticky header actions */}
      <div className="toolbar">
        <div className="title">Platform Settings</div>
        <div className="actions">
          <button className="btn" onClick={loadConfig} disabled={loading}>Load</button>
          <button className="btn primary" onClick={save} disabled={!canSave}>Save</button>
          <button className="btn ghost" onClick={reloadAgent}>Reload Agent</button>
        </div>
      </div>

      {msg.text && <div className={`notice ${msg.kind}`}>{msg.text}</div>}

      {/* Agent */}
      <section className="card">
        <div className="card-title">Agent</div>
        <div className="grid two">
          <label className="field">
            <span>Agent ID</span>
            <input value={cfg.agent.id} onChange={(e)=>set(["agent","id"], e.target.value)} />
            <small>Unique stable identifier for this endpoint.</small>
          </label>
          <label className="field">
            <span>Agent Name</span>
            <input value={cfg.agent.name} onChange={(e)=>set(["agent","name"], e.target.value)} />
            <small>Display name seen in alerts & dashboards.</small>
          </label>
          <label className="field">
            <span>File Burst Threshold (/sec)</span>
            <input type="number" min="1"
              value={cfg.agent.file_burst_threshold_per_sec}
              onChange={(e)=>set(["agent","file_burst_threshold_per_sec"], +e.target.value)} />
            <small>Trigger sev↑ when many files change per second.</small>
          </label>
          <label className="field">
            <span>CPU Threshold (%)</span>
            <input type="number" min="1"
              value={cfg.agent.cpu_usage_threshold}
              onChange={(e)=>set(["agent","cpu_usage_threshold"], +e.target.value)} />
            <small>Flag processes exceeding this CPU usage.</small>
          </label>
          <label className="field">
            <span>Disk Write Threshold (bytes/sec)</span>
            <input type="number" min="1"
              value={cfg.agent.io_write_threshold_bytes}
              onChange={(e)=>set(["agent","io_write_threshold_bytes"], +e.target.value)} />
            <small>Flag processes with heavy write throughput.</small>
          </label>
        </div>

        <div className="row-split">
          <div className="col">
            <div className="subhead">
              Watch Paths
              <button className="mini" onClick={() => addList(["agent","watch_paths"])}>Add Path</button>
            </div>
            {cfg.agent.watch_paths.map((p,i)=>(
              <div className="list-row" key={`wp-${i}`}>
                <input
                  placeholder='e.g. C:\\Users\\Public'
                  value={p}
                  onChange={(e)=>setList(["agent","watch_paths"], i, e.target.value)} />
                <button className="mini ghost" onClick={()=>removeList(["agent","watch_paths"], i)}>Remove</button>
              </div>
            ))}
          </div>

          <div className="col">
            <div className="subhead">
              Extension Watchlist
              <button className="mini" onClick={() => addList(["agent","ext_watchlist"])}>Add Extension</button>
            </div>
            {cfg.agent.ext_watchlist.map((p,i)=>(
              <div className="list-row" key={`ext-${i}`}>
                <input placeholder=".lockbit" value={p}
                  onChange={(e)=>setList(["agent","ext_watchlist"], i, e.target.value)} />
                <button className="mini ghost" onClick={()=>removeList(["agent","ext_watchlist"], i)}>Remove</button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Outbound */}
      <section className="card">
        <div className="card-title">Outbound</div>

        <label className="field" style={{ maxWidth: 360 }}>
          <span>Mode</span>
          <select value={cfg.outbound.mode} onChange={(e)=>set(["outbound","mode"], e.target.value)}>
            <option value="https">HTTP(S)</option>
            <option value="mqtt">MQTT</option>
          </select>
        </label>

        {cfg.outbound.mode === "https" && (
          <div className="grid two">
            <label className="field">
              <span>Collector URL</span>
              <input value={cfg.outbound.https.url}
                     onChange={(e)=>set(["outbound","https","url"], e.target.value)}
                     placeholder="http://127.0.0.1:8000/ingest" />
              <small>Local dev uses http://127.0.0.1:8000/ingest</small>
            </label>
            <label className="field">
              <span>CA File (optional)</span>
              <input value={cfg.outbound.https.cafile || ""}
                     onChange={(e)=>set(["outbound","https","cafile"], e.target.value)}
                     placeholder="path/to/ca.crt" />
              <small>Only required for custom TLS roots.</small>
            </label>
          </div>
        )}

        {cfg.outbound.mode === "mqtt" && (
          <div className="grid two">
            <label className="field"><span>Host</span>
              <input value={cfg.outbound.mqtt.host}
                     onChange={(e)=>set(["outbound","mqtt","host"], e.target.value)} />
            </label>
            <label className="field"><span>Port</span>
              <input type="number" value={cfg.outbound.mqtt.port}
                     onChange={(e)=>set(["outbound","mqtt","port"], +e.target.value)} />
            </label>
            <label className="field"><span>Username</span>
              <input value={cfg.outbound.mqtt.username || ""}
                     onChange={(e)=>set(["outbound","mqtt","username"], e.target.value)} />
            </label>
            <label className="field"><span>Password</span>
              <input type="password" value={cfg.outbound.mqtt.password || ""}
                     onChange={(e)=>set(["outbound","mqtt","password"], e.target.value)} />
            </label>
            <label className="field"><span>CA File</span>
              <input value={cfg.outbound.mqtt.cafile || ""}
                     onChange={(e)=>set(["outbound","mqtt","cafile"], e.target.value)} />
            </label>
          </div>
        )}
      </section>

      {/* Security note */}
      <section className="card">
        <div className="card-title">Security</div>
        <p className="muted">HMAC key is managed by the server and is not editable here.</p>
      </section>

      {/* Diagnostics */}
      <section className="card">
        <div className="card-title">Diagnostics</div>
        <div className="diag">
          <button className="btn mini" onClick={()=>test("health")}>Test Health</button>
          <span>Health: {chip(status.health)}</span>

          <button className="btn mini" onClick={()=>test("metrics")}>Test Metrics</button>
          <span>Metrics: {chip(status.metrics)}</span>

          <button className="btn mini" onClick={()=>test("alerts")}>Test Alerts</button>
          <span>Alerts: {chip(status.alerts)}</span>
        </div>
        <p className="muted small">API Base: <code>{API}</code></p>
      </section>
    </div>
  );
}
