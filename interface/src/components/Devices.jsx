// src/components/Devices.jsx
import React, { useEffect, useMemo, useState } from "react";
import "./Devices.css";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";
// Expected backend (once ready):
// GET    /api/devices?status=&q=&page=&size=
// POST   /api/devices
// GET    /api/devices/:id
// PATCH  /api/devices/:id
// DELETE /api/devices/:id
// POST   /api/devices/:id/actions  { type: "quarantine|unquarantine|reload_config" }

export default function Devices() {
  const [loading, setLoading] = useState(true);
  const [devices, setDevices] = useState([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(8);

  // Drawer / modal state
  const [selected, setSelected] = useState(null);
  const [edit, setEdit] = useState(null);       // mutable copy of selected for editing
  const [showAdd, setShowAdd] = useState(false);
  const [newDev, setNewDev] = useState({
    hostname: "",
    role: "agent",
    tags: "",
  });

  // ---------- Fetch devices ----------
  useEffect(() => {
    let alive = true;

    const mock = [
      {
        id: "dev-001",
        hostname: "PLC-CELL-A",
        role: "agent",
        status: "online",
        last_seen: new Date().toISOString(),
        watch_paths: ["C:\\Users\\Public", "C:\\ProgramData"],
        ext_watchlist: [".lockbit", ".conti", ".encrypted"],
        cpu_threshold: 85,
        io_write_threshold_bytes: 104857600,
        tags: ["OT", "Cell-A"],
      },
      {
        id: "dev-002",
        hostname: "HMI-01",
        role: "gateway",
        status: "degraded",
        last_seen: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
        watch_paths: ["C:\\Users\\Public"],
        ext_watchlist: [".ryk", ".lkr"],
        cpu_threshold: 80,
        io_write_threshold_bytes: 52428800,
        tags: ["HMI"],
      },
      {
        id: "dev-003",
        hostname: "HISTORIAN-SRV",
        role: "sensor",
        status: "offline",
        last_seen: new Date(Date.now() - 1000 * 60 * 65).toISOString(),
        watch_paths: ["D:\\Logs"],
        ext_watchlist: [".wnry", ".wcry"],
        cpu_threshold: 90,
        io_write_threshold_bytes: 157286400,
        tags: ["Historian", "DMZ"],
      },
    ];

    async function load() {
      setLoading(true);
      try {
        // Uncomment when backend is ready:
        // const res = await fetch(`${API_BASE}/api/devices`);
        // if (!res.ok) throw new Error(`devices ${res.status}`);
        // const data = await res.json();
        const data = mock;
        if (!alive) return;
        setDevices(data);
      } catch (e) {
        console.error(e);
        toast.error("Failed to load devices (showing mock data).");
        if (!alive) return;
        setDevices(mock);
      } finally {
        if (alive) setLoading(false);
      }
    }

    load();
    const id = setInterval(load, 15000); // gentle refresh
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // ---------- Filters + pagination ----------
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return devices.filter((d) => {
      const sOk = status === "ALL" ? true : d.status === status.toLowerCase();
      if (!sOk) return false;
      if (!q) return true;
      return (
        d.hostname.toLowerCase().includes(q) ||
        (d.id || "").toLowerCase().includes(q) ||
        (d.tags || []).join(",").toLowerCase().includes(q)
      );
    });
  }, [devices, query, status]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);

  useEffect(() => {
    if (page > totalPages) setPage(1);
  }, [totalPages, page]);

  // ---------- Helpers ----------
  const badge = (s) =>
    `d-badge ${s === "online" ? "ok" : s === "degraded" ? "warn" : "err"}`;

  const prettyBytes = (n) => {
    if (!n && n !== 0) return "—";
    if (n < 1024) return `${n} B/s`;
    if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB/s`;
    if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB/s`;
    return `${(n / 1024 ** 3).toFixed(1)} GB/s`;
  };

  // ---------- Actions (wire later) ----------
  const doAction = async (id, type) => {
    try {
      // await fetch(`${API_BASE}/api/devices/${id}/actions`, {
      //   method: "POST",
      //   headers: { "Content-Type": "application/json" },
      //   body: JSON.stringify({ type }),
      // });
      toast.success(`${type} requested for ${id}`);
    } catch {
      toast.error(`Failed to ${type}`);
    }
  };

  const saveEdit = async () => {
    try {
      // await fetch(`${API_BASE}/api/devices/${edit.id}`, {
      //   method: "PATCH",
      //   headers: { "Content-Type": "application/json" },
      //   body: JSON.stringify({
      //     cpu_threshold: Number(edit.cpu_threshold) || 0,
      //     io_write_threshold_bytes: Number(edit.io_write_threshold_bytes) || 0,
      //     watch_paths: edit.watch_paths,
      //     ext_watchlist: edit.ext_watchlist,
      //   }),
      // });
      // optimistic UI
      setDevices((prev) =>
        prev.map((d) => (d.id === edit.id ? { ...d, ...edit } : d))
      );
      toast.success("Device updated");
      setSelected(edit);
      setEdit(null);
    } catch {
      toast.error("Failed to update device");
    }
  };

  const removeDevice = async (id) => {
    if (!window.confirm("Remove this device?")) return;
    try {
      // await fetch(`${API_BASE}/api/devices/${id}`, { method: "DELETE" });
      setDevices((prev) => prev.filter((d) => d.id !== id));
      toast.success("Device removed");
    } catch {
      toast.error("Failed to remove device");
    }
  };

  const addDevice = async () => {
    if (!newDev.hostname.trim()) {
      toast.info("Hostname is required");
      return;
    }
    try {
      // const res = await fetch(`${API_BASE}/api/devices`, {
      //   method: "POST",
      //   headers: { "Content-Type": "application/json" },
      //   body: JSON.stringify({
      //     hostname: newDev.hostname.trim(),
      //     role: newDev.role,
      //     tags: newDev.tags
      //       .split(",")
      //       .map((t) => t.trim())
      //       .filter(Boolean),
      //   }),
      // });
      // const created = await res.json();
      const created = {
        id: `dev-${Math.random().toString(36).slice(2, 7)}`,
        hostname: newDev.hostname.trim(),
        role: newDev.role,
        status: "online",
        last_seen: new Date().toISOString(),
        watch_paths: [],
        ext_watchlist: [],
        cpu_threshold: 85,
        io_write_threshold_bytes: 104857600,
        tags: newDev.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      };
      setDevices((p) => [created, ...p]);
      setShowAdd(false);
      setNewDev({ hostname: "", role: "agent", tags: "" });
      toast.success("Device added");
    } catch {
      toast.error("Failed to add device");
    }
  };

  const openDrawer = (d) => {
    setSelected(d);
    setEdit({ ...d });
  };

  const closeDrawer = () => {
    setSelected(null);
    setEdit(null);
  };

  // ---------- UI ----------
  return (
    <div className="devices-wrap">
      <main className="devices-main">
        <div className="dv-header">
          <div>
            <h1 className="dv-title">Devices</h1>
            <p className="dv-sub">Inventory, health and enforcement controls</p>
          </div>
          <div className="dv-actions">
            <button className="btn primary" onClick={() => setShowAdd(true)}>
              Add Device
            </button>
          </div>
        </div>

        {/* Filters */}
        <section className="dv-filters">
          <label className="dv-field grow">
            <span>Search</span>
            <input
              placeholder="hostname, id, tags…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>

          <label className="dv-field">
            <span>Status</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="ALL">All</option>
              <option value="online">Online</option>
              <option value="degraded">Degraded</option>
              <option value="offline">Offline</option>
            </select>
          </label>

          <div className="dv-count">{filtered.length} devices</div>
        </section>

        {/* Table */}
        <section className="dv-card">
          {loading ? (
            <div className="dv-loading">Loading devices…</div>
          ) : filtered.length === 0 ? (
            <div className="dv-empty">No matching devices.</div>
          ) : (
            <>
              <div className="table-scroll">
                <table className="dv-table">
                  <thead>
                    <tr>
                      <th>Device</th>
                      <th>Status</th>
                      <th>Role</th>
                      <th>Last Seen</th>
                      <th>CPU Threshold</th>
                      <th>IO Threshold</th>
                      <th>Tags</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((d) => (
                      <tr key={d.id}>
                        <td>
                          <div className="cell-main">
                            <div className="cell-title">{d.hostname}</div>
                            <div className="cell-sub">{d.id}</div>
                          </div>
                        </td>
                        <td><span className={badge(d.status)}>{d.status}</span></td>
                        <td className="muted">{d.role}</td>
                        <td className="muted">
                          {new Date(d.last_seen).toLocaleString()}
                        </td>
                        <td>{d.cpu_threshold}%</td>
                        <td>{prettyBytes(d.io_write_threshold_bytes)}</td>
                        <td className="muted">{(d.tags || []).join(", ") || "—"}</td>
                        <td className="row-actions">
                          <button className="btn small" onClick={() => openDrawer(d)}>View</button>
                          <button className="btn small" onClick={() => doAction(d.id, d.status === "online" ? "quarantine" : "unquarantine")}>
                            {d.status === "online" ? "Quarantine" : "Unquarantine"}
                          </button>
                          <button className="btn small" onClick={() => doAction(d.id, "reload_config")}>Reload</button>
                          <button className="btn small danger" onClick={() => removeDevice(d.id)}>Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="pagination">
                <button className="btn small" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Prev</button>
                <div className="pg-num">
                  Page {page} of {totalPages}
                </div>
                <button className="btn small" disabled={page === totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Next</button>
              </div>
            </>
          )}
        </section>

        {/* Drawer */}
        {selected && (
          <div className="drawer">
            <div className="drawer-panel">
              <div className="drawer-head">
                <div>
                  <div className="drawer-title">{selected.hostname}</div>
                  <div className="drawer-sub">{selected.id}</div>
                </div>
                <button className="btn" onClick={closeDrawer}>Close</button>
              </div>

              <div className="drawer-body">
                <div className="drawer-grid">
                  <label className="dv-field">
                    <span>CPU Threshold (%)</span>
                    <input
                      type="number"
                      value={edit.cpu_threshold}
                      onChange={(e) => setEdit({ ...edit, cpu_threshold: e.target.value })}
                    />
                  </label>
                  <label className="dv-field">
                    <span>IO Threshold (bytes/sec)</span>
                    <input
                      type="number"
                      value={edit.io_write_threshold_bytes}
                      onChange={(e) =>
                        setEdit({
                          ...edit,
                          io_write_threshold_bytes: e.target.value,
                        })
                      }
                    />
                  </label>
                </div>

                <label className="dv-field">
                  <span>Watch Paths</span>
                  <TagEditor
                    value={edit.watch_paths || []}
                    onChange={(v) => setEdit({ ...edit, watch_paths: v })}
                    placeholder="e.g. C:\Users\Public"
                  />
                </label>

                <label className="dv-field">
                  <span>Extension Watchlist</span>
                  <TagEditor
                    value={edit.ext_watchlist || []}
                    onChange={(v) => setEdit({ ...edit, ext_watchlist: v })}
                    placeholder="e.g. .lockbit"
                  />
                </label>

                <div className="drawer-actions">
                  <button className="btn" onClick={() => doAction(edit.id, "reload_config")}>Reload Config</button>
                  <button className="btn primary" onClick={saveEdit}>Save Changes</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Add Device modal */}
        {showAdd && (
          <div className="modal">
            <div className="modal-card">
              <div className="modal-head">
                <div className="modal-title">Add Device</div>
                <button className="btn" onClick={() => setShowAdd(false)}>Close</button>
              </div>
              <div className="modal-body">
                <label className="dv-field">
                  <span>Hostname</span>
                  <input
                    value={newDev.hostname}
                    onChange={(e) => setNewDev({ ...newDev, hostname: e.target.value })}
                  />
                </label>
                <label className="dv-field">
                  <span>Role</span>
                  <select
                    value={newDev.role}
                    onChange={(e) => setNewDev({ ...newDev, role: e.target.value })}
                  >
                    <option value="agent">agent</option>
                    <option value="gateway">gateway</option>
                    <option value="sensor">sensor</option>
                  </select>
                </label>
                <label className="dv-field">
                  <span>Tags (comma-separated)</span>
                  <input
                    value={newDev.tags}
                    onChange={(e) => setNewDev({ ...newDev, tags: e.target.value })}
                    placeholder="OT, Cell-A"
                  />
                </label>
              </div>
              <div className="modal-actions">
                <button className="btn primary" onClick={addDevice}>Create</button>
              </div>
            </div>
          </div>
        )}

        <ToastContainer position="bottom-right" />
      </main>
    </div>
  );
}

// -------- Small tag editor (chips) ----------
function TagEditor({ value, onChange, placeholder }) {
  const [text, setText] = useState("");

  const add = () => {
    const t = text.trim();
    if (!t) return;
    onChange([...(value || []), t]);
    setText("");
  };
  const remove = (i) => {
    const next = [...value];
    next.splice(i, 1);
    onChange(next);
  };

  return (
    <div className="tag-editor">
      <div className="tags">
        {(value || []).map((v, i) => (
          <span key={`${v}-${i}`} className="chip">
            {v}
            <button className="chip-x" type="button" onClick={() => remove(i)}>×</button>
          </span>
        ))}
      </div>
      <div className="tag-input-row">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder || "Add value"}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
        />
        <button className="btn small" type="button" onClick={add}>Add</button>
      </div>
    </div>
  );
}
