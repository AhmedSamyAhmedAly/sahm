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

export default function AdminUsers() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", first_name: "", last_name: "", mobile: "" });

  const load = () => {
    api.adminStats().then(setStats).catch((e) => setErr(e.message));
    api.adminUsers().then(setUsers).catch((e) => setErr(e.message));
  };
  useEffect(load, []);

  const wrap = async (fn) => {
    setErr(""); setBusy(true);
    try { await fn(); load(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const addUser = (e) => {
    e.preventDefault();
    wrap(async () => {
      await api.adminCreateUser({ ...form });
      setForm({ email: "", password: "", first_name: "", last_name: "", mobile: "" });
    });
  };

  const resetPw = (u) => {
    const pw = window.prompt(`New password for ${u.email} (min 8 chars):`);
    if (pw) wrap(() => api.adminUpdateUser(u.id, { password: pw }));
  };
  const toggleActive = (u) => wrap(() => api.adminUpdateUser(u.id, { is_active: !u.is_active }));
  const toggleRole = (u) => wrap(() => api.adminUpdateUser(u.id, { role: u.role === "admin" ? "member" : "admin" }));
  const del = (u) => {
    if (window.confirm(`Delete ${u.email}? This cannot be undone.`))
      wrap(() => api.adminDeleteUser(u.id));
  };

  const fmt = (d) => (d ? new Date(d).toLocaleDateString() : "—");
  const isAdminAcct = (u) => u.role === "admin";
  const nameOf = (u) => [u.first_name, u.last_name].filter(Boolean).join(" ") || "—";

  return (
    <div className="container">
      <h2 style={{ marginTop: 0 }}>Users</h2>
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
          <div className="field" style={{ marginBottom: 0, flex: "1 1 140px" }}>
            <label>First name</label>
            <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 140px" }}>
            <label>Last name</label>
            <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
            <label>Email</label>
            <input type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 150px" }}>
            <label>Mobile</label>
            <input type="tel" placeholder="+20…" value={form.mobile}
              onChange={(e) => setForm({ ...form, mobile: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 160px" }}>
            <label>Temp password (min 8)</label>
            <input type="text" required minLength={8} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy}>
            Add user
          </button>
        </form>
        <p style={{ color: "var(--muted)", fontSize: 12, marginBottom: 0 }}>
          New accounts are always <b>members</b>. Only <b>{user?.email}</b> is admin. Self-serve
          registration is a future phase — for now you set members up here.
        </p>
      </div>

      <div className="section-title">All users</div>
      <div className="card" style={{ overflowX: "auto" }}>
        <table className="responsive">
          <thead>
            <tr>
              <th>Name</th><th>Email</th><th>Mobile</th><th>Role</th><th>Status</th>
              <th>Last login</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} style={{ cursor: "default" }}>
                <td className="tickercell" data-label="Name">{nameOf(u)}</td>
                <td data-label="Email">{u.email}</td>
                <td data-label="Mobile">{u.mobile || "—"}</td>
                <td data-label="Role">
                  <span className={`badge ${isAdminAcct(u) ? "strong_buy" : "buy"}`}>
                    {u.role.toUpperCase()}
                  </span>
                </td>
                <td data-label="Status">{u.is_active ? <span className="up">active</span> : <span className="down">suspended</span>}</td>
                <td data-label="Last login">{fmt(u.last_login_at)}</td>
                <td data-label="Actions">
                  {u.is_primary ? (
                    <span className="pill">primary admin</span>
                  ) : u.email === user?.email ? (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                      <button className="iconbtn" disabled={busy} onClick={() => resetPw(u)}>Reset PW</button>
                      <span className="pill">you</span>
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button className="iconbtn" disabled={busy} onClick={() => resetPw(u)}>Reset PW</button>
                      <button className="iconbtn" disabled={busy} onClick={() => toggleRole(u)}>
                        {u.role === "admin" ? "Remove admin" : "Make admin"}
                      </button>
                      <button className="iconbtn" disabled={busy} onClick={() => toggleActive(u)}>
                        {u.is_active ? "Suspend" : "Activate"}
                      </button>
                      <button className="iconbtn" disabled={busy} onClick={() => del(u)}
                        style={{ color: "var(--red)", borderColor: "var(--red)" }}>Delete</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="disclaimer">
        Only the <b>primary admin</b> (pinned by email) is protected; other admins you grant can be
        managed here. Roles, suspensions and deletes are enforced server-side.
      </p>
    </div>
  );
}
