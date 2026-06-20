import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { SIGNAL_LABEL, money, prob, signed } from "../format.js";

const RANGES = [
  { label: "1M", days: 30 }, { label: "3M", days: 90 }, { label: "6M", days: 180 },
  { label: "1Y", days: 365 }, { label: "All", days: 0 },
];

function Kpi({ label, value, cls }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={`value ${cls || ""}`}>{value}</div>
    </div>
  );
}

export default function Portfolio() {
  const { setUserBudget } = useAuth();
  const [pf, setPf] = useState(null);
  const [assets, setAssets] = useState([]);
  const [alloc, setAlloc] = useState(null);
  const [hist, setHist] = useState(null);
  const [range, setRange] = useState(90);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ ticker: "", buy_price: "", quantity: "" });
  const [initBudget, setInitBudget] = useState("");
  const [step, setStep] = useState(1000);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState({ buy_price: "", quantity: "" });
  const [msg, setMsg] = useState("");
  const fileRef = useRef(null);

  const load = async () => {
    const d = await api.portfolio();
    setPf(d);
    if (d.budget > 0) {
      try { setAlloc(await api.allocate(d.budget)); } catch { setAlloc(null); }
    } else {
      setAlloc(null);
    }
  };

  useEffect(() => {
    load().catch((e) => setErr(e.message));
    api.assets().then(setAssets).catch(() => {});
  }, []);

  useEffect(() => {
    if (pf && pf.holdings.length) api.portfolioHistory(range).then(setHist).catch(() => {});
    else setHist(null);
  }, [range, pf?.holdings.length]);

  const wrap = async (fn) => {
    setErr(""); setBusy(true);
    try { await fn(); await load(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const addHolding = (e) => {
    e.preventDefault();
    wrap(async () => {
      await api.addHolding(form.ticker, parseFloat(form.buy_price), parseFloat(form.quantity));
      setForm({ ticker: "", buy_price: "", quantity: "" });
    });
  };
  const sell = (h) => {
    if (window.confirm(`Sell (close) your ${h.ticker.replace(".EGX", "")} position?`))
      wrap(() => api.deleteHolding(h.id));
  };
  const changeBudget = (delta) => {
    const nb = Math.max(0, (pf.budget || 0) + delta);
    wrap(async () => { await api.setBudget(nb); setUserBudget(nb); });
  };
  const setStartBudget = () => {
    const nb = Math.max(0, parseFloat(initBudget) || 0);
    if (nb <= 0) { setErr("Enter a budget greater than 0"); return; }
    wrap(async () => { await api.setBudget(nb); setUserBudget(nb); });
  };

  const startEdit = (h) => { setEditId(h.id); setEditForm({ buy_price: h.buy_price, quantity: h.quantity }); };
  const saveEdit = (h) => wrap(async () => {
    await api.updateHolding(h.id, {
      buy_price: parseFloat(editForm.buy_price), quantity: parseFloat(editForm.quantity),
    });
    setEditId(null);
  });

  const onCsv = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const items = [];
      String(reader.result).split(/\r?\n/).forEach((line) => {
        const c = line.split(",").map((x) => x.trim());
        if (c.length < 3 || !c[0] || /ticker/i.test(c[0])) return;
        const price = parseFloat(c[1]), qty = parseFloat(c[2]);
        if (isFinite(price) && isFinite(qty)) items.push({ ticker: c[0], buy_price: price, quantity: qty });
      });
      if (!items.length) { setErr("No valid rows. Expected: ticker,buy_price,quantity"); return; }
      setMsg("");
      wrap(async () => {
        const r = await api.importHoldings(items);
        setMsg(`Imported ${r.added}${r.skipped ? `, skipped ${r.skipped}` : ""}.` +
          (r.errors?.length ? ` Issues: ${r.errors.join("; ")}` : ""));
      });
    };
    reader.readAsText(file);
  };
  const TEMPLATE = "data:text/csv;charset=utf-8," +
    encodeURIComponent("ticker,buy_price,quantity\nCOMI,120,50\nSWDY,45,100");

  if (err && !pf) return <div className="container"><div className="error">{err}</div></div>;
  if (!pf) return <div className="loading">Loading portfolio…</div>;

  const pnlCls = (v) => (v == null ? "" : v >= 0 ? "up" : "down");
  const isNew = !pf.budget && pf.holdings.length === 0;
  const editInput = { width: 72, background: "var(--bg)", border: "1px solid var(--border)",
    color: "var(--text)", borderRadius: 6, padding: "6px 8px" };

  return (
    <div className="container">
      <h2 style={{ marginTop: 0 }}>Portfolio</h2>
      {err && <div className="error">{err}</div>}
      {msg && <div className="card" style={{ padding: "10px 14px", marginBottom: 12, color: "var(--accent)", fontSize: 14 }}>{msg}</div>}

      {isNew && (
        <div className="card" style={{ padding: 18, marginBottom: 18, borderColor: "var(--accent)" }}>
          <h3 style={{ marginTop: 0 }}>👋 Welcome to your Portfolio</h3>
          <p style={{ color: "var(--muted)", marginBottom: 8 }}>Two quick steps to get started:</p>
          <ol style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            <li><b>Set your budget</b> below — the cash you want to invest.</li>
            <li><b>Add stocks you already own</b> (ticker, buy price, quantity).</li>
          </ol>
          <p style={{ color: "var(--muted)", marginTop: 8, marginBottom: 0 }}>
            We'll then suggest how to split your budget across the best signals.
          </p>
        </div>
      )}

      <div className="kpis">
        <Kpi label="Invested" value={money(pf.invested)} />
        <Kpi label="Current value" value={money(pf.current_value)} />
        <Kpi label="Total P/L" value={`${pf.pnl >= 0 ? "+" : ""}${money(pf.pnl)}${pf.pnl_pct != null ? ` (${signed(pf.pnl_pct)})` : ""}`} cls={pnlCls(pf.pnl)} />
        <Kpi label="Budget" value={pf.budget ? money(pf.budget) : "—"} />
      </div>

      {/* Budget */}
      <div className="section-title">Budget</div>
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        {!pf.budget ? (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
              <label>Starting budget (EGP)</label>
              <input type="number" step="any" value={initBudget} onChange={(e) => setInitBudget(e.target.value)} />
            </div>
            <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy} onClick={setStartBudget}>
              Set budget
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ fontSize: 26, fontWeight: 800 }}>{money(pf.budget)} <small style={{ color: "var(--muted)", fontSize: 13 }}>EGP</small></div>
            <div style={{ flex: 1 }} />
            <label style={{ color: "var(--muted)", fontSize: 13 }}>Step</label>
            <input type="number" value={step} onChange={(e) => setStep(parseFloat(e.target.value) || 0)}
              style={{ width: 100, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 8, padding: "8px 10px" }} />
            <button className="ghost" disabled={busy} onClick={() => changeBudget(-step)}>− {money(step)}</button>
            <button className="ghost" disabled={busy} onClick={() => changeBudget(step)}>+ {money(step)}</button>
          </div>
        )}
      </div>

      {/* Add holding */}
      <div className="section-title">Add a stock you own</div>
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        <form onSubmit={addHolding} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
            <label>Stock</label>
            <input list="tickers" required placeholder="Type or pick a ticker"
              value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} />
            <datalist id="tickers">
              {assets.map((a) => (
                <option key={a.ticker} value={a.ticker.replace(".EGX", "")}>
                  {a.ticker.replace(".EGX", "")} — {a.name}
                </option>
              ))}
            </datalist>
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 120px" }}>
            <label>Buy price</label>
            <input type="number" step="any" required value={form.buy_price} onChange={(e) => setForm({ ...form, buy_price: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 120px" }}>
            <label>Quantity</label>
            <input type="number" step="any" required value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </div>
          <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy}>Add</button>
        </form>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
          <button className="ghost" disabled={busy} onClick={() => fileRef.current?.click()}>Import CSV</button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={onCsv} style={{ display: "none" }} />
          <a className="link" href={TEMPLATE} download="portfolio_template.csv">Download template</a>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>CSV columns: ticker, buy_price, quantity</span>
        </div>
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
                <td className="num" data-label="Buy">
                  {editId === h.id ? (
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <input type="number" step="any" title="Buy price" style={editInput}
                        value={editForm.buy_price} onChange={(e) => setEditForm({ ...editForm, buy_price: e.target.value })} />
                      <input type="number" step="any" title="Quantity" style={editInput}
                        value={editForm.quantity} onChange={(e) => setEditForm({ ...editForm, quantity: e.target.value })} />
                    </div>
                  ) : money(h.buy_price)}
                </td>
                <td className="num" data-label="Now">{money(h.current_price)}</td>
                <td className={`num ${pnlCls(h.pnl)}`} data-label="P/L">
                  {h.pnl == null ? "—" : `${h.pnl >= 0 ? "+" : ""}${money(h.pnl)}`}
                  {h.pnl_pct != null && <small style={{ display: "block", color: "var(--muted)" }}>{signed(h.pnl_pct)}</small>}
                </td>
                <td data-label="Alert">{h.alert ? <span className={h.sell_suggested ? "down" : ""}>{h.sell_suggested ? "⚠ " : ""}{h.alert}</span> : <span style={{ color: "var(--muted)" }}>—</span>}</td>
                <td data-label="">
                  {editId === h.id ? (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="ghost" disabled={busy} onClick={() => saveEdit(h)}>Save</button>
                      <button className="ghost" disabled={busy} onClick={() => setEditId(null)}>Cancel</button>
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="ghost" disabled={busy} onClick={() => startEdit(h)}>Edit</button>
                      <button className="ghost" disabled={busy} onClick={() => sell(h)}
                        style={{ color: h.sell_suggested ? "var(--red)" : "var(--text)", borderColor: h.sell_suggested ? "var(--red)" : "var(--border)" }}>
                        Sell
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Performance chart */}
      {pf.holdings.length > 0 && (
        <>
          <div className="section-title">Performance</div>
          <div className="card" style={{ padding: 16, marginBottom: 18 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
              {RANGES.map((r) => (
                <button key={r.days} className="ghost" onClick={() => setRange(r.days)}
                  style={range === r.days ? { borderColor: "var(--accent)", color: "var(--accent)" } : {}}>
                  {r.label}
                </button>
              ))}
            </div>
            {hist && hist.series.length > 1 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={hist.series} margin={{ top: 6, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="#232c3d" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "#8a97ad", fontSize: 11 }} minTickGap={40} />
                  <YAxis tick={{ fill: "#8a97ad", fontSize: 11 }} width={64} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "#161c28", border: "1px solid #232c3d", borderRadius: 8 }} />
                  <Line type="monotone" dataKey="value" name="Value" stroke="#3ddc97" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="invested" name="Cost basis" stroke="#8a97ad" strokeWidth={1} strokeDasharray="4 4" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ color: "var(--muted)", margin: 0 }}>Not enough price history for this range yet.</p>
            )}
            <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>
              Current holdings valued over time (green) vs. what you paid (dashed). End-of-day data.
            </p>
          </div>
        </>
      )}

      {/* Auto allocation */}
      <div className="section-title">Suggested allocation</div>
      <div className="card" style={{ padding: 16 }}>
        {!pf.budget ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>Set a budget above to see a suggested allocation.</p>
        ) : !alloc || alloc.allocations.length === 0 ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>No buy candidates to allocate right now.</p>
        ) : (
          <>
            <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
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
          </>
        )}
      </div>

      <p className="disclaimer">
        P/L and signals use the latest end-of-day data. Allocation is a diversified suggestion
        weighted by success rate — <b>not financial advice</b>. You decide and execute every trade.
      </p>
    </div>
  );
}
