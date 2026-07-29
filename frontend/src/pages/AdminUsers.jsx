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
  const [form, setForm] = useState({ email: "", password: "" });

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
      setForm({ email: "", password: "" });
    });
  };

  const resetPw = (u) => {
    const pw = window.prompt(`New password for ${u.email} (min 8 chars):`);
    if (pw) wrap(() => api.adminUpdateUser(u.id, { password: pw }));
  };
  const toggleActive = (u) => wrap(() => api.adminUpdateUser(u.id, { is_active: !u.is_active }));
  // Cycle member -> staff -> admin -> member. staff = full access, never pays,
  // but no admin panel.
  const NEXT_ROLE = { member: "staff", staff: "admin", admin: "member" };
  const cycleRole = (u) => wrap(() => api.adminUpdateUser(u.id, { role: NEXT_ROLE[u.role] || "member" }));

  // Give / extend / revoke a plan without payment.
  const grant = (u) => {
    const plan = window.prompt(
      `Plan for ${u.email} — type: egx, us, both  (or "none" to revoke)`,
      u.plan || "both");
    if (plan === null) return;
    const p = plan.trim().toLowerCase();
    if (p === "none" || p === "") return wrap(() => api.adminSetSubscription(u.id, { plan: null }));
    if (!["egx", "us", "both"].includes(p)) return alert("Plan must be egx, us, both or none");
    const days = window.prompt("How many days? (adds to any time already left)", "30");
    if (days === null) return;
    wrap(() => api.adminSetSubscription(u.id, {
      plan: p, days: Number(days) || 30, note: "granted from admin panel",
    }));
  };
  const del = (u) => {
    if (window.confirm(`Delete ${u.email}? This cannot be undone.`))
      wrap(() => api.adminDeleteUser(u.id));
  };

  const fmt = (d) => (d ? new Date(d).toLocaleDateString() : "—");
  const isAdminAcct = (u) => u.role === "admin";

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
          <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
            <label>Email</label>
            <input type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
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
              <th>Email</th><th>Role</th><th>Plan</th><th>Status</th>
              <th>Last login</th><th>Actions</th>
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
                <td data-label="Plan">
                  {u.role === "admin" || u.role === "staff" ? (
                    <span className="pill" title="Role includes full access">free access</span>
                  ) : u.subscription_active ? (
                    <span className="up" title={`Markets: ${(u.markets || []).join(", ")}`}>
                      {(u.plan || "").toUpperCase()}
                      <small style={{ display: "block", color: "var(--muted)" }}>
                        {u.plan_source === "manual" ? "granted" : u.plan_source} · to {String(u.plan_until || "").slice(0, 10)}
                      </small>
                    </span>
                  ) : (
                    <span className="down">none</span>
                  )}
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
                      <button className="iconbtn" disabled={busy} onClick={() => cycleRole(u)}>
                        Role: {u.role} →
                      </button>
                      <button className="iconbtn" disabled={busy} onClick={() => grant(u)}
                        title="Give, extend or revoke a plan without payment">
                        💳 Plan
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
