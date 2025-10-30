// src/pages/Backups.jsx
import React, { useEffect, useMemo, useState } from "react";
import "./Backups.css";

const API_BASE = (process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

function fmtTime(ts) {
  try {
    return new Date(Number(ts) * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

export default function Backups() {
  const [settings, setSettings] = useState({
    source_path: "",
    backup_dir: "",
    retention_count: 5,
    max_total_gb: 2.0,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [destRestore, setDestRestore] = useState("");

  const loadSettings = async () => {
    const r = await fetch(`${API_BASE}/api/backups/settings`);
    const data = await r.json();
    setSettings(data);
  };
  const loadList = async () => {
    const r = await fetch(`${API_BASE}/api/backups`);
    const data = await r.json();
    setItems(Array.isArray(data) ? data : []);
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      try { await loadSettings(); await loadList(); }
      finally { setLoading(false); }
    })();
  }, []);

  const onSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const r = await fetch(`${API_BASE}/api/backups/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!r.ok) throw new Error("Failed to save");
      await loadSettings();
      alert("Settings saved.");
    } catch (e) {
      alert(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const runBackup = async () => {
    if (!window.confirm("Run a new backup now?")) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/api/backups/run`, { method: "POST" });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || "Backup failed");
      }
      await loadList();
      alert("Backup completed.");
    } catch (e) {
      alert(e.message || "Backup failed");
    } finally {
      setBusy(false);
    }
  };

  const restore = async (name) => {
    const dest = destRestore.trim() || undefined;
    if (!window.confirm(`Restore "${name}" ${dest ? `to ${dest}` : "to source path"}?`)) return;
    setBusy(true);
    try {
      const params = new URLSearchParams();
      params.set("name", name);
      if (dest) params.set("dest", dest);
      const r = await fetch(`${API_BASE}/api/backups/restore?${params.toString()}`, {
        method: "POST",
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || "Restore failed");
      }
      alert("Restore completed.");
    } catch (e) {
      alert(e.message || "Restore failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (name) => {
    if (!window.confirm(`Delete backup "${name}"?`)) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/api/backups/${encodeURIComponent(name)}`, { method: "DELETE" });
      if (!r.ok) throw new Error("Delete failed");
      await loadList();
    } catch (e) {
      alert(e.message || "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const download = (name) => {
    window.location.href = `${API_BASE}/api/backups/download/${encodeURIComponent(name)}`;
  };

  return (
    <div className="bk-wrap">
      <div className="bk-header">
        <div>
          <h2 className="bk-title">Backups</h2>
          <p className="bk-sub">One-click ZIP backups with retention & size caps.</p>
        </div>
        <div className="bk-actions">
          <button className="btn primary" onClick={runBackup} disabled={busy || loading}>
            {busy ? "Working..." : "Run Backup"}
          </button>
        </div>
      </div>

      {/* Settings */}
      <section className="card">
        <h3 className="card-title">Settings</h3>
        <form className="bk-grid" onSubmit={onSave}>
          <label className="field">
            <span className="label">Source Path</span>
            <input
              value={settings.source_path}
              onChange={(e) => setSettings({ ...settings, source_path: e.target.value })}
              placeholder="Folder to back up (e.g., C:\Users\you\Downloads)"
            />
          </label>

          <label className="field">
            <span className="label">Backup Location</span>
            <input
              value={settings.backup_dir}
              onChange={(e) => setSettings({ ...settings, backup_dir: e.target.value })}
              placeholder="Where to store backup zips"
            />
          </label>

          <label className="field">
            <span className="label">Retention Count</span>
            <input
              type="number"
              min={1}
              value={settings.retention_count}
              onChange={(e) => setSettings({ ...settings, retention_count: Number(e.target.value) })}
            />
          </label>

          <label className="field">
            <span className="label">Max Total Size (GB)</span>
            <input
              type="number"
              step="0.1"
              min="0.1"
              value={settings.max_total_gb}
              onChange={(e) => setSettings({ ...settings, max_total_gb: Number(e.target.value) })}
            />
          </label>

          <div className="field">
            <span className="label">Restore Destination (optional)</span>
            <input
              value={destRestore}
              onChange={(e) => setDestRestore(e.target.value)}
              placeholder="Leave empty to restore back to Source Path"
            />
          </div>

          <div className="form-actions">
            <button className="btn primary" type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save Settings"}
            </button>
          </div>
        </form>
      </section>

      {/* List */}
      <section className="card">
        <h3 className="card-title">Existing Backups</h3>
        <div className="table-wrap">
          <table className="bk-table">
            <thead>
              <tr>
                <th style={{width: "30%"}}>Name</th>
                <th>Size</th>
                <th>Created</th>
                <th style={{width: "260px"}}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={4} className="empty">No backups yet.</td></tr>
              ) : items.map((it) => (
                <tr key={it.name}>
                  <td>{it.name}</td>
                  <td>{it.size_human}</td>
                  <td>{fmtTime(it.timestamp)}</td>
                  <td className="row-actions">
                    <button className="btn" onClick={() => download(it.name)}>Download</button>
                    <button className="btn" onClick={() => restore(it.name)} disabled={busy}>Restore</button>
                    <button className="btn danger" onClick={() => remove(it.name)} disabled={busy}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
