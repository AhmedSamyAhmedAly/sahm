import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import NumberInput from "../components/NumberInput.jsx";
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
  const { setUserBudget } = useAuth();
  const [pf, setPf] = useState(null);
  const [alloc, setAlloc] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ ticker: "", buy_price: "", quantity: "", deduct: true });
  const [msg, setMsg] = useState("");
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState({ buy_price: "", quantity: "" });
  const [editingBudget, setEditingBudget] = useState(false);
  const [budgetInput, setBudgetInput] = useState("");
  const [sellFor, setSellFor] = useState(null);
  const [sellForm, setSellForm] = useState({ sell_price: "", units: "" });
  const [showSales, setShowSales] = useState(false);
  const [sales, setSales] = useState(null);
  const [saleEditId, setSaleEditId] = useState(null);
  const [saleEdit, setSaleEdit] = useState({ sell_price: "", units: "" });
  const fileRef = useRef(null);

  const load = async () => {
    const d = await api.portfolio();
    setPf(d);
    setUserBudget(d.budget);
    if (d.budget > 0) { try { setAlloc(await api.allocate(d.budget)); } catch { setAlloc(null); } }
    else setAlloc(null);
  };

  useEffect(() => { load().catch((e) => setErr(e.message)); }, []);

  const wrap = async (fn) => {
    setErr(""); setBusy(true);
    try { await fn(); await load(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const addHolding = (e) => {
    e.preventDefault();
    wrap(async () => {
      await api.addHolding(form.ticker, parseFloat(form.buy_price), parseFloat(form.quantity), form.deduct);
      setForm({ ticker: "", buy_price: "", quantity: "", deduct: form.deduct });
    });
  };
  const removeHolding = (h) => {
    if (window.confirm(`Remove ${h.ticker.replace(".EGX", "")} from your portfolio?`))
      wrap(() => api.deleteHolding(h.id));
  };
  const startEdit = (h) => { setEditId(h.id); setEditForm({ buy_price: h.buy_price, quantity: h.quantity }); };
  const saveEdit = (h) => wrap(async () => {
    await api.updateHolding(h.id, {
      buy_price: parseFloat(editForm.buy_price), quantity: parseFloat(editForm.quantity),
    });
    setEditId(null);
  });

  const openSell = (h) => {
    setSellFor(h);
    setSellForm({ sell_price: h.current_price ?? "", units: h.quantity });
  };
  const confirmSell = () => {
    const price = parseFloat(sellForm.sell_price), units = parseFloat(sellForm.units);
    if (!(price > 0) || !(units > 0)) { setErr("Enter a valid sell price and units"); return; }
    wrap(async () => {
      await api.sellHolding(sellFor.id, price, units);
      setSellFor(null);
    });
  };

  const saveBudget = (val) => {
    const nb = Math.max(0, parseFloat(val) || 0);
    if (nb <= 0) { setErr("Enter a budget greater than 0"); return; }
    wrap(async () => { await api.setBudget(nb); setUserBudget(nb); setEditingBudget(false); });
  };

  // ---- sell history ----
  const openSales = () => { setShowSales(true); setSaleEditId(null); api.sales().then(setSales).catch((e) => setErr(e.message)); };
  const refreshSales = () => api.sales().then(setSales).catch(() => {});
  const startSaleEdit = (s) => { setSaleEditId(s.id); setSaleEdit({ sell_price: s.sell_price, units: s.units }); };
  const saveSaleEdit = (s) => wrap(async () => {
    await api.updateSale(s.id, { sell_price: parseFloat(saleEdit.sell_price), units: parseFloat(saleEdit.units) });
    setSaleEditId(null); await refreshSales();
  });
  const removeSale = (s) => {
    if (!window.confirm(`Remove this sell of ${s.units} ${s.ticker.replace(".EGX", "")}? Units go back to the holding and proceeds leave your budget.`)) return;
    wrap(async () => { await api.deleteSale(s.id); await refreshSales(); });
  };

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
  const editInput = { width: 84, background: "var(--bg)", border: "1px solid var(--border)",
    color: "var(--text)", borderRadius: 6, padding: "6px 8px" };

  return (
    <div className="container">
      <h2 style={{ marginTop: 0 }}>Portfolio</h2>
      {err && <div className="error">{err}</div>}
      {msg && <div className="card" style={{ padding: "10px 14px", marginBottom: 12, color: "var(--accent)", fontSize: 14 }}>{msg}</div>}

      <div className="kpis">
        <Kpi label="💼 Invested" value={money(pf.invested)} />
        <Kpi label="📊 Current value" value={money(pf.current_value)} />
        <Kpi label="💰 Earnings (sold)" cls={pnlCls(pf.realized_pnl)}
          value={`${pf.realized_pnl >= 0 ? "+" : ""}${money(pf.realized_pnl)}`} />
        <Kpi label="💧 Liquid money" value={pf.budget ? money(pf.budget) : "—"} />
      </div>

      {/* Budget / Liquid money */}
      <div className="section-title">💧 Liquid money (budget)</div>
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        {!pf.budget || editingBudget ? (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
              <label>Liquid money (EGP)</label>
              <NumberInput step={1000} min={0} autoFocus
                value={editingBudget ? budgetInput : (budgetInput || "")}
                onChange={setBudgetInput} />
            </div>
            <button className="primary" style={{ width: "auto", padding: "11px 18px" }}
              disabled={busy} onClick={() => saveBudget(budgetInput)}>Save</button>
            {pf.budget > 0 && (
              <button className="ghost" disabled={busy} onClick={() => setEditingBudget(false)}>Cancel</button>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div style={{ fontSize: 26, fontWeight: 800 }}>{money(pf.budget)} <small style={{ color: "var(--muted)", fontSize: 13 }}>EGP free cash</small></div>
            <div style={{ flex: 1 }} />
            <button className="ghost" disabled={busy}
              onClick={() => { setBudgetInput(String(pf.budget)); setEditingBudget(true); }}>Edit</button>
          </div>
        )}
        <p style={{ color: "var(--muted)", fontSize: 12, margin: "10px 0 0" }}>
          Your free cash to invest. Buying a stock (with “deduct” ticked) lowers it; selling adds the
          proceeds back automatically.
        </p>
      </div>

      {/* Add holding */}
      <div className="section-title">➕ Add a stock you own</div>
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        <form onSubmit={addHolding} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
            <label>Stock</label>
            <input list="tickers" required placeholder="Type or pick a ticker"
              value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 130px" }}>
            <label>Buy price</label>
            <NumberInput step={0.5} min={0} value={form.buy_price}
              onChange={(v) => setForm({ ...form, buy_price: v })} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 130px" }}>
            <label>Quantity</label>
            <NumberInput step={1} min={0} value={form.quantity}
              onChange={(v) => setForm({ ...form, quantity: v })} />
          </div>
          <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy}>Add</button>
        </form>
        <label className="checkrow" style={{ marginTop: 12 }}>
          <input type="checkbox" checked={form.deduct}
            onChange={(e) => setForm({ ...form, deduct: e.target.checked })} />
          Subtract this cost from my liquid money
        </label>
        <p style={{ color: "var(--muted)", fontSize: 12, margin: "8px 0 0" }}>
          Buying a stock you already own <b>averages in</b> (updates your average buy price).
        </p>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
          <button type="button" className="ghost" disabled={busy} onClick={() => fileRef.current?.click()}>Import CSV</button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={onCsv} style={{ display: "none" }} />
          <a className="link" href={TEMPLATE} download="portfolio_template.csv">Download template</a>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>CSV: ticker, buy_price, quantity</span>
        </div>
      </div>
      <TickerOptions />

      {/* Holdings */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", margin: "22px 0 10px" }}>
        <div className="section-title" style={{ margin: 0 }}>📦 Your holdings</div>
        <div style={{ flex: 1 }} />
        <button className="iconbtn" onClick={openSales}>🧾 Sell history</button>
      </div>
      <div className="card" style={{ padding: 4 }}>
        <table className="responsive holdings">
          <thead>
            <tr>
              <th>Stock</th><th>Signal</th><th className="num">Bought</th><th className="num">Now</th>
              <th className="num">Target</th><th className="num">P/L</th><th></th>
            </tr>
          </thead>
          <tbody>
            {pf.holdings.length === 0 && (
              <tr><td colSpan={7} style={{ color: "var(--muted)" }}>No holdings yet — add one above.</td></tr>
            )}
            {pf.holdings.map((h) => (
              <tr key={h.id} style={{ cursor: "default" }}>
                <td className="tickercell" data-label="Stock">
                  <Link to={`/stocks/${h.ticker}`}>{h.ticker.replace(".EGX", "")}</Link>
                  <small>
                    {h.name} · {h.quantity} sh{h.sold_qty > 0 ? ` · sold ${h.sold_qty}@${money(h.avg_sell_price)}` : ""}
                    {h.from_budget ? " · 💧 from budget" : ""}
                  </small>
                  {h.alert && (
                    <div className={`alertline ${h.alert === "Stop loss" ? "warn" : "good"}`}>
                      {h.alert === "Stop loss" ? "🛑 Stop loss" : "🎯 Take profit"}
                    </div>
                  )}
                </td>
                <td data-label="Signal">
                  {["hold", "sell", "strong_sell"].includes(h.signal)
                    ? <span className={`badge ${h.signal}`}>{SIGNAL_LABEL[h.signal]}</span>
                    : <span style={{ color: "var(--muted)" }}>—</span>}
                </td>
                <td className="num" data-label="Bought">
                  {editId === h.id ? (
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", flexWrap: "wrap" }}>
                      <input type="number" step="any" title="Buy price" style={editInput}
                        value={editForm.buy_price} onChange={(e) => setEditForm({ ...editForm, buy_price: e.target.value })} />
                      <input type="number" step="any" title="Quantity" style={editInput}
                        value={editForm.quantity} onChange={(e) => setEditForm({ ...editForm, quantity: e.target.value })} />
                    </div>
                  ) : money(h.buy_price)}
                </td>
                <td className="num" data-label="Now">{money(h.current_price)}</td>
                <td className="num up" data-label="Target">{money(h.target_price)}</td>
                <td className={`num ${pnlCls(h.pnl)}`} data-label="P/L">
                  <span className="pl-main">{h.pnl == null ? "—" : `${h.pnl >= 0 ? "+" : ""}${money(h.pnl)}`}</span>
                  {h.pnl_pct != null && <small className="pl-sub">{signed(h.pnl_pct)}</small>}
                </td>
                <td data-label="">
                  {editId === h.id ? (
                    <div className="acts">
                      <button className="iconbtn" disabled={busy} onClick={() => saveEdit(h)}>✓ Save</button>
                      <button className="iconbtn" disabled={busy} onClick={() => setEditId(null)}>Cancel</button>
                    </div>
                  ) : (
                    <div className="acts">
                      <button className="iconbtn" disabled={busy} onClick={() => startEdit(h)}>✏️ Edit</button>
                      <button className="iconbtn" disabled={busy} onClick={() => openSell(h)}
                        style={{ color: h.sell_suggested ? "var(--red)" : undefined, borderColor: h.sell_suggested ? "var(--red)" : undefined }}>💵 Sell</button>
                      <button className="iconbtn" disabled={busy} onClick={() => removeHolding(h)}>🗑️ Remove</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Allocation */}
      <div className="section-title">🎯 Suggested allocation</div>
      <div className="card" style={{ padding: 16 }}>
        {!pf.budget ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>Set your liquid money above to see a suggested allocation.</p>
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
                  <tr><th>Stock</th><th>Signal</th><th>Success</th><th className="num">Allocate</th><th className="num">Shares</th><th className="num">Entry</th></tr>
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

      {/* Sell modal */}
      {sellFor && (
        <div className="modal-overlay" onClick={() => setSellFor(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <h3>Sell {sellFor.ticker.replace(".EGX", "")}</h3>
            <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
              You hold {sellFor.quantity} shares (avg buy {money(sellFor.buy_price)}).
            </p>
            <div className="field"><label>Sell price</label>
              <NumberInput step={0.5} min={0} value={sellForm.sell_price}
                onChange={(v) => setSellForm({ ...sellForm, sell_price: v })} /></div>
            <div className="field"><label>Units (max {sellFor.quantity})</label>
              <NumberInput step={1} min={0} max={sellFor.quantity} value={sellForm.units}
                onChange={(v) => setSellForm({ ...sellForm, units: v })} /></div>
            <p style={{ color: "var(--muted)", fontSize: 12 }}>
              Proceeds are added to your liquid money. Selling all units closes the position; a partial
              sell reduces it and updates your average sell price.
            </p>
            <div className="modal-actions">
              <div className="grow" />
              <button className="ghost" disabled={busy} onClick={() => setSellFor(null)}>Cancel</button>
              <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy} onClick={confirmSell}>Confirm sell</button>
            </div>
          </div>
        </div>
      )}

      {/* Sell history modal */}
      {showSales && (
        <div className="modal-overlay" onClick={() => setShowSales(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640 }}>
            <h3>Sell history</h3>
            <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
              Edit or remove a sell. Changes re-open the units on the holding and adjust your liquid money.
            </p>
            {sales == null ? (
              <p style={{ color: "var(--muted)" }}>Loading…</p>
            ) : sales.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>No sells yet.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="responsive">
                  <thead>
                    <tr><th>Stock</th><th>Date</th><th className="num">Units</th><th className="num">Price</th><th className="num">Realized</th><th></th></tr>
                  </thead>
                  <tbody>
                    {sales.map((s) => (
                      <tr key={s.id} style={{ cursor: "default" }}>
                        <td className="tickercell" data-label="Stock">{s.ticker.replace(".EGX", "")}<small>{s.name}</small></td>
                        <td data-label="Date" style={{ color: "var(--muted)" }}>{(s.created_at || "").slice(0, 10)}</td>
                        <td className="num" data-label="Units">
                          {saleEditId === s.id
                            ? <input type="number" step="any" style={editInput} value={saleEdit.units}
                                onChange={(e) => setSaleEdit({ ...saleEdit, units: e.target.value })} />
                            : s.units}
                        </td>
                        <td className="num" data-label="Price">
                          {saleEditId === s.id
                            ? <input type="number" step="any" style={editInput} value={saleEdit.sell_price}
                                onChange={(e) => setSaleEdit({ ...saleEdit, sell_price: e.target.value })} />
                            : money(s.sell_price)}
                        </td>
                        <td className={`num ${pnlCls(s.gain)}`} data-label="Realized">{`${s.gain >= 0 ? "+" : ""}${money(s.gain)}`}</td>
                        <td data-label="">
                          <div className="acts">
                            {saleEditId === s.id ? (
                              <>
                                <button className="iconbtn" disabled={busy} onClick={() => saveSaleEdit(s)}>Save</button>
                                <button className="iconbtn" disabled={busy} onClick={() => setSaleEditId(null)}>Cancel</button>
                              </>
                            ) : (
                              <>
                                <button className="iconbtn" disabled={busy} onClick={() => startSaleEdit(s)}>Edit</button>
                                <button className="iconbtn" disabled={busy} onClick={() => removeSale(s)}>Remove</button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="modal-actions">
              <div className="grow" />
              <button className="ghost" onClick={() => setShowSales(false)}>Close</button>
            </div>
          </div>
        </div>
      )}

      <p className="disclaimer">
        P/L, earnings and signals use the latest end-of-day data. Allocation is a diversified
        suggestion weighted by success rate — <b>not financial advice</b>.
      </p>
    </div>
  );
}

// Fills the shared #tickers datalist used by the Add-holding input.
function TickerOptions() {
  const [assets, setAssets] = useState([]);
  useEffect(() => { api.assets().then(setAssets).catch(() => {}); }, []);
  return (
    <datalist id="tickers">
      {assets.map((a) => (
        <option key={a.ticker} value={a.ticker.replace(".EGX", "")}>
          {a.ticker.replace(".EGX", "")} — {a.name}
        </option>
      ))}
    </datalist>
  );
}
