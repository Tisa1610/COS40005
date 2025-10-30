import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Incidents.css";

const API_BASE = (process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000").replace(/\/$/,"");

// ---------- helpers ----------
const LVL = ["INFO","WARNING","ERROR","CRITICAL"];
const STAT = ["open","investigating","contained","monitoring","closed"];

const emptyForm = {
  title: "",
  description: "",
  severity: "WARNING",
  assignee: "",
  tags: "",
};

function fmt(ts) {
  try { const d=new Date(ts); if (!isNaN(d)) return d.toLocaleString(); } catch {}
  return ts || "—";
}

function clsBadge(sev) {
  const s = String(sev||"INFO").toUpperCase();
  return `badge ${s.toLowerCase()}`;
}

export default function Incidents() {
  const nav = useNavigate();

  // data
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  // filters
  const [q, setQ] = useState("");
  const [sev, setSev] = useState("ALL");
  const [status, setStatus] = useState("ALL");

  // create modal
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);

  // detail drawer
  const [openId, setOpenId] = useState(null);
  const openItem = useMemo(() => items.find(x=>x.id===openId) || null, [items, openId]);

  // initial + poll
  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/incidents`, { cache: "no-store" });
        if (!alive) return;
        if (!r.ok) throw new Error(`GET ${r.status}`);
        const data = await r.json();
        setItems(Array.isArray(data) ? data : []);
        setErr(null);
      } catch (e) {
        if (!alive) return;
        setErr("Could not load incidents");
      } finally {
        if (alive) setLoading(false);
      }
    };
    pull();
    const t = setInterval(pull, 8000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  // filters
  const filtered = useMemo(() => {
    const qq = q.trim().toLowerCase();
    return items.filter(it => {
      if (sev !== "ALL" && String(it.severity).toUpperCase() !== sev) return false;
      if (status !== "ALL" && String(it.status).toLowerCase() !== status) return false;
      if (!qq) return true;
      const hay = `${it.title} ${it.description} ${it.assignee} ${it.tags?.join(" ")||""}`.toLowerCase();
      return hay.includes(qq);
    });
  }, [items, q, sev, status]);

  // actions
  const createIncident = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      const body = {
        title: form.title.trim(),
        description: form.description.trim(),
        severity: form.severity,
        assignee: form.assignee.trim() || null,
        tags: form.tags ? form.tags.split(",").map(s=>s.trim()).filter(Boolean) : [],
      };
      const r = await fetch(`${API_BASE}/api/incidents`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`POST ${r.status}`);
      const inc = await r.json();
      setItems(prev => [inc, ...prev]);
      setShowNew(false);
      setForm(emptyForm);
      setOpenId(inc.id);
    } catch (e) {
      alert("Failed to create incident");
    } finally {
      setCreating(false);
    }
  };

  const patchIncident = async (iid, patch) => {
    // optimistic
    setItems(prev => prev.map(x => x.id===iid ? {...x, ...patch, updated_at:new Date().toISOString()} : x));
    try {
      const r = await fetch(`${API_BASE}/api/incidents/${iid}`, {
        method: "PATCH",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(patch),
      });
      if (!r.ok) throw new Error(`PATCH ${r.status}`);
      const up = await r.json();
      setItems(prev => prev.map(x => x.id===iid ? up : x));
    } catch (e) {
      alert("Update failed — reverted.");
      // refresh
      const r = await fetch(`${API_BASE}/api/incidents`);
      setItems(await r.json());
    }
  };

  const addNote = async (iid, text, author="savindu") => {
    if (!text.trim()) return;
    try {
      const r = await fetch(`${API_BASE}/api/incidents/${iid}/note`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ author, text }),
      });
      if (!r.ok) throw new Error(`NOTE ${r.status}`);
      const up = await r.json();
      setItems(prev => prev.map(x => x.id===iid ? up : x));
    } catch {
      alert("Failed to add note");
    }
  };

  const closeIncident = async (iid) => {
    // optimistic
    setItems(prev => prev.map(x => x.id===iid ? {...x, status:"closed", closed_at:new Date().toISOString()} : x));
    try {
      const r = await fetch(`${API_BASE}/api/incidents/${iid}/close`, { method:"POST" });
      if (!r.ok) throw new Error(`CLOSE ${r.status}`);
      const up = await r.json();
      setItems(prev => prev.map(x => x.id===iid ? up : x));
    } catch {
      alert("Close failed");
    }
  };

  return (
    <div className="inc-wrap">
      <main className="inc-main">
        {/* Header */}
        <div className="inc-header">
          <div>
            <h1 className="inc-title">Incidents</h1>
            <p className="inc-sub">Create, triage, and track incident response.</p>
          </div>
          <div className="header-actions">
            <button className="btn primary" onClick={()=>setShowNew(true)}>New Incident</button>
            <Link className="btn ghost" to="/compliance-logs">Compliance Logs</Link>
          </div>
        </div>

        {/* Filters */}
        <div className="filters card">
          <div className="field">
            <span className="label">Severity</span>
            <select value={sev} onChange={e=>setSev(e.target.value)}>
              <option value="ALL">All</option>
              {LVL.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
          <div className="field">
            <span className="label">Status</span>
            <select value={status} onChange={e=>setStatus(e.target.value)}>
              <option value="ALL">All</option>
              {STAT.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="field grow">
            <span className="label">Search</span>
            <input placeholder="title, desc, assignee, tag…" value={q} onChange={e=>setQ(e.target.value)} />
          </div>
        </div>

        {/* Table */}
        <div className="card table-card">
          {err && <div className="error">{err}</div>}
          <div className="table-wrap">
            <table className="inc-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Severity</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Assignee</th>
                  <th>Tags</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="9">Loading…</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan="9">No incidents match your filters.</td></tr>
                ) : (
                  filtered.map(row => (
                    <tr key={row.id} className={`row-${String(row.severity||"info").toLowerCase()}`}>
                      <td>#{row.id}</td>
                      <td><span className={clsBadge(row.severity)}>{String(row.severity).toUpperCase()}</span></td>
                      <td className="title-cell">
                        <button className="linklike" onClick={()=>setOpenId(row.id)}>{row.title}</button>
                        {row.description ? <div className="muted small">{row.description.slice(0,120)}</div> : null}
                      </td>
                      <td>
                        <select
                          className="mini-select"
                          value={row.status}
                          onChange={e=>patchIncident(row.id, {status:e.target.value})}
                        >
                          {STAT.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td>
                        <input
                          className="mini-input"
                          value={row.assignee || ""}
                          onChange={e=>patchIncident(row.id, {assignee:e.target.value||null})}
                          placeholder="—"
                        />
                      </td>
                      <td className="tags">
                        {(row.tags||[]).map(t => <span key={t} className="tag">{t}</span>)}
                      </td>
                      <td>{fmt(row.created_at)}</td>
                      <td>{fmt(row.updated_at)}</td>
                      <td className="actions">
                        {row.status !== "closed" ? (
                          <button className="btn small" onClick={()=>closeIncident(row.id)}>Close</button>
                        ) : <span className="muted">Closed</span>}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Drawer (details) */}
        {openItem && (
          <div className="drawer">
            <div className="drawer-card">
              <div className="drawer-head">
                <div>
                  <div className="drawer-id">Incident #{openItem.id}</div>
                  <div className="drawer-title">{openItem.title}</div>
                </div>
                <button className="btn" onClick={()=>setOpenId(null)}>Close</button>
              </div>

              <div className="drawer-meta">
                <span className={clsBadge(openItem.severity)}>{openItem.severity}</span>
                <span className="chip">{openItem.status}</span>
                <span className="chip">Assignee: {openItem.assignee || "—"}</span>
                <span className="chip">Created: {fmt(openItem.created_at)}</span>
                <span className="chip">Updated: {fmt(openItem.updated_at)}</span>
              </div>

              {openItem.description && (
                <div className="drawer-section">
                  <div className="section-title">Description</div>
                  <p className="desc">{openItem.description}</p>
                </div>
              )}

              <div className="drawer-grid">
                <div className="drawer-section">
                  <div className="section-title">Notes</div>
                  <NoteList
                    items={openItem.notes || []}
                    onAdd={(text)=>addNote(openItem.id, text)}
                  />
                </div>

                <div className="drawer-section">
                  <div className="section-title">Artifacts</div>
                  <ArtifactList items={openItem.artifacts || []}/>
                </div>

                <div className="drawer-section">
                  <div className="section-title">Timeline</div>
                  <TimelineList items={openItem.timeline || []}/>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* New incident modal */}
        {showNew && (
          <div className="modal">
            <div className="modal-card">
              <div className="modal-head">
                <div className="modal-title">New Incident</div>
                <button className="btn" onClick={()=>setShowNew(false)}>Close</button>
              </div>
              <form onSubmit={createIncident} className="form-grid">
                <label className="f">
                  <span className="l">Title</span>
                  <input
                    required
                    value={form.title}
                    onChange={e=>setForm({...form, title:e.target.value})}
                    placeholder="e.g., Ransomware indicators on HOST-01"
                  />
                </label>
                <label className="f">
                  <span className="l">Severity</span>
                  <select
                    value={form.severity}
                    onChange={e=>setForm({...form, severity:e.target.value})}
                  >
                    {LVL.map(l => <option key={l} value={l}>{l}</option>)}
                  </select>
                </label>
                <label className="f">
                  <span className="l">Assignee</span>
                  <input
                    value={form.assignee}
                    onChange={e=>setForm({...form, assignee:e.target.value})}
                    placeholder="e.g., savindu"
                  />
                </label>
                <label className="f f-col">
                  <span className="l">Description</span>
                  <textarea
                    rows={4}
                    value={form.description}
                    onChange={e=>setForm({...form, description:e.target.value})}
                    placeholder="What happened? Early hypothesis, scope, affected host(s)…"
                  />
                </label>
                <label className="f">
                  <span className="l">Tags (comma-separated)</span>
                  <input
                    value={form.tags}
                    onChange={e=>setForm({...form, tags:e.target.value})}
                    placeholder="ransomware, host-01"
                  />
                </label>
                <div className="modal-actions">
                  <button type="button" className="btn" onClick={()=>setShowNew(false)}>Cancel</button>
                  <button type="submit" className="btn primary" disabled={creating}>
                    {creating ? "Creating…" : "Create Incident"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

/* ------------- subcomponents ------------- */

function NoteList({ items, onAdd }) {
  const [txt, setTxt] = useState("");
  return (
    <div className="notes">
      <ul className="notes-list">
        {items.length === 0 ? <li className="muted small">No notes yet.</li> :
          items.slice().reverse().map(n => (
            <li key={n.id}>
              <div className="note-top">
                <span className="author">{n.author || "—"}</span>
                <span className="time">{fmt(n.at)}</span>
              </div>
              <div className="note-text">{n.text}</div>
            </li>
          ))
        }
      </ul>
      <div className="note-add">
        <input
          value={txt}
          onChange={e=>setTxt(e.target.value)}
          placeholder="Add a note…"
          onKeyDown={e=>{ if(e.key==="Enter"){ onAdd(txt); setTxt(""); } }}
        />
        <button className="btn small" onClick={()=>{ onAdd(txt); setTxt(""); }}>Add</button>
      </div>
    </div>
  );
}

function ArtifactList({ items }) {
  if (!items.length) return <div className="muted small">No artifacts linked.</div>;
  return (
    <ul className="artifacts">
      {items.map((a, i)=>(
        <li key={i}>
          <span className="kind">{a.kind}:</span> <span className="val">{String(a.value)}</span>
        </li>
      ))}
    </ul>
  );
}

function TimelineList({ items }) {
  if (!items.length) return <div className="muted small">No timeline events yet.</div>;
  return (
    <ul className="timeline">
      {items.slice().reverse().map(ev => (
        <li key={ev.id}>
          <span className="time">{fmt(ev.at)}</span>
          <span className="t">{ev.type}</span>
          <span className="d">{JSON.stringify(ev.details)}</span>
        </li>
      ))}
    </ul>
  );
}

