import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { money } from "../format.js";
import { currencyForTicker } from "../market.jsx";
import { useTradeSettings, positionSize } from "../tradeSettings.js";
import { usePositions } from "../positions.js";
import BandPill, { baseRateMap, baseRateFor } from "./BandPill.jsx";

const RISK_CHOICES = [0.5, 1, 2];

// Money with the market's currency (EGP after the number, $ before it).
function fmt(x, cur) {
  if (x == null) return "—";
  return cur === "$" ? `$${money(x)}` : `${money(x)} ${cur}`;
}

// A copy-to-clipboard button for a limit price (paste straight into your broker).
function CopyPrice({ value }) {
  const [done, setDone] = useState(false);
  if (value == null) return null;
  return (
    <button type="button" className="copybtn" title="Copy the price for your limit order"
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard?.writeText(String(value)).then(() => {
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        });
      }}>
      {done ? "✓ copied" : "⧉ copy"}
    </button>
  );
}

// The actionable trade plan for a pick: the buy/target/stop levels (as LIMIT-order
// prices), a position-size calculator (how many shares for your risk), and the
// plain-English reminder to confirm the live price and use limit orders.
export default function TradePlan({ pick, ticker }) {
  const nav = useNavigate();
  const { capital, riskPct, setCapital, setRiskPct } = useTradeSettings();
  const { add } = usePositions();
  const cur = currencyForTicker(ticker);
  const [rates, setRates] = useState({});
  useEffect(() => { api.trackRecord().then((t) => setRates(baseRateMap(t))).catch(() => {}); }, []);
  // "I bought this" confirm step — your actual fill price/shares, editable.
  const [buying, setBuying] = useState(false);
  const [buyPrice, setBuyPrice] = useState("");
  const [buyShares, setBuyShares] = useState("");

  const entry = pick?.entry_price ?? null;
  const target = pick?.target_price ?? null;
  const stop = pick?.stop_loss ?? null;

  if (entry == null || stop == null) {
    return (
      <div className="card" style={{ padding: 16 }}>
        <div className="section-title" style={{ marginTop: 0 }}>Your trade plan</div>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          No trade plan for this stock — it didn’t pass our filters, so there’s no
          buy / target / stop suggestion (data only).
        </p>
      </div>
    );
  }

  const size = positionSize({ capital, riskPct, entry, stop });
  const gainPerShare = target != null ? target - entry : null;

  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="section-title" style={{ marginTop: 0 }}>Your trade plan</div>

      {/* The three levels — framed as LIMIT-order prices, not "buy at market". */}
      <div className="plan-levels">
        <div className="plan-level">
          <span className="plan-label">Buy (limit) at</span>
          <b>{fmt(entry, cur)}</b>
          <CopyPrice value={entry} />
        </div>
        <div className="plan-level up">
          <span className="plan-label">Sell target (limit) at</span>
          <b>{fmt(target, cur)}</b>
          <CopyPrice value={target} />
          {pick.target_pct ? <small>+{Math.round(pick.target_pct * 100)}%
            {pick.horizon_days ? ` · ~${pick.horizon_days}d` : ""}</small> : null}
        </div>
        <div className="plan-level down">
          <span className="plan-label">Safety stop at</span>
          <b>{fmt(stop, cur)}</b>
          <small>−{Math.round(((entry - stop) / entry) * 100)}%</small>
        </div>
      </div>

      {pick.bands?.length > 0 && (
        <div className="plan-scenarios">
          <span className="plan-label">All target scenarios</span>
          <div className="bandpills">
            {pick.bands.map((b) => (
              <BandPill key={`${b.target_pct}_${b.horizon_days}`} band={b} baseRate={baseRateFor(rates, b)} />
            ))}
          </div>
          <div className="edge-legend">
            <span className="plan-label">Colour = how much the success % beats pure luck:</span>
            <span className="band-pill edge-strong">real skill (≥1.25× luck)</span>
            <span className="band-pill edge-mild">some edge (≥1.08×)</span>
            <span className="band-pill edge-none">mostly luck (&lt;1.08×)</span>
          </div>
        </div>
      )}

      {/* Position sizer: how MUCH to buy so a stop-out only costs your chosen slice. */}
      <div className="sizer">
        <div className="sizer-inputs">
          <label>
            Your capital ({cur})
            <input type="number" min="0" inputMode="numeric" value={capital || ""}
              placeholder="e.g. 10000"
              onChange={(e) => setCapital(e.target.value)} />
          </label>
          <div className="sizer-risk">
            <span>Risk per trade</span>
            <div className="risk-btns">
              {RISK_CHOICES.map((r) => (
                <button key={r} type="button"
                  className={"iconbtn" + (riskPct === r ? " active-risk" : "")}
                  onClick={() => setRiskPct(r)}>{r}%</button>
              ))}
            </div>
          </div>
        </div>

        {!capital ? (
          <p className="sizer-hint">Enter your capital to see <b>how many shares</b> to buy for your risk.</p>
        ) : size && size.shares > 0 ? (
          <div className="sizer-out">
            <div className="sizer-shares">
              Buy <b>{size.shares.toLocaleString()}</b> shares
              <span className="muted"> (≈ {fmt(size.cost, cur)}, {Math.round((size.cost / capital) * 100)}% of capital)</span>
            </div>
            <div className="sizer-risk-line">
              If it hits the stop you lose ≈ <b className="down">{fmt(size.maxLoss, cur)}</b>
              <span className="muted"> ({riskPct}% of your money)</span>
              {gainPerShare > 0 && (
                <>{" · "}if it hits target ≈ <b className="up">+{fmt(size.shares * gainPerShare, cur)}</b></>
              )}
            </div>
            {size.cappedByCapital && (
              <div className="sizer-hint">Limited by your capital (not your risk) — this is all your capital can buy.</div>
            )}
          </div>
        ) : (
          <p className="sizer-hint">Your capital is too small to buy even one share at this price.</p>
        )}
      </div>

      {!buying ? (
        <button type="button" className="primary" style={{ marginTop: 12 }}
          onClick={() => {
            setBuyPrice(entry != null ? String(entry) : "");
            setBuyShares(size?.shares ? String(size.shares) : "");
            setBuying(true);
          }}>
          ＋ I bought this — track it
        </button>
      ) : (
        <div className="buy-confirm">
          <span className="plan-label">Confirm what you actually got (your broker fill):</span>
          <div className="buy-confirm-row">
            <label>I bought at ({cur})
              <input type="number" min="0" step="any" value={buyPrice}
                onChange={(e) => setBuyPrice(e.target.value)} />
            </label>
            <label>Shares
              <input type="number" min="0" value={buyShares}
                onChange={(e) => setBuyShares(e.target.value)} />
            </label>
            <button type="button" className="primary"
              disabled={!Number(buyPrice) || !Number(buyShares)}
              onClick={() => {
                add({
                  ticker, shares: Number(buyShares), buyPrice: Number(buyPrice), stop, target,
                  horizon: pick.horizon_days || null, date: new Date().toISOString().slice(0, 10),
                });
                nav("/positions");
              }}>
              Track it
            </button>
            <button type="button" className="iconbtn" onClick={() => setBuying(false)}>Cancel</button>
          </div>
          {Number(buyPrice) > 0 && entry > 0 && Math.abs(Number(buyPrice) / entry - 1) > 0.02 && (
            <div className="sizer-hint">
              ⚠ Your fill is {Math.abs((Number(buyPrice) / entry - 1) * 100).toFixed(1)}% away from the
              planned entry — the target/stop maths shift with it. Re-check the risk before committing.
            </div>
          )}
        </div>
      )}

      <p className="disclaimer" style={{ marginTop: 12 }}>
        These are <b>plans based on last night’s close</b> — check the <b>live price</b> in your
        broker first. Use a <b>limit buy</b> at the entry (never “buy at market”) so a morning gap
        can’t overpay you, and a <b>limit sell</b> at the target. Not financial advice.
      </p>
    </div>
  );
}
