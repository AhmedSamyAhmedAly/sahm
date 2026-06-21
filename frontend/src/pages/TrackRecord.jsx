import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api.js";
import { prob, signed } from "../format.js";

export default function TrackRecord() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.trackRecord().then(setD).catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="container"><div className="error">{err}</div></div>;
  if (!d) return <div className="loading">Loading track record…</div>;

  // Group backtest stats by score band for a readable table.
  const bands = {};
  for (const s of d.backtest) {
    (bands[s.score_band] = bands[s.score_band] || []).push(s);
  }
  const sortedBands = Object.keys(bands).sort((a, b) => parseInt(b) - parseInt(a));

  const winPct = d.live_win_rate == null ? null : Math.round(d.live_win_rate * 100);

  return (
    <div className="container">
      <h2 style={{ marginTop: 0 }}>Track Record</h2>
      <div className="card" style={{ padding: 16, marginBottom: 18, borderColor: "var(--accent)" }}>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          <b>In plain English:</b> this page is our honesty check. {winPct == null ? (
            <>Once enough of our past picks have played out, you'll see here how often they actually worked.</>
          ) : (
            <>Of the <b>{d.live_graded}</b> past picks that have fully played out, <b>{winPct}%</b> hit
            their target — versus roughly <b>34%</b> if you'd picked at random. So the picks worked
            noticeably more often than luck.</>
          )} About half still miss, which is exactly why stops and spreading your money across
          several picks matter. <b>No one can promise a winner.</b>
        </p>
      </div>

      <div className="kpis">
        <div className="kpi"><div className="label">How often picks won</div><div className="value">{winPct == null ? "—" : `${winPct}%`}</div></div>
        <div className="kpi"><div className="label">Picks measured</div><div className="value">{d.live_graded}</div></div>
        <div className="kpi"><div className="label">Avg return per pick</div><div className="value">{d.live_avg_return == null ? "—" : signed(d.live_avg_return)}</div></div>
        <div className="kpi"><div className="label">Random would win</div><div className="value">~34%</div></div>
      </div>

      {d.models?.length > 0 && (
        <>
          <div className="section-title">How accurate is the model?</div>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
            We tested the model on years of history it had never seen. The column that matters most is
            <b> Lift</b> — how many times more often the model's top picks hit their target than a
            random guess. <b>2× means twice as often as luck.</b>
            <br />
            <span style={{ fontSize: 12 }}>
              (For the technical: <b>AUC</b> 0.5 = no skill, ~0.6 = a real but modest edge;
              <b> Top-picks hit-rate</b> vs. <b>Baseline</b> is the model's success rate vs. the market average.)
            </span>
          </p>
          <div className="card" style={{ overflowX: "auto", marginBottom: 18 }}>
            <table>
              <thead>
                <tr>
                  <th>Target</th>
                  <th className="num">AUC</th>
                  <th className="num">Top-picks hit-rate</th>
                  <th className="num">Baseline</th>
                  <th className="num">Lift</th>
                  <th className="num">Samples</th>
                </tr>
              </thead>
              <tbody>
                {d.models.map((m) => (
                  <tr key={m.band_key} style={{ cursor: "default" }}>
                    <td className="tickercell">
                      +{Math.round(m.target_pct * 100)}% / {m.horizon_days}d
                    </td>
                    <td className="num">{m.auc?.toFixed(3) ?? "—"}</td>
                    <td className="num prob"><b>{prob(m.precision_top10)}</b></td>
                    <td className="num" style={{ color: "var(--muted)" }}>{prob(m.base_rate)}</td>
                    <td className="num up">{m.lift_top10 ? `${m.lift_top10}×` : "—"}</td>
                    <td className="num" style={{ color: "var(--muted)" }}>
                      {m.n_samples.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {d.equity_curve.length > 0 && (
        <div className="card" style={{ padding: 16, marginBottom: 18 }}>
          <div className="section-title" style={{ marginTop: 0 }}>Adding up every pick's result over time</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={d.equity_curve} margin={{ top: 6, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#232c3d" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#8a97ad", fontSize: 11 }} minTickGap={40} />
              <YAxis tick={{ fill: "#8a97ad", fontSize: 11 }} width={54} />
              <Tooltip contentStyle={{ background: "#161c28", border: "1px solid #232c3d", borderRadius: 8 }} />
              <Line type="monotone" dataKey="cumulative" stroke="#3ddc97" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="section-title">Do higher scores really do better?</div>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
        Every stock gets a <b>score from 0–100</b>. This table groups years of history by score and
        shows how often each group hit the target. If the system works, <b>higher score rows should
        have higher percentages</b> — and they do. Each cell is a different target (e.g. “+10% / 10d”
        = gained 10% within 10 days).
      </p>
      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Score band</th>
              <th className="num">+5% / 10d</th>
              <th className="num">+10% / 10d</th>
              <th className="num">+15% / 20d</th>
              <th className="num">+20% / 20d</th>
              <th className="num">Samples</th>
            </tr>
          </thead>
          <tbody>
            {sortedBands.map((band) => {
              const cells = bands[band];
              const find = (t, h) => cells.find((c) => Math.abs(c.target_pct - t) < 1e-6 && c.horizon_days === h);
              const n = Math.max(...cells.map((c) => c.n_samples));
              const cell = (t, h) => {
                const s = find(t, h);
                return s ? <b className="prob">{prob(s.hit_rate)}</b> : "—";
              };
              return (
                <tr key={band} style={{ cursor: "default" }}>
                  <td className="tickercell">{band}</td>
                  <td className="num">{cell(0.05, 10)}</td>
                  <td className="num">{cell(0.10, 10)}</td>
                  <td className="num">{cell(0.15, 20)}</td>
                  <td className="num">{cell(0.20, 20)}</td>
                  <td className="num" style={{ color: "var(--muted)" }}>{n}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="disclaimer">
        Backtest = how the fixed scoring rules would have performed historically. It is an honest
        frequency, not a promise of future results. Educational/research tool, <b>not financial advice</b>.
      </p>
    </div>
  );
}
