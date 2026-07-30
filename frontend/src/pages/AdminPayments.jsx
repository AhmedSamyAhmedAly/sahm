import { useEffect, useState } from "react";
import { api } from "../api.js";

const money = (x) => (x == null ? "—" : `$${Number(x).toFixed(2)}`);
const when = (s) => (s ? String(s).replace("T", " ").slice(0, 16) : "—");

const ACTION = {
  activate: { label: "activated", cls: "up" },
  renew: { label: "renewed", cls: "up" },
  grant: { label: "granted", cls: "" },
  revoke: { label: "revoked", cls: "down" },
  cancel: { label: "cancelled", cls: "down" },
  payment_failed: { label: "payment failed", cls: "down" },
  expire: { label: "expired", cls: "down" },
};

function Kpi({ label, value, sub, tone }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={`value ${tone || ""}`}>{value}</div>
      {sub && <div style={{ color: "var(--muted)", fontSize: 11 }}>{sub}</div>}
    </div>
  );
}

export default function AdminPayments() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.adminPayments().then(setD).catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="container"><div className="error">{err}</div></div>;
  if (!d) return <div className="loading">Loading payments…</div>;

  const planRows = Object.entries(d.by_plan || {});

  return (
    <div className="container wide">
      <h2 style={{ marginBottom: 4 }}>Payments</h2>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        Subscription revenue and activity. Provider: <b>{d.provider}</b> — its dashboard
        is the source of truth for money actually settled; this page reflects what the
        app recorded.
      </p>

      <div className="kpis">
        <Kpi label="Active subscribers" value={d.active_subscribers} />
        <Kpi label="Est. MRR" value={money(d.mrr_estimate)}
          sub="annual plans counted as 1/12 per month" tone="up" />
        <Kpi label="Recorded this month" value={money(d.collected_this_month)} />
        <Kpi label="Recorded (last 100 events)" value={money(d.collected)} />
      </div>

      <div className="kpis" style={{ marginTop: 10 }}>
        <Kpi label="Free access (admin/staff)" value={d.free_role_users} />
        <Kpi label="No active plan" value={d.unpaid_users}
          tone={d.unpaid_users ? "down" : ""} />
        {planRows.map(([plan, n]) => (
          <Kpi key={plan} label={`${(plan || "?").toUpperCase()} subscribers`} value={n} />
        ))}
      </div>

      {d.expiring_soon?.length > 0 && (
        <>
          <div className="section-title">⏰ Expiring within 7 days</div>
          <div className="card" style={{ overflowX: "auto" }}>
            <table className="responsive">
              <thead>
                <tr><th>Email</th><th>Plan</th><th>Expires</th><th className="num">Days left</th><th>Source</th></tr>
              </thead>
              <tbody>
                {d.expiring_soon.map((u) => (
                  <tr key={u.email}>
                    <td className="tickercell" data-label="Email">{u.email}</td>
                    <td data-label="Plan">{(u.plan || "").toUpperCase()}</td>
                    <td data-label="Expires">{when(u.plan_until)}</td>
                    <td className={`num ${u.days_left <= 2 ? "down" : ""}`} data-label="Days left">
                      {u.days_left}
                    </td>
                    <td data-label="Source">{u.source || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="section-title">Recent activity</div>
      <div className="card" style={{ overflowX: "auto" }}>
        <table className="responsive">
          <thead>
            <tr>
              <th>When</th><th>Email</th><th>Event</th><th>Plan</th>
              <th className="num">Amount</th><th>Source</th><th>Note</th>
            </tr>
          </thead>
          <tbody>
            {d.events.length === 0 && (
              <tr><td colSpan={7} style={{ color: "var(--muted)" }}>
                No subscription activity yet.
              </td></tr>
            )}
            {d.events.map((e, i) => {
              const a = ACTION[e.action] || { label: e.action, cls: "" };
              return (
                <tr key={i}>
                  <td data-label="When">{when(e.created_at)}</td>
                  <td className="tickercell" data-label="Email">{e.email}</td>
                  <td data-label="Event"><span className={a.cls}>{a.label}</span></td>
                  <td data-label="Plan">
                    {(e.plan || "").toUpperCase()}
                    {e.period ? <small style={{ display: "block", color: "var(--muted)" }}>{e.period}</small> : null}
                  </td>
                  <td className="num" data-label="Amount">{e.amount ? money(e.amount) : "—"}</td>
                  <td data-label="Source">{e.source || "—"}</td>
                  <td data-label="Note" style={{ color: "var(--muted)", fontSize: 12 }}>
                    {e.note || e.reference || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="disclaimer" style={{ marginTop: 12 }}>
        <b>Est. MRR</b> prices each active plan at its monthly rate (annual plans divided
        by 12) — a forward estimate, not cash received. <b>Recorded</b> totals only count
        activation/renewal events this app captured, so reconcile against your
        provider&nbsp;dashboard and bank before treating either as accounting.
      </p>
    </div>
  );
}
