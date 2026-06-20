import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api.js";
import { SIGNAL_LABEL, money, prob, signed } from "../format.js";

export default function StockDetail() {
  const { ticker } = useParams();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.stock(ticker).then(setD).catch((e) => setErr(e.message));
  }, [ticker]);

  if (err) return <div className="container"><div className="error">{err}</div></div>;
  if (!d) return <div className="loading">Loading {ticker}…</div>;

  const p = d.latest;
  const chart = d.bars.map((b) => ({ date: b.date, close: b.close }));

  return (
    <div className="container">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <button className="ghost" onClick={() => nav(-1)}>← Back</button>
        <h2 style={{ margin: 0 }}>
          {ticker.replace(".EGX", "")} <span style={{ color: "var(--muted)", fontWeight: 500, fontSize: 16 }}>{d.name}</span>
        </h2>
        <div style={{ flex: 1 }} />
      </div>

      <div className="detail-grid">
        <div className="card" style={{ padding: 16 }}>
          <div className="section-title" style={{ marginTop: 0 }}>Price (last {chart.length} days)</div>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={chart} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3ddc97" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#3ddc97" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#232c3d" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#8a97ad", fontSize: 11 }} minTickGap={40} />
              <YAxis domain={["auto", "auto"]} tick={{ fill: "#8a97ad", fontSize: 11 }} width={54} />
              <Tooltip
                contentStyle={{ background: "#161c28", border: "1px solid #232c3d", borderRadius: 8 }}
                labelStyle={{ color: "#8a97ad" }}
              />
              <Area type="monotone" dataKey="close" stroke="#3ddc97" strokeWidth={2} fill="url(#g)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div>
          {d.components && (
            <div className="card" style={{ padding: 16 }}>
              <div className="section-title" style={{ marginTop: 0 }}>Score breakdown</div>
              {Object.entries(d.components).map(([k, v]) => (
                <div key={k} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                    <span style={{ textTransform: "capitalize", color: "var(--muted)" }}>{k}</span>
                    <span>{v}</span>
                  </div>
                  <div className="scorebar" style={{ width: "100%" }}><i style={{ width: `${v}%` }} /></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {p?.reasons?.length > 0 && (
        <>
          <div className="section-title">Why this pick</div>
          <div className="card" style={{ padding: "8px 20px" }}>
            <ul className="reasons">
              {p.reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        </>
      )}

      {(p?.news_label || d.news?.headlines?.length) && (
        <>
          <div className="section-title">News &amp; sentiment</div>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className={`badge ${p?.news_label === "positive" ? "strong_buy" : p?.news_label === "negative" ? "sell" : "hold"}`}>
                {(p?.news_label || "neutral").toUpperCase()}
              </span>
              {p?.news_catalyst && <span className="pill" style={{ color: "var(--amber)" }}>⚡ catalyst</span>}
              {d.news?.risk_flag && <span className="pill" style={{ color: "var(--red)" }}>⚠ risk</span>}
              {d.news?.engine && d.news.engine !== "keyword" && d.news.engine !== "none" && (
                <span className="pill">AI: {d.news.engine}</span>
              )}
            </div>
            {p?.news_thesis && <p style={{ marginBottom: 8 }}>{p.news_thesis}</p>}
            <ul className="reasons" style={{ marginTop: 4 }}>
              {(d.news?.headlines || []).map((h, i) => (
                <li key={i}>
                  <a href={h.url} target="_blank" rel="noreferrer">{h.title}</a>{" "}
                  <small style={{ color: "var(--muted)" }}>{h.source}</small>
                </li>
              ))}
              {(!d.news?.headlines || d.news.headlines.length === 0) && (
                <li style={{ color: "var(--muted)" }}>No recent headlines found.</li>
              )}
            </ul>
            <p className="disclaimer" style={{ marginTop: 8 }}>
              Live news signal — <b>separate from the backtested Success %</b>. It nudges ranking
              slightly and flags catalysts; it does not change the model's probability.
            </p>
          </div>
        </>
      )}

      <div className="section-title">Past calls &amp; outcomes</div>
      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Date</th><th>Signal</th><th>Score</th>
              <th className="num">Entry</th><th>Result</th><th className="num">Return</th><th className="num">Days</th>
            </tr>
          </thead>
          <tbody>
            {d.history.length === 0 && (
              <tr><td colSpan={7} style={{ color: "var(--muted)" }}>No graded history yet.</td></tr>
            )}
            {d.history.map((h, i) => (
              <tr key={i} style={{ cursor: "default" }}>
                <td>{h.date}</td>
                <td><span className={`badge ${h.signal}`}>{SIGNAL_LABEL[h.signal]}</span></td>
                <td>{h.score}</td>
                <td className="num">{money(h.entry_price)}</td>
                <td>{h.hit_target == null ? <span className="pill">open</span> : h.hit_target ? <span className="up">✓ hit target</span> : <span className="down">✗ missed</span>}</td>
                <td className={`num ${(h.return_pct ?? 0) >= 0 ? "up" : "down"}`}>{h.return_pct == null ? "—" : signed(h.return_pct)}</td>
                <td className="num">{h.days_to_target ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
