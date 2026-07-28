import { money } from "../format.js";
import { currencyForTicker } from "../market.jsx";
import { useTradeSettings, positionSize } from "../tradeSettings.js";

const RISK_CHOICES = [0.5, 1, 2];

// Money with the market's currency (EGP after the number, $ before it).
function fmt(x, cur) {
  if (x == null) return "—";
  return cur === "$" ? `$${money(x)}` : `${money(x)} ${cur}`;
}

// The actionable trade plan for a pick: the buy/target/stop levels (as LIMIT-order
// prices), a position-size calculator (how many shares for your risk), and the
// plain-English reminder to confirm the live price and use limit orders.
export default function TradePlan({ pick, ticker }) {
  const { capital, riskPct, setCapital, setRiskPct } = useTradeSettings();
  const cur = currencyForTicker(ticker);

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
        </div>
        <div className="plan-level up">
          <span className="plan-label">Sell target (limit) at</span>
          <b>{fmt(target, cur)}</b>
          {pick.target_pct ? <small>+{Math.round(pick.target_pct * 100)}%
            {pick.horizon_days ? ` · ~${pick.horizon_days}d` : ""}</small> : null}
        </div>
        <div className="plan-level down">
          <span className="plan-label">Safety stop at</span>
          <b>{fmt(stop, cur)}</b>
          <small>−{Math.round(((entry - stop) / entry) * 100)}%</small>
        </div>
      </div>

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

      <p className="disclaimer" style={{ marginTop: 12 }}>
        These are <b>plans based on last night’s close</b> — check the <b>live price</b> in your
        broker first. Use a <b>limit buy</b> at the entry (never “buy at market”) so a morning gap
        can’t overpay you, and a <b>limit sell</b> at the target. Not financial advice.
      </p>
    </div>
  );
}
