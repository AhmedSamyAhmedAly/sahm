import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api.js";
import { SIGNAL_LABEL, money, prob, signed } from "../format.js";

const TIMEFRAMES = [
  { label: "1D", days: 1 }, { label: "1W", days: 7 }, { label: "1M", days: 30 },
  { label: "6M", days: 182 }, { label: "1Y", days: 365 },
];

export default function StockDetail() {
  const { ticker } = useParams();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [tf, setTf] = useState(TIMEFRAMES[3]); // default 6M

  useEffect(() => {
    api.stock(ticker).then(setD).catch((e) => setErr(e.message));
  }, [ticker]);

  const chart = useMemo(() => {
    if (!d) return [];
    const all = d.bars.map((b) => ({ date: b.date, open: b.open, close: b.close }));
    if (!all.length) return all;
    const last = new Date(all[all.length - 1].date);
    const cutoff = new Date(last);
    cutoff.setDate(cutoff.getDate() - tf.days);
    const filtered = all.filter((b) => new Date(b.date) >= cutoff);
    return filtered.length >= 2 ? filtered : all.slice(-2); // keep at least 2 points to draw
  }, [d, tf]);

  if (err) return <div className="container"><div className="error">{err}</div></div>;
  if (!d) return <div className="loading">Loading {ticker}…</div>;

  const p = d.latest;
  const fewPoints = chart.length <= 3;

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
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            <div className="section-title" style={{ margin: 0 }}>Price — open &amp; close</div>
            <div style={{ flex: 1 }} />
            {TIMEFRAMES.map((t) => (
              <button key={t.label} className="iconbtn" onClick={() => setTf(t)}
                style={tf.label === t.label ? { borderColor: "var(--accent)", color: "var(--accent)" } : {}}>
                {t.label}
              </button>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chart} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3ddc97" stopOpacity={0.35} />
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
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="close" name="Close" stroke="#3ddc97" strokeWidth={2}
                fill="url(#g)" dot={fewPoints} />
              <Line type="monotone" dataKey="open" name="Open" stroke="#4aa8ff" strokeWidth={1.5}
                strokeDasharray="4 3" dot={fewPoints} />
            </ComposedChart>
          </ResponsiveContainer>
          <p style={{ color: "var(--muted)", fontSize: 12, margin: "6px 0 0" }}>
            End-of-day data — each point is one trading session’s open and close.
          </p>
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
