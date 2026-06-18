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

  return (
    <div className="container">
      <div className="kpis">
        <div className="kpi"><div className="label">Live win rate</div><div className="value">{d.live_win_rate == null ? "—" : `${Math.round(d.live_win_rate * 100)}%`}</div></div>
        <div className="kpi"><div className="label">Graded calls</div><div className="value">{d.live_graded}</div></div>
        <div className="kpi"><div className="label">Avg return / call</div><div className="value">{d.live_avg_return == null ? "—" : signed(d.live_avg_return)}</div></div>
        <div className="kpi"><div className="label">Backtest cells</div><div className="value">{d.backtest.length}</div></div>
      </div>

      {d.equity_curve.length > 0 && (
        <div className="card" style={{ padding: 16, marginBottom: 18 }}>
          <div className="section-title" style={{ marginTop: 0 }}>Cumulative realized return (graded calls)</div>
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

      <div className="section-title">Backtested success rate by score band</div>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
        The honest numbers: across years of history, how often did stocks in each score band reach
        the target within the horizon. Higher score bands should show higher hit-rates.
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
