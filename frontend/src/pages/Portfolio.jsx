import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { SIGNAL_LABEL, money, prob, signed } from "../format.js";

function Kpi({ label, value, cls }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={`value ${cls || ""}`}>{value}</div>
    </div>
  );
}

export default function Portfolio() {
  const [pf, setPf] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ ticker: "", buy_price: "", quantity: "" });
  const [budget, setBudget] = useState("");
  const [alloc, setAlloc] = useState(null);

  const load = () =>
    api.portfolio().then((d) => { setPf(d); if (d.budget) setBudget(d.budget); })
      .catch((e) => setErr(e.message));
  useEffect(load, []);

  const wrap = async (fn) => {
    setErr(""); setBusy(true);
    try { await fn(); load(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const addHolding = (e) => {
    e.preventDefault();
    wrap(async () => {
      await api.addHolding(form.ticker, parseFloat(form.buy_price), parseFloat(form.quantity));
      setForm({ ticker: "", buy_price: "", quantity: "" });
    });
  };
  const del = (h) => wrap(() => api.deleteHolding(h.id));
  const saveBudget = () => wrap(() => api.setBudget(parseFloat(budget) || 0));
  const suggest = () =>
    wrap(async () => setAlloc(await api.allocate(parseFloat(budget) || undefined)));

  if (err && !pf) return <div className="container"><div className="error">{err}</div></div>;
  if (!pf) return <div className="loading">Loading portfolio…</div>;

  const pnlCls = (v) => (v == null ? "" : v >= 0 ? "up" : "down");

  return (
    <div className="container">
      <h2 style={{ marginTop: 0 }}>Portfolio</h2>
      {err && <div className="error">{err}</div>}

      <div className="kpis">
        <Kpi label="Invested" value={money(pf.invested)} />
        <Kpi label="Current value" value={money(pf.current_value)} />
        <Kpi label="Total P/L" value={`${pf.pnl >= 0 ? "+" : ""}${money(pf.pnl)}${pf.pnl_pct != null ? ` (${signed(pf.pnl_pct)})` : ""}`} cls={pnlCls(pf.pnl)} />
        <Kpi label="Budget" value={pf.budget ? money(pf.budget) : "—"} />
      </div>

      {/* Add holding */}
      <div className="section-title">Add a stock you bought</div>
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        <form onSubmit={addHolding} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 150px" }}>
            <label>Ticker (e.g. COMI)</label>
            <input required value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 130px" }}>
            <label>Buy price</label>
            <input type="number" step="any" required value={form.buy_price} onChange={(e) => setForm({ ...form, buy_price: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 130px" }}>
            <label>Quantity (shares)</label>
            <input type="number" step="any" required value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </div>
          <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy}>Add</button>
        </form>
      </div>

      {/* Holdings */}
      <div className="section-title">Your holdings</div>
      <div className="card" style={{ overflowX: "auto" }}>
        <table className="responsive">
          <thead>
            <tr>
              <th>Stock</th><th>Signal</th><th>Success</th><th className="num">Buy</th>
              <th className="num">Now</th><th className="num">P/L</th><th>Alert</th><th></th>
            </tr>
          </thead>
          <tbody>
            {pf.holdings.length === 0 && (
              <tr><td colSpan={8} style={{ color: "var(--muted)" }}>No holdings yet — add one above.</td></tr>
            )}
            {pf.holdings.map((h) => (
              <tr key={h.id} style={{ cursor: "default" }}>
                <td className="tickercell" data-label="Stock">
                  <Link to={`/stocks/${h.ticker}`}>{h.ticker.replace(".EGX", "")}</Link>
                  <small>{h.name} · {h.quantity} sh</small>
                </td>
                <td data-label="Signal">{h.signal ? <span className={`badge ${h.signal}`}>{SIGNAL_LABEL[h.signal]}</span> : "—"}</td>
                <td data-label="Success" className="prob"><b>{prob(h.success_prob)}</b></td>
                <td className="num" data-label="Buy">{money(h.buy_price)}</td>
                <td className="num" data-label="Now">{money(h.current_price)}</td>
                <td className={`num ${pnlCls(h.pnl)}`} data-label="P/L">
                  {h.pnl == null ? "—" : `${h.pnl >= 0 ? "+" : ""}${money(h.pnl)}`}
                  {h.pnl_pct != null && <small style={{ display: "block", color: "var(--muted)" }}>{signed(h.pnl_pct)}</small>}
                </td>
                <td data-label="Alert">{h.alert ? <span className={h.sell_suggested ? "down" : ""}>{h.sell_suggested ? "⚠ " : ""}{h.alert}</span> : <span style={{ color: "var(--muted)" }}>—</span>}</td>
                <td data-label="">
                  <button className="ghost" disabled={busy} onClick={() => del(h)} style={{ color: "var(--red)", borderColor: "var(--red)" }}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Budget + allocation */}
      <div className="section-title">Budget &amp; suggested allocation</div>
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
            <label>Budget (EGP)</label>
            <input type="number" step="any" value={budget} onChange={(e) => setBudget(e.target.value)} />
          </div>
          <button className="ghost" disabled={busy} onClick={saveBudget}>Save budget</button>
          <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy} onClick={suggest}>
            Suggest allocation
          </button>
        </div>

        {alloc && (
          <div style={{ marginTop: 16 }}>
            <p style={{ color: "var(--muted)", fontSize: 13 }}>
              {alloc.note} Leftover cash: <b>{money(alloc.leftover_cash)}</b> EGP.
            </p>
            <div style={{ overflowX: "auto" }}>
              <table className="responsive">
                <thead>
                  <tr>
                    <th>Stock</th><th>Signal</th><th>Success</th>
                    <th className="num">Allocate</th><th className="num">Shares</th><th className="num">Entry</th>
                  </tr>
                </thead>
                <tbody>
                  {alloc.allocations.map((a) => (
                    <tr key={a.ticker} style={{ cursor: "default" }}>
                      <td className="tickercell" data-label="Stock">{a.ticker.replace(".EGX", "")}<small>{a.name}</small></td>
                      <td data-label="Signal"><span className={`badge ${a.signal}`}>{SIGNAL_LABEL[a.signal]}</span></td>
                      <td className="prob" data-label="Success"><b>{prob(a.success_prob)}</b></td>
                      <td className="num" data-label="Allocate">{money(a.suggested_amount)}</td>
                      <td className="num" data-label="Shares">{a.shares}</td>
                      <td className="num" data-label="Entry">{money(a.entry_price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <p className="disclaimer">
        P/L and signals use the latest end-of-day data. Allocation is a diversified suggestion
        weighted by success rate — <b>not financial advice</b>. You decide and execute every trade.
      </p>
    </div>
  );
}
