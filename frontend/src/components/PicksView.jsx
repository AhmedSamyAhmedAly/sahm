import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useMarket, currencyForTicker } from "../market.jsx";
import { groupOf, groupLabel, money, prob } from "../format.js";
import { baseRateMap, baseRateFor as baseRateForMap } from "./BandPill.jsx";

const BUY_GROUPS = ["strong_buy", "buy"];

// Money with the market's currency ($ before the number, EGP after it).
function fmt(x, cur) {
  if (x == null) return "—";
  return cur === "$" ? `$${money(x)}` : `${money(x)} ${cur}`;
}

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

// "Easy to trade" flag — a stand-in for how tight the spread is (Point 3).
const LIQ = {
  high: { label: "Easy", cls: "liq-high", tip: "Heavily traded — tight spread, easy to buy/sell." },
  ok: { label: "OK", cls: "liq-ok", tip: "Reasonably traded — a small spread cost." },
  thin: { label: "Thin ⚠", cls: "liq-thin", tip: "Thinly traded — WIDE spread; you can lose 1–2% just entering. Trade with care or skip." },
};
function LiquidityChip({ p }) {
  const l = LIQ[p.liquidity];
  if (!l) return <span style={{ color: "var(--muted)" }}>—</span>;
  return <span className={`pill ${l.cls}`} title={l.tip}>{l.label}</span>;
}

/**
 * mode: "suggestions" (buy-rated, full detail + pills) | "all" (whole universe, browse)
 */
