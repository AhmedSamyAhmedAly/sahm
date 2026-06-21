import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { money } from "../format.js";
import NumberInput from "./NumberInput.jsx";

const FEATURES = [
  { ic: "📈", t: "Daily Suggestions", d: "Every trading morning we scan the whole EGX and rank the strongest buy setups — each with an honest, backtested Success %." },
  { ic: "🎯", t: "Clear plan per stock", d: "Every pick comes with an entry, a target and a stop, plus a fresh AI read of the news. You decide and place the trade." },
  { ic: "💼", t: "Your Portfolio", d: "Track the stocks you own with live P/L and earnings, get a sell alert when a signal turns, and split your budget across the best signals." },
  { ic: "💧", t: "Liquid money", d: "Your budget is the free cash you can invest. Buying can subtract from it; selling adds the proceeds back automatically." },
];

const onbEdit = { width: 76, background: "var(--bg)", border: "1px solid var(--border)",
  color: "var(--text)", borderRadius: 6, padding: "5px 7px" };

export default function Onboarding({ open, onClose, onDone }) {
  const { user, setUserBudget } = useAuth();
  const [step, setStep] = useState(0);
  const [budget, setBudget] = useState("");
  const [liquid, setLiquid] = useState(null);
  const [assets, setAssets] = useState([]);
  const [form, setForm] = useState({ ticker: "", buy_price: "", quantity: "", deduct: true });
  const [added, setAdded] = useState([]);
  const [editId, setEditId] = useState(null);
  const [editVals, setEditVals] = useState({ buy_price: "", quantity: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep(0); setErr(""); setAdded([]);
    setForm({ ticker: "", buy_price: "", quantity: "", deduct: true });
    setBudget(user?.budget ? String(user.budget) : "");
    setLiquid(user?.budget ?? null);
    api.assets().then(setAssets).catch(() => {});
  }, [open]);

  if (!open) return null;

  const saveBudget = async () => {
    const nb = Math.max(0, parseFloat(budget) || 0);
    if (nb <= 0) { setErr("Enter a budget greater than 0."); return; }
    setErr(""); setBusy(true);
    try {
      await api.setBudget(nb);
      setUserBudget(nb);
      setLiquid(nb);
      setStep(2);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const syncLiquid = async () => {
    const pf = await api.portfolio();
    setLiquid(pf.budget); setUserBudget(pf.budget);
  };

  const addOne = async () => {
    const price = parseFloat(form.buy_price), qty = parseFloat(form.quantity);
    if (!form.ticker || !(price > 0) || !(qty > 0)) { setErr("Enter a ticker, buy price and quantity."); return; }
    setErr(""); setBusy(true);
    try {
      const h = await api.addHolding(form.ticker, price, qty, form.deduct);
      setAdded((a) => [...a.filter((x) => x.id !== h.id),
        { id: h.id, ticker: h.ticker.replace(".EGX", ""), qty: h.quantity, price: h.buy_price, deduct: form.deduct }]);
      setForm({ ticker: "", buy_price: "", quantity: "", deduct: form.deduct });
      await syncLiquid();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const removeOne = async (id) => {
    setErr(""); setBusy(true);
    try {
      await api.deleteHolding(id);
      setAdded((a) => a.filter((x) => x.id !== id));
      if (editId === id) setEditId(null);
      await syncLiquid();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const startEditOne = (h) => { setEditId(h.id); setEditVals({ buy_price: String(h.price), quantity: String(h.qty) }); };
  const saveEditOne = async (id) => {
    const price = parseFloat(editVals.buy_price), qty = parseFloat(editVals.quantity);
    if (!(price > 0) || !(qty > 0)) { setErr("Enter a valid buy price and quantity."); return; }
    setErr(""); setBusy(true);
    try {
      const h = await api.updateHolding(id, { buy_price: price, quantity: qty });
      setAdded((a) => a.map((x) => (x.id === id ? { ...x, price: h.buy_price, qty: h.quantity } : x)));
      setEditId(null);
      await syncLiquid();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const finish = () => { onClose(); onDone?.(); };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
        <div className="steps-dots">
          {[0, 1, 2].map((i) => <i key={i} className={step >= i ? "on" : ""} />)}
        </div>
        {err && <div className="error">{err}</div>}

        {step === 0 && (
          <>
            <h2>Welcome to Saaed <span style={{ color: "var(--accent)" }}>📈</span></h2>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>
              A quick tour of how Saaed helps you trade the Egyptian Exchange with an honest edge.
            </p>
            {FEATURES.map((f) => (
              <div className="onb-feature" key={f.t}>
                <div className="ic">{f.ic}</div>
                <div><b>{f.t}</b><span>{f.d}</span></div>
              </div>
            ))}
            <p style={{ color: "var(--muted)", fontSize: 12 }}>
              ⚠️ Saaed gives algorithmic <i>suggestions</i> that can be wrong — it tips the odds, it
              doesn't remove risk. Not financial advice.
            </p>
            <div className="modal-actions">
              <button className="ghost" onClick={onClose}>Skip</button>
              <div className="grow" />
              <button className="primary" style={{ width: "auto", padding: "11px 20px" }} onClick={() => setStep(1)}>Next</button>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <h2>Set your budget 💧</h2>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>
              Your <b>liquid money</b> — the cash you want to invest. We use it to suggest how to
              split across the best signals. You can change it any time.
            </p>
            <div className="field">
              <label>Budget (EGP)</label>
              <NumberInput value={budget} step={1000} min={0} placeholder="e.g. 50000"
                autoFocus onChange={setBudget} />
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setStep(0)}>← Back</button>
              <div className="grow" />
              <button className="primary" style={{ width: "auto", padding: "11px 20px" }}
                disabled={busy} onClick={saveBudget}>Next</button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h2>Add stocks you own 💼 <small style={{ color: "var(--muted)", fontWeight: 500, fontSize: 14 }}>(optional)</small></h2>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>
              This step is <b>optional</b> — add what you already hold so we can track P/L and warn you
              when to sell. You can edit or remove these any time, here or on the Portfolio page.
            </p>
            <div className="field" style={{ marginBottom: 10 }}>
              <label>Stock</label>
              <input list="onb-tickers" placeholder="Type or pick a ticker" value={form.ticker}
                onChange={(e) => setForm({ ...form, ticker: e.target.value })} />
              <datalist id="onb-tickers">
                {assets.map((a) => (
                  <option key={a.ticker} value={a.ticker.replace(".EGX", "")}>
                    {a.ticker.replace(".EGX", "")} — {a.name}
                  </option>
                ))}
              </datalist>
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <div className="field" style={{ flex: "1 1 130px" }}>
                <label>Buy price</label>
                <NumberInput value={form.buy_price} step={0.5} min={0}
                  onChange={(v) => setForm({ ...form, buy_price: v })} />
              </div>
              <div className="field" style={{ flex: "1 1 130px" }}>
                <label>Quantity</label>
                <NumberInput value={form.quantity} step={1} min={0}
                  onChange={(v) => setForm({ ...form, quantity: v })} />
              </div>
            </div>
            <label className="checkrow" style={{ marginBottom: 12 }}>
              <input type="checkbox" checked={form.deduct}
                onChange={(e) => setForm({ ...form, deduct: e.target.checked })} />
              💧 Subtract this cost from my liquid budget
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4, flexWrap: "wrap" }}>
              <button className="iconbtn" disabled={busy} onClick={addOne}>➕ Add holding</button>
              {liquid != null && (
                <span style={{ color: "var(--muted)", fontSize: 13 }}>
                  💧 Liquid money left: <b style={{ color: "var(--text)" }}>{money(liquid)}</b> EGP
                </span>
              )}
            </div>
            {added.length > 0 && (
              <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                {added.map((a) => (
                  <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
                    background: "var(--card-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "8px 10px" }}>
                    <b>{a.ticker}</b>
                    {editId === a.id ? (
                      <>
                        <input type="number" step="any" placeholder="price" style={onbEdit}
                          value={editVals.buy_price} onChange={(e) => setEditVals({ ...editVals, buy_price: e.target.value })} />
                        <input type="number" step="any" placeholder="qty" style={onbEdit}
                          value={editVals.quantity} onChange={(e) => setEditVals({ ...editVals, quantity: e.target.value })} />
                        <div style={{ flex: 1 }} />
                        <button className="iconbtn" disabled={busy} onClick={() => saveEditOne(a.id)}>✓ Save</button>
                        <button className="iconbtn" disabled={busy} onClick={() => setEditId(null)}>Cancel</button>
                      </>
                    ) : (
                      <>
                        <span style={{ color: "var(--muted)", fontSize: 13 }}>{a.qty} sh @ {money(a.price)}{a.deduct ? " · 💧" : ""}</span>
                        <div style={{ flex: 1 }} />
                        <button className="iconbtn" disabled={busy} onClick={() => startEditOne(a)}>✏️ Edit</button>
                        <button className="iconbtn" disabled={busy} onClick={() => removeOne(a.id)}>🗑️ Remove</button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
            <div className="modal-actions">
              <button className="ghost" onClick={() => setStep(1)}>← Back</button>
              <div className="grow" />
              <button className="ghost" onClick={finish}>Skip for now</button>
              <button className="primary" style={{ width: "auto", padding: "11px 20px" }} onClick={finish}>
                {added.length ? "Done" : "Finish"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
