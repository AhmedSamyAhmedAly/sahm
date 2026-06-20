import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

function Kpi({ label, value }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

export default function Admin() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", role: "member" });

  const load = () => {
    api.adminStats().then(setStats).catch((e) => setErr(e.message));
    api.adminUsers().then(setUsers).catch((e) => setErr(e.message));
    api.adminMessages().then(setMessages).catch(() => {});
  };
  useEffect(load, []);

  const wrap = async (fn) => {
    setErr("");
    setBusy(true);
    try {
      await fn();
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const addUser = (e) => {
    e.preventDefault();
    wrap(async () => {
      await api.adminCreateUser(form.email, form.password, form.role);
      setForm({ email: "", password: "", role: "member" });
    });
  };

  const resetPw = (u) => {
    const pw = window.prompt(`New password for ${u.email} (min 8 chars):`);
    if (pw) wrap(() => api.adminUpdateUser(u.id, { password: pw }));
  };
  const toggleActive = (u) =>
    wrap(() => api.adminUpdateUser(u.id, { is_active: !u.is_active }));
  const toggleRole = (u) =>
    wrap(() => api.adminUpdateUser(u.id, { role: u.role === "admin" ? "member" : "admin" }));
  const resolveMsg = (m) => wrap(() => api.resolveMessage(m.id));
  const del = (u) => {
    if (window.confirm(`Delete ${u.email}? This cannot be undone.`))
      wrap(() => api.adminDeleteUser(u.id));
  };

  const fmt = (d) => (d ? new Date(d).toLocaleDateString() : "—");
  const isAdminAcct = (u) => u.role === "admin";

  return (
    <div className="container">
      <h2 style={{ marginTop: 0 }}>Admin</h2>
      {err && <div className="error">{err}</div>}

      {stats && (
        <div className="kpis">
          <Kpi label="Total users" value={stats.total_users} />
          <Kpi label="Active" value={stats.active_users} />
          <Kpi label="Logins (7d)" value={stats.logins_last_7d} />
          <Kpi label="Last scan" value={stats.last_scan_date || "—"} />
        </div>
      )}

      <div className="section-title">Add a member</div>
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        <form onSubmit={addUser} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 220px" }}>
            <label>Email</label>
            <input type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 180px" }}>
            <label>Temp password (min 8)</label>
            <input type="text" required minLength={8} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy}>
            Add user
          </button>
        </form>
        <p style={{ color: "var(--muted)", fontSize: 12, marginBottom: 0 }}>
          New accounts are always <b>members</b>. Only <b>{user?.email}</b> is admin.
        </p>
      </div>

      <div className="section-title">Users</div>
      <div className="card" style={{ overflowX: "auto" }}>
        <table className="responsive">
          <thead>
            <tr>
              <th>Email</th><th>Role</th><th>Status</th><th>Created</th>
              <th>Last login</th><th className="num">Watchlist</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} style={{ cursor: "default" }}>
                <td className="tickercell" data-label="Email">{u.email}</td>
                <td data-label="Role">
                  <span className={`badge ${isAdminAcct(u) ? "strong_buy" : "buy"}`}>
                    {u.role.toUpperCase()}
                  </span>
                </td>
                <td data-label="Status">{u.is_active ? <span className="up">active</span> : <span className="down">suspended</span>}</td>
                <td data-label="Created">{fmt(u.created_at)}</td>
                <td data-label="Last login">{fmt(u.last_login_at)}</td>
                <td className="num" data-label="Watchlist">{u.watchlist_count}</td>
                <td data-label="Actions">
                  {u.is_primary ? (
                    <span className="pill">primary admin</span>
                  ) : u.email === user?.email ? (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                      <button className="ghost" disabled={busy} onClick={() => resetPw(u)}>Reset PW</button>
                      <span className="pill">you</span>
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button className="ghost" disabled={busy} onClick={() => resetPw(u)}>Reset PW</button>
                      <button className="ghost" disabled={busy} onClick={() => toggleRole(u)}>
                        {u.role === "admin" ? "Remove admin" : "Make admin"}
                      </button>
                      <button className="ghost" disabled={busy} onClick={() => toggleActive(u)}>
                        {u.is_active ? "Suspend" : "Activate"}
                      </button>
                      <button className="ghost" disabled={busy} onClick={() => del(u)}
                        style={{ color: "var(--red)", borderColor: "var(--red)" }}>Delete</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-title">Messages</div>
      <div className="card" style={{ padding: 16 }}>
        {messages.length === 0 && <p style={{ color: "var(--muted)", margin: 0 }}>No messages yet.</p>}
        {messages.map((m) => (
          <div key={m.id} style={{ borderBottom: "1px solid var(--border)", padding: "12px 0" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <b>{m.title}</b>
              {m.resolved && <span className="pill" style={{ color: "var(--green)" }}>resolved</span>}
              <span style={{ color: "var(--muted)", fontSize: 12 }}>
                {m.email}{m.created_at ? ` · ${new Date(m.created_at).toLocaleString()}` : ""}
              </span>
              <div style={{ flex: 1 }} />
              <button className="ghost" disabled={busy} onClick={() => resolveMsg(m)}>
                {m.resolved ? "Reopen" : "Resolve"}
              </button>
            </div>
            {m.description && <p style={{ margin: "6px 0", whiteSpace: "pre-wrap" }}>{m.description}</p>}
            {m.attachments?.length > 0 && (
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                {m.attachments.map((a, i) => (
                  <a key={i} className="link" download={a.name}
                    href={`data:${a.type || "application/octet-stream"};base64,${a.data}`}>📎 {a.name}</a>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <p className="disclaimer">
        Only the <b>primary admin</b> (pinned by email) is protected; other admins you grant can be
        managed here. Roles, suspensions and deletes are enforced server-side.
      </p>
    </div>
  );
}