export default function PicksView({ mode = "suggestions", showKpis = false, title = "Suggestions" }) {
  const nav = useNavigate();
  const { market, current } = useMarket();
  const [data, setData] = useState(null);
  const [track, setTrack] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("rank");
  const [dir, setDir] = useState("desc");   // desc = best/strongest first
  const isAll = mode === "all";

  useEffect(() => {
    setData(null);
    setErr("");
    api.picks({ limit: 500, market }).then(setData).catch((e) => setErr(e.message));
    api.trackRecord().then(setTrack).catch(() => {});
  }, [market]);

  // Base hit-rate ("luck") per band, from the model metrics — for the edge coloring.
  const baseRates = useMemo(() => baseRateMap(track), [track]);

  // The engine's headline target for a pick (best profit-per-day that clears its
  // confidence floor). Per-stock alternatives live on the stock detail page.
  const targetFor = (p) => ({
    pct: p.target_pct, days: p.horizon_days, price: p.target_price, prob: p.success_prob,
  });

  const rows = useMemo(() => {
    if (!data) return [];
    let r = data.picks;
    if (!isAll) r = r.filter((p) => BUY_GROUPS.includes(groupOf(p.signal)));
    if (q) {
      const s = q.toLowerCase();
      r = r.filter((p) => p.ticker.toLowerCase().includes(s) || (p.name || "").toLowerCase().includes(s));
    }
    if (isAll) {
      r = [...r].sort((a, b) => (a.name || a.ticker).localeCompare(b.name || b.ticker));
    } else {
      // Conviction order for the 4 displayed tiers; unscored rows sink last.
      const SIGNAL_ORDER = { strong_buy: 0, buy: 1, hold: 2, sell: 3 };
      const cmp = (a, b) => {
        if (sort === "signal") {
          const d = (SIGNAL_ORDER[groupOf(a.signal)] ?? 9) - (SIGNAL_ORDER[groupOf(b.signal)] ?? 9);
          // Same tier -> keep the confidence order within it.
          return d !== 0 ? d : (a.rank || 0) - (b.rank || 0);
        }
        if (sort === "name") return (a.name || a.ticker).localeCompare(b.name || b.ticker);
        return (a.rank || 0) - (b.rank || 0);
      };
      // "desc" is the natural reading of each sort (best first, strongest signal
      // first, A-Z); flipping reverses whichever is active.
      const sign = dir === "desc" ? 1 : -1;
      r = [...r].sort((a, b) => sign * cmp(a, b));
    }
    return r;
  }, [data, q, sort, dir, isAll]);

  if (err) return <div className="container"><div className="error">{err}</div></div>;
  if (!data) return <div className="loading">Loading…</div>;

  if (data.universe_size === 0 && data.picks.length === 0) {
    return (
      <div className="container wide">
        <div className="card" style={{ textAlign: "center", padding: "48px 24px" }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>{current.flag}</div>
          <strong style={{ fontSize: 18 }}>{current.name} — coming soon</strong>
          <p style={{ color: "var(--muted)", marginTop: 8, maxWidth: 460, marginInline: "auto" }}>
            We haven’t loaded {current.label} stocks yet. The daily scan for this market
            will publish ranked suggestions here soon.
          </p>
        </div>
      </div>
    );
  }

  const strongBuys = data.picks.filter((p) => groupOf(p.signal) === "strong_buy").length;
  const winRate = track?.live_win_rate;

  return (
    <div className="container wide">
      {showKpis && (
        <div className="kpis">
          <Kpi label="Stocks scanned" value={data.active_count} />
          <Kpi label="Strong buys today" value={strongBuys} />
          <Kpi label="Live win rate" value={winRate == null ? "—" : `${Math.round(winRate * 100)}%`} />
          <Kpi label="Last update" value={data.date || "—"} />
        </div>
      )}

      {!isAll && (
        <div className="trade-note">
          These are <b>plans based on last night’s close</b>. Check the <b>live price</b> in your broker
          and use a <b>limit buy</b> at the Buy price and a <b>limit sell</b> at the Sell target (never “at market”).
          The small % under the Sell target is how often it’s hit — its <b>colour shows how much it beats luck</b>,
          which matters more than the raw %.
        </div>
      )}

      <div className="card">
        <div className="toolbar">
          <div>
            <strong style={{ fontSize: 16 }}>{title}</strong>
          </div>
          <span className="pill">{rows.length} shown</span>
          <div className="spacer" style={{ flex: 1 }} />
          <input placeholder="Search ticker / name" value={q} onChange={(e) => setQ(e.target.value)} />
          {!isAll && (
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="rank">Sort: best first (confidence)</option>
              <option value="signal">Sort: signal</option>
              <option value="name">Sort: name</option>
            </select>
          )}
          {!isAll && (
            <button type="button" className="iconbtn" style={{ minWidth: 104 }}
              onClick={() => setDir((d) => (d === "desc" ? "asc" : "desc"))}
              title={dir === "desc" ? "Best / strongest first" : "Reversed — weakest first"}>
              {dir === "desc" ? "↓ Best first" : "↑ Reversed"}
            </button>
          )}
        </div>

        {!isAll && (
          <div className="legend">
            <span className="legend-title">News</span>
            <span>🟢 positive</span>
            <span>🔴 negative</span>
            <span>➖ neutral</span>
            <span title="A strong, recent event (earnings, a big contract, a deal, a payout…) that can move the price soon.">
              ⚡ catalyst
            </span>
            <span>— not analysed</span>
            <span className="legend-title" style={{ marginLeft: 10 }}>Trade</span>
            <span title="Heavily traded — tight spread, easy to buy/sell.">Easy</span>
            <span title="Reasonably traded — a small spread cost.">OK</span>
            <span title="Thinly traded — WIDE spread; you can lose 1–2% just entering.">Thin ⚠</span>
          </div>
        )}

        <div style={{ overflowX: "auto" }}>
          {isAll ? (
            <table className="responsive">
              <thead><tr><th>#</th><th>Stock</th><th className="num">Last price</th><th>Trade</th></tr></thead>
              <tbody>
                {rows.map((p, i) => (
                  <tr key={p.ticker} onClick={() => nav(`/stocks/${p.ticker}`)}>
                    <td className="num" data-label="#">{i + 1}</td>
                    <td className="tickercell" data-label="Stock">
                      {p.ticker.split(".")[0]}<small>{p.name}</small>
                    </td>
                    <td className="num" data-label="Last price">{fmt(p.last_close, currencyForTicker(p.ticker))}</td>
                    <td data-label="Trade"><LiquidityChip p={p} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="responsive">
              <thead>
                <tr>
                  <th>#</th><th>Stock</th><th>Signal</th><th>Trade</th><th>News</th>
                  <th className="num">Buy (limit)</th><th className="num">Sell target</th>
                  <th className="num" title="How often this target was hit historically — colour shows how much that beats pure luck">Confidence</th>
                  <th className="num">Stop</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => {
                  const cur = currencyForTicker(p.ticker);
                  const t = targetFor(p);
                  const br = baseRateForMap(baseRates, { target_pct: t.pct, horizon_days: t.days });
                  const lift = t.prob != null && br ? t.prob / br : null;
                  const successColor =
                    lift == null ? "var(--muted)" : lift >= 1.25 ? "var(--accent)" : lift >= 1.08 ? "var(--text)" : "var(--muted)";
                  return (
                    <tr key={p.ticker} onClick={() => nav(`/stocks/${p.ticker}`)}>
                      <td className="num" data-label="#">{p.rank}</td>
                      <td className="tickercell" data-label="Stock">
                        {p.ticker.split(".")[0]}<small>{p.name}</small>
                      </td>
                      <td data-label="Signal">
                        <span className={`badge ${groupOf(p.signal)}`}>{groupLabel(p.signal)}</span>
                      </td>
                      <td data-label="Trade"><LiquidityChip p={p} /></td>
                      <td data-label="News"><NewsChip p={p} /></td>
                      <td className="num" data-label="Buy">{fmt(p.entry_price ?? p.last_close, cur)}</td>
                      <td className="num up" data-label="Sell target">
                        {fmt(t.price, cur)}
                        {t.pct != null && (
                          <small style={{ display: "block", color: "var(--muted)", fontWeight: 400 }}>
                            +{Math.round(t.pct * 100)}%{t.days ? ` · ~${t.days}d` : ""}
                          </small>
                        )}
                      </td>
                      <td className="num" data-label="Confidence">
                        {t.prob == null ? (
                          <span style={{ color: "var(--muted)" }}>—</span>
                        ) : (
                          <span title={lift ? `${lift.toFixed(1)}× better than luck` : "vs-luck unknown"}
                            style={{ color: successColor, fontWeight: 700 }}>
                            {prob(t.prob)}
                          </span>
                        )}
                      </td>
                      <td className="num down" data-label="Stop">{fmt(p.stop_loss, cur)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <p className="disclaimer">
        {isAll
          ? `Browse the full ${current.label} universe. Tap a stock for its trade plan & position size. `
          : "Buy / Sell target / Stop are the plan prices (use limit orders). The % under the Sell target is how often that target is hit; its colour shows how much it beats random luck. Open a stock for all target scenarios & position size. "}
        A high success % on a small target mostly happens anyway — look at the <b>beats-luck</b> colour, not the raw %.
        Educational tool, <b>not financial advice</b>.
      </p>
    </div>
  );
}
