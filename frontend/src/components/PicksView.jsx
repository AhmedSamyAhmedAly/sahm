import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { SIGNAL_LABEL, money, prob } from "../format.js";

const BANDS = [
  { key: "auto", label: "Auto — best profit / time", target: null, horizon: null },
  { key: "t3_h40", label: "Target: +3% in 40d", target: 0.03, horizon: 40 },
  { key: "t5_h30", label: "Target: +5% in 30d", target: 0.05, horizon: 30 },
  { key: "t10_h10", label: "Target: +10% in 10d", target: 0.1, horizon: 10 },
];

const CONF = [
  { key: "0", label: "Any confidence", min: 0 },
  { key: "0.8", label: "≥ 80% confident", min: 0.8 },
  { key: "0.85", label: "≥ 85% confident", min: 0.85 },
];

const BUY_SIGNALS = ["buy", "strong_buy", "super_strong_buy"];

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

export default function PicksView({
  suggestionsOnly = false, showKpis = false, minimal = false, title = "Stocks", tab = null,
}) {
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [track, setTrack] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [signal, setSignal] = useState("");
  const [sort, setSort] = useState("rank");
  const [dir, setDir] = useState("asc");
  // In tab mode the band/confidence/signal are fixed by the tab preset and the
  // selectors are hidden; otherwise the user drives them.
  const [band, setBand] = useState(tab ? (tab.band || BANDS[0]) : BANDS[0]);
  const [conf, setConf] = useState(tab ? { min: tab.minConf || 0 } : CONF[0]);

  useEffect(() => {
    const params = { limit: 400 };
    if (band.target != null) { params.target = band.target; params.horizon = band.horizon; }
    api.picks(params).then(setData).catch((e) => setErr(e.message));
  }, [band]);

  useEffect(() => {
    if (showKpis) api.trackRecord().then(setTrack).catch(() => {});
  }, [showKpis]);

  const rows = useMemo(() => {
    if (!data) return [];
    let r = data.picks;
    if (tab) r = r.filter((p) => (tab.ratings || BUY_SIGNALS).includes(p.signal));
    else if (suggestionsOnly) r = r.filter((p) => BUY_SIGNALS.includes(p.signal));
    if (signal) r = r.filter((p) => p.signal === signal);
    if (conf.min > 0) r = r.filter((p) => (p.success_prob || 0) >= conf.min);
    if (q) {
      const s = q.toLowerCase();
      r = r.filter((p) => p.ticker.toLowerCase().includes(s) || (p.name || "").toLowerCase().includes(s));
    }
    if (minimal) {
      r = [...r].sort((a, b) => (a.name || a.ticker).localeCompare(b.name || b.ticker));
    } else {
      const cmp = (a, b) => {
        if (sort === "rank") return (a.rank || 0) - (b.rank || 0);
        if (sort === "prob") return (a.success_prob || 0) - (b.success_prob || 0);
        if (sort === "rr") return (a.risk_reward || 0) - (b.risk_reward || 0);
        if (sort === "name") return (a.name || a.ticker).localeCompare(b.name || b.ticker);
        return (a.score || 0) - (b.score || 0);
      };
      const sign = dir === "asc" ? 1 : -1;
      r = [...r].sort((a, b) => sign * cmp(a, b));
    }
    return r;
  }, [data, q, signal, conf, sort, dir, suggestionsOnly, minimal, tab]);

  if (err) return <div className="container"><div className="error">{err}</div></div>;
  if (!data) return <div className="loading">Loading…</div>;

  const strongBuys = data.picks.filter(
    (p) => p.signal === "strong_buy" || p.signal === "super_strong_buy").length;
  const superBuys = data.picks.filter((p) => p.signal === "super_strong_buy").length;
  const winRate = track?.live_win_rate;

  return (
    <div className="container wide">
      {showKpis && (
        <div className="kpis">
          <Kpi label="Stocks scanned" value={data.active_count} />
          <Kpi label="Strong buys today" value={superBuys ? `${strongBuys} · ${superBuys} super` : strongBuys} />
          <Kpi label="Live win rate" value={winRate == null ? "—" : `${Math.round(winRate * 100)}%`} />
          <Kpi label="Last update" value={data.date || "—"} />
        </div>
      )}

      <div className="card">
        <div className="toolbar">
          <div>
            <strong style={{ fontSize: 16 }}>{title}</strong>
            {tab?.sub && <div style={{ color: "var(--muted)", fontSize: 12 }}>{tab.sub}</div>}
          </div>
          <span className="pill">{rows.length} shown</span>
          <div className="spacer" style={{ flex: 1 }} />
          <input placeholder="Search ticker / name" value={q} onChange={(e) => setQ(e.target.value)} />
          {!minimal && !tab && (
            <select value={band.key} onChange={(e) => setBand(BANDS.find((b) => b.key === e.target.value))}>
              {BANDS.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}
            </select>
          )}
          {!minimal && !tab && (
            <select value={conf.key} onChange={(e) => setConf(CONF.find((c) => c.key === e.target.value))}>
              {CONF.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
          )}
          {!minimal && !tab && (
            <select value={signal} onChange={(e) => setSignal(e.target.value)}>
              {suggestionsOnly ? (
                <>
                  <option value="">All buys</option>
                  <option value="super_strong_buy">Super strong buy</option>
                  <option value="strong_buy">Strong buy</option>
                  <option value="buy">Buy</option>
                </>
              ) : (
                <>
                  <option value="">All signals</option>
                  <option value="super_strong_buy">Super strong buy</option>
                  <option value="strong_buy">Strong buy</option>
                  <option value="buy">Buy</option>
                  <option value="hold">Hold</option>
                  <option value="sell">Sell</option>
                  <option value="strong_sell">Strong sell</option>
                  <option value="super_strong_sell">Super strong sell</option>
                </>
              )}
            </select>
          )}
          {!minimal && (
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="rank">Sort: # (rank)</option>
              <option value="score">Sort: Score</option>
              <option value="prob">Sort: Success %</option>
              <option value="rr">Sort: Risk/Reward</option>
              <option value="name">Sort: Stock name</option>
            </select>
          )}
          {!minimal && (
            <button type="button" className="iconbtn" onClick={() => setDir((d) => (d === "desc" ? "asc" : "desc"))}
              title={dir === "desc" ? "Descending (high → low)" : "Ascending (low → high)"}
              style={{ minWidth: 96 }}>
              {dir === "desc" ? "↓ High–Low" : "↑ Low–High"}
            </button>
          )}
        </div>

        {!minimal && (
          <div className="legend">
            <span className="legend-title">News</span>
            <span>🟢 positive</span>
            <span>🔴 negative</span>
            <span>➖ neutral</span>
            <span title="A strong, recent event (earnings, a big contract, a deal, a payout…) that can move the price soon.">
              ⚡ catalyst
            </span>
            <span>— not analysed</span>
          </div>
        )}

        <div style={{ overflowX: "auto" }}>
          {minimal ? (
            <table className="responsive">
              <thead><tr><th>#</th><th>Stock</th></tr></thead>
              <tbody>
                {rows.map((p, i) => (
                  <tr key={p.ticker} onClick={() => nav(`/stocks/${p.ticker}`)}>
                    <td className="num" data-label="#">{i + 1}</td>
                    <td className="tickercell" data-label="Stock">
                      {p.ticker.replace(".EGX", "")}<small>{p.name}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="responsive">
              <thead>
                <tr>
                  <th>#</th><th>Stock</th><th>Signal</th><th>News</th><th>Score</th>
                  <th>Success</th><th className="num">Entry</th><th className="num">Target</th>
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
                      {p.ticker.replace(".EGX", "")}<small>{p.name}</small>
                    </td>
                    <td data-label="Signal">
                      {p.signal
                        ? <span className={`badge ${p.signal}`}>{SIGNAL_LABEL[p.signal]}</span>
                        : <span className="pill" title="Did not pass the scan filters — data only">data only</span>}
                    </td>
                    <td data-label="News"><NewsChip p={p} /></td>
                    <td data-label="Score">
                      {p.score == null ? (
                        <small style={{ color: "var(--muted)" }}>—</small>
                      ) : (
                        <>
                          <div className="scorebar"><i style={{ width: `${p.score}%` }} /></div>
                          <small style={{ color: "var(--muted)" }}>{p.score}</small>
                        </>
                      )}
                    </td>
                    <td className="prob" data-label="Success"><b>{prob(p.success_prob)}</b></td>
                    <td className="num" data-label="Entry">{money(p.entry_price ?? p.last_close)}</td>
                    <td className="num up" data-label="Target">
                      {money(p.target_price)}
                      {p.target_pct ? (
                        <small style={{ display: "block", color: "var(--muted)" }}>
                          +{Math.round(p.target_pct * 100)}% / {p.horizon_days}d
                        </small>
                      ) : null}
                    </td>
                    <td className="num down" data-label="Stop">{money(p.stop_loss)}</td>
                    <td className="num hide-sm" data-label="R:R">{p.risk_reward ?? "—"}</td>
                    <td className="num hide-sm" data-label="Hold">
                      {p.expected_hold_days ? `~${Math.round(p.expected_hold_days)}d` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <p className="disclaimer">
        {minimal
          ? "Browse the full EGX universe. Tap a stock for details. "
          : "Success is the historical, backtested/ML hit-rate for stocks in the same score band — not a guarantee. "}
        Stocks marked <b>“data only”</b> didn’t pass our liquidity/history filters, so we show their
        latest price but make <b>no prediction</b> for them. Sell/hold signals for stocks you own
        appear on your Portfolio. Educational/research tool, <b>not financial advice</b>.
      </p>
    </div>
  );
}
