import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { money, signed } from "../format.js";
import { useMarket, currencyForTicker } from "../market.jsx";
import { usePositions, positionStatus } from "../positions.js";
import TickerPicker from "../components/TickerPicker.jsx";

function fmt(x, cur) {
  if (x == null) return "—";
  return cur === "$" ? `$${money(x)}` : `${money(x)} ${cur}`;
}

const BLANK = { ticker: "", shares: "", buyPrice: "", stop: "", target: "", horizon: "" };

export default function Positions() {
  const nav = useNavigate();
  const { market } = useMarket();
  const { positions, add, remove } = usePositions();
  const [prices, setPrices] = useState({});
  const [form, setForm] = useState(BLANK);


  // Pull the latest price for every held ticker (few positions → a few calls).
  const tickers = useMemo(() => [...new Set(positions.map((p) => p.ticker))], [positions]);
  useEffect(() => {
    let cancelled = false;
    Promise.all(
      tickers.map((t) =>
        api.stock(t).then((d) => [t, d.bars?.length ? d.bars[d.bars.length - 1].close : null]).catch(() => [t, null])
      )
    ).then((pairs) => {
      if (!cancelled) setPrices(Object.fromEntries(pairs));
    });
    return () => { cancelled = true; };
  }, [tickers.join(",")]);

  const submit = (e) => {
    e.preventDefault();
    const ticker = form.ticker.trim().toUpperCase();
    if (!ticker || !form.shares || !form.buyPrice) return;
    add({
      ticker,
      shares: Number(form.shares),
      buyPrice: Number(form.buyPrice),
      stop: form.stop ? Number(form.stop) : null,
      target: form.target ? Number(form.target) : null,
      horizon: form.horizon ? Number(form.horizon) : null,
      date: new Date().toISOString().slice(0, 10),
    });
    setForm(BLANK);
  };

  // Portfolio totals.
  const totals = positions.reduce(
    (acc, p) => {
      const price = prices[p.ticker];
      acc.cost += p.buyPrice * p.shares;
      if (price != null) { acc.value += price * p.shares; acc.priced = true; }
      return acc;
    },
    { cost: 0, value: 0, priced: false }
  );
  const pl = totals.value - totals.cost;

  return (
    <div className="container wide">
      <h2 style={{ marginTop: 0 }}>My positions</h2>
      <p style={{ color: "var(--muted)", marginTop: -6 }}>
        Track what you own. This <b>watches your exits</b> — it flags when a stock hits your
        target, breaks your stop, or overstays its plan. Selling well is half the game.
      </p>

      {positions.length > 0 && (
        <div className="kpis" style={{ marginBottom: 14 }}>
          <div className="kpi"><div className="label">Invested</div><div className="value">{fmt(totals.cost, "")}</div></div>
          <div className="kpi"><div className="label">Current value</div><div className="value">{totals.priced ? fmt(totals.value, "") : "—"}</div></div>
          <div className="kpi">
            <div className="label">Profit / loss</div>
            <div className={`value ${pl >= 0 ? "up" : "down"}`}>{totals.priced ? fmt(pl, "") : "—"}</div>
          </div>
          <div className="kpi">
            <div className="label">Return</div>
            <div className={`value ${pl >= 0 ? "up" : "down"}`}>
              {totals.priced && totals.cost ? signed((pl / totals.cost) * 100) : "—"}
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ overflowX: "auto", marginBottom: 14 }}>
        {positions.length === 0 ? (
          <p style={{ color: "var(--muted)", margin: 8 }}>
            No positions yet. Add one below, or open any stock and use <b>“I bought this”</b> on its
            trade plan to track it here.
          </p>
        ) : (
          <table className="responsive">
            <thead>
              <tr>
                <th>Stock</th><th className="num">Shares</th><th className="num">Buy</th>
                <th className="num">Now</th><th className="num">P/L</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const cur = currencyForTicker(p.ticker);
                const price = prices[p.ticker];
                const plv = price != null ? (price - p.buyPrice) * p.shares : null;
                const plpct = price != null ? (price / p.buyPrice - 1) * 100 : null;
                const st = positionStatus(p, price);
                return (
                  <tr key={p.id}>
                    <td className="tickercell" onClick={() => nav(`/stocks/${p.ticker}`)} style={{ cursor: "pointer" }}>
                      {p.ticker.split(".")[0]}<small>bought {p.date}</small>
                    </td>
                    <td className="num" data-label="Shares">{p.shares}</td>
                    <td className="num" data-label="Buy">{fmt(p.buyPrice, cur)}</td>
                    <td className="num" data-label="Now">{fmt(price, cur)}</td>
                    <td className={`num ${plv >= 0 ? "up" : "down"}`} data-label="P/L">
                      {plv == null ? "—" : <>{fmt(plv, cur)}<small style={{ display: "block", color: "var(--muted)" }}>{signed(plpct)}</small></>}
                    </td>
                    <td data-label="Status">
                      <span className={`badge ${st.kind === "stop" ? "sell" : st.kind === "target" ? "strong_buy" : st.kind === "time" ? "hold" : ""}`}
                        style={st.kind === "hold" ? { background: "transparent", color: "var(--muted)" } : {}}>
                        {st.label}
                      </span>
                    </td>
                    <td><button className="iconbtn" onClick={() => remove(p.id)} title="Remove">✕</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div className="section-title" style={{ marginTop: 0 }}>Add a position</div>
        <form onSubmit={submit} className="pos-form">
          <label style={{ minWidth: 240 }}>Ticker
            <TickerPicker value={form.ticker} market={market}
              onChange={(t) => setForm({ ...form, ticker: t })} />
          </label>
          <label>Shares<input type="number" min="0" value={form.shares}
            onChange={(e) => setForm({ ...form, shares: e.target.value })} /></label>
          <label>Buy price<input type="number" min="0" step="any" value={form.buyPrice}
            onChange={(e) => setForm({ ...form, buyPrice: e.target.value })} /></label>
          <label>Stop (optional)<input type="number" min="0" step="any" value={form.stop}
            onChange={(e) => setForm({ ...form, stop: e.target.value })} /></label>
          <label>Target (optional)<input type="number" min="0" step="any" value={form.target}
            onChange={(e) => setForm({ ...form, target: e.target.value })} /></label>
          <label>Plan days (optional)<input type="number" min="0" value={form.horizon}
            onChange={(e) => setForm({ ...form, horizon: e.target.value })} /></label>
          <button type="submit" className="primary">Add</button>
        </form>
      </div>

      <p className="disclaimer" style={{ marginTop: 12 }}>
        Prices are end-of-day. Alerts are reminders to <b>review</b>, not automatic trades — you place
        every buy/sell yourself in your broker. Not financial advice.
      </p>
    </div>
  );
}
