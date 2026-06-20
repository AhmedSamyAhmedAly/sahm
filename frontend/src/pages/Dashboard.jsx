import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { SIGNAL_LABEL, money, prob, signed } from "../format.js";

function Kpi({ label, value }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

function NewsChip({ p }) {
  if (p.news_label == null && p.news_sentiment == null)
    return <span style={{ color: "var(--muted)" }}>—</span>;
  const cls = p.news_label === "positive" ? "up" : p.news_label === "negative" ? "down" : "";
  const dot = p.news_label === "positive" ? "🟢" : p.news_label === "negative" ? "🔴" : "➖";
  return (
    <span className={cls} title={p.news_thesis || ""} style={{ whiteSpace: "nowrap" }}>
      {dot} {p.news_catalyst ? "⚡" : ""}
    </span>
  );
}

export default function Dashboard() {
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [track, setTrack] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [signal, setSignal] = useState("");
  const [sort, setSort] = useState("score");

  useEffect(() => {
    api.picks({ limit: 300 }).then(setData).catch((e) => setErr(e.message));
    api.trackRecord().then(setTrack).catch(() => {});
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    let r = data.picks;
    if (signal) r = r.filter((p) => p.signal === signal);
    if (q) {
      const s = q.toLowerCase();
      r = r.filter(
        (p) => p.ticker.toLowerCase().includes(s) || (p.name || "").toLowerCase().includes(s)
      );
    }
    r = [...r].sort((a, b) => {
      if (sort === "prob") return (b.success_prob || 0) - (a.success_prob || 0);
      if (sort === "rr") return (b.risk_reward || 0) - (a.risk_reward || 0);
      return b.score - a.score;
    });
    return r;
  }, [data, q, signal, sort]);

  if (err) return <div className="container"><div className="error">{err}</div></div>;
  if (!data) return <div className="loading">Loading picks…</div>;

  const strongBuys = data.picks.filter((p) => p.signal === "strong_buy").length;
  const winRate = track?.live_win_rate;

  return (
    <div className="container wide">
      <div className="kpis">
        <Kpi label="Stocks scanned" value={data.active_count} />
        <Kpi label="Strong buys today" value={strongBuys} />
        <Kpi
          label="Live win rate"
          value={winRate == null ? "—" : `${Math.round(winRate * 100)}%`}
        />
        <Kpi label="Last update" value={data.date || "—"} />
      </div>

      <div className="card">
        <div className="toolbar">
          <strong style={{ fontSize: 16 }}>Today's Buys</strong>
          <span className="pill">{rows.length} shown</span>
          <div className="spacer" style={{ flex: 1 }} />
          <input placeholder="Search ticker / name" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={signal} onChange={(e) => setSignal(e.target.value)}>
            <option value="">All signals</option>
            <option value="strong_buy">Strong buy</option>
            <option value="buy">Buy</option>
            <option value="hold">Hold</option>
            <option value="sell">Sell</option>
            <option value="strong_sell">Strong sell</option>
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="score">Sort: Score</option>
            <option value="prob">Sort: Success %</option>
            <option value="rr">Sort: Risk/Reward</option>
          </select>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="responsive">
            <thead>
              <tr>
                <th>#</th>
                <th>Stock</th>
                <th>Signal</th>
                <th>News</th>
                <th>Score</th>
                <th>Success</th>
                <th>Goal</th>
                <th className="num">Entry</th>
                <th className="num">Target</th>
                <th className="num">Stop</th>
                <th className="num hide-sm" title="Risk : Reward — potential gain vs. potential loss. Higher is better.">R:R</th>
                <th className="num hide-sm">Hold</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.ticker} onClick={() => nav(`/stocks/${p.ticker}`)}>
                  <td className="num" data-label="#">{p.rank}</td>
                  <td className="tickercell" data-label="Stock">
                    {p.ticker.replace(".EGX", "")}
                    <small>{p.name}</small>
                  </td>
                  <td data-label="Signal">
                    <span className={`badge ${p.signal}`}>{SIGNAL_LABEL[p.signal]}</span>
                  </td>
                  <td data-label="News"><NewsChip p={p} /></td>
                  <td data-label="Score">
                    <div className="scorebar">
                      <i style={{ width: `${p.score}%` }} />
                    </div>
                    <small style={{ color: "var(--muted)" }}>{p.score}</small>
                  </td>
                  <td className="prob" data-label="Success">
                    <b>{prob(p.success_prob)}</b>
                  </td>
                  <td data-label="Goal">
                    <small style={{ color: "var(--muted)" }}>
                      +{Math.round((p.target_pct || 0) * 100)}% / {p.horizon_days}d
                    </small>
                  </td>
                  <td className="num" data-label="Entry">{money(p.entry_price)}</td>
                  <td className="num up" data-label="Target">{money(p.target_price)}</td>
                  <td className="num down" data-label="Stop">{money(p.stop_loss)}</td>
                  <td className="num hide-sm" data-label="R:R">{p.risk_reward ?? "—"}</td>
                  <td className="num hide-sm" data-label="Hold">
                    {p.expected_hold_days ? `~${Math.round(p.expected_hold_days)}d` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="disclaimer">
        <b>Success %</b> is the historical, backtested hit-rate for stocks in the same score band —
        not a guarantee. Educational/research tool, <b>not financial advice</b>.
      </p>
    </div>
  );
}
