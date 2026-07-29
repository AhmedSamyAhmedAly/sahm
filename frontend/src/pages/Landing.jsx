import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Logo from "../components/Logo.jsx";
import AdSlot from "../components/AdSlot.jsx";

// Public marketing/landing page shown to logged-out visitors. The hero is the
// honest, verifiable TRACK RECORD — the one thing that earns trust (and users).
// Everything claimed here must match what the app actually does.
export default function Landing() {
  const [tr, setTr] = useState(null);
  const [cat, setCat] = useState(null);

  useEffect(() => {
    api.trackRecord().then(setTr).catch(() => {});
    api.plans().then(setCat).catch(() => {});
  }, []);

  const winRate = tr?.live_win_rate;
  const graded = tr?.live_graded || 0;
  // Headline the band with the biggest EDGE OVER LUCK, not the biggest raw
  // percentage — a 94% hit-rate on a target the market clears anyway isn't skill.
  const bestEdge = (tr?.models || [])
    .filter((m) => m.lift_top10)
    .sort((a, b) => (b.lift_top10 || 0) - (a.lift_top10 || 0))[0];
  const cheapest = Math.min(...((cat?.plans || []).map((p) => p.monthly).filter(Number.isFinite)), Infinity);

  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-brand"><Logo /></div>
        <h1>Daily stock signals you can actually check.</h1>
        <p className="landing-sub">
          Saeed scans the <b>Egyptian Exchange</b> and the <b>US market</b> every trading
          morning and ranks the highest-confidence buys — each with an entry, a target, a
          stop, and a <b>backtested, live-graded</b> success rate. No hype, no hidden results.
        </p>
        <div className="landing-cta">
          <Link to="/login" className="btn-primary">
            {Number.isFinite(cheapest) ? `Get started — from $${cheapest}/mo` : "Get started"}
          </Link>
        </div>
      </header>

      <div className="container"><AdSlot slot="landing-hero" /></div>

      <section className="landing-stats">
        <div className="lstat">
          <div className="lstat-val">{winRate == null ? "—" : `${Math.round(winRate * 100)}%`}</div>
          <div className="lstat-label">
            {graded ? `Live win rate · ${graded} graded calls` : "Live win rate — grading in progress"}
          </div>
        </div>
        <div className="lstat">
          <div className="lstat-val">{bestEdge ? `${bestEdge.lift_top10}×` : "—"}</div>
          <div className="lstat-label">
            {bestEdge
              ? `Better than luck on +${Math.round(bestEdge.target_pct * 100)}% in ${bestEdge.horizon_days}d`
              : "Measured edge over random"}
          </div>
        </div>
        <div className="lstat">
          <div className="lstat-val">16 yrs</div>
          <div className="lstat-label">of history behind every call</div>
        </div>
      </section>

      <section className="landing-how">
        <h2>How it works</h2>
        <div className="landing-steps">
          <div className="lstep">
            <span>1</span><b>We scan both markets before the open.</b> Every liquid stock,
            scored by models trained on 16 years of history — separately for EGX and the US.
          </div>
          <div className="lstep">
            <span>2</span><b>You get a plan, not just a tip.</b> Buy price, sell target and
            safety stop as limit-order prices, plus <b>how many shares</b> to buy for the risk
            you choose.
          </div>
          <div className="lstep">
            <span>3</span><b>We watch your exits.</b> Track what you own and get flagged when
            a stock hits its target, breaks its stop, or overstays its plan.
          </div>
          <div className="lstep">
            <span>4</span><b>We grade ourselves.</b> Every past call is checked against what
            actually happened, and every success rate is shown next to what pure luck would give.
          </div>
        </div>
      </section>

      {cat?.plans?.length > 0 && (
        <section className="landing-how" style={{ paddingTop: 0 }}>
          <h2>Simple pricing</h2>
          <div className="plan-grid" style={{ maxWidth: 860, margin: "0 auto" }}>
            {cat.plans.map((p) => (
              <div key={p.code} className="plan-card" style={{ cursor: "default" }}>
                <div className="plan-name">{p.label}</div>
                <div className="plan-price">${p.monthly}<small>/mo</small></div>
                <div className="plan-save">or ${p.annual}/year</div>
                <p className="plan-blurb">{p.blurb}</p>
              </div>
            ))}
          </div>
          <div className="landing-cta" style={{ justifyContent: "center" }}>
            <Link to="/login" className="btn-primary">Create your account</Link>
          </div>
        </section>
      )}

      <p className="disclaimer" style={{ textAlign: "center", maxWidth: 720, margin: "24px auto" }}>
        Educational / research tool — <b>not financial advice</b>. Signals are algorithmic
        estimates that can be wrong; about half of even our best calls miss, which is why
        stops and position sizing matter. Past performance doesn't guarantee future results,
        and you can lose money. You review and place every trade yourself.
      </p>
    </div>
  );
}
