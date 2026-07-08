import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Logo from "../components/Logo.jsx";

// Public marketing/landing page shown to logged-out visitors. The hero is the
// honest, verifiable TRACK RECORD — the one thing that earns trust (and users).
export default function Landing() {
  const [tr, setTr] = useState(null);

  useEffect(() => {
    api.trackRecord().then(setTr).catch(() => {});
  }, []);

  const winRate = tr?.live_win_rate;
  const graded = tr?.live_graded || 0;
  // Best backtested band (highest hit-rate with a meaningful sample) as a headline.
  const bestBt = (tr?.backtest || [])
    .filter((b) => (b.n_samples || 0) >= 200)
    .sort((a, b) => (b.hit_rate || 0) - (a.hit_rate || 0))[0];

  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-brand"><Logo /></div>
        <h1>Daily EGX signals you can actually check.</h1>
        <p className="landing-sub">
          Saaed scans the whole Egyptian Exchange every morning and gives you the highest‑confidence
          buys — with an honest, <b>backtested and live‑graded</b> success rate. No hype, no hidden results.
        </p>
        <div className="landing-cta">
          <Link to="/login" className="btn-primary">Get started — free</Link>
          <Link to="/track-record" className="btn-ghost">See the track record</Link>
        </div>
      </header>

      <section className="landing-stats">
        <div className="lstat">
          <div className="lstat-val">{winRate == null ? "—" : `${Math.round(winRate * 100)}%`}</div>
          <div className="lstat-label">Live win rate{graded ? ` · ${graded} graded calls` : ""}</div>
        </div>
        <div className="lstat">
          <div className="lstat-val">{bestBt ? `${Math.round((bestBt.hit_rate || 0) * 100)}%` : "—"}</div>
          <div className="lstat-label">
            {bestBt ? `Top band hits +${Math.round(bestBt.target_pct * 100)}% in ${bestBt.horizon_days}d` : "Backtested success"}
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
          <div className="lstep"><span>1</span><b>We scan EGX nightly.</b> Every liquid stock, scored by a model trained on 16 years of data.</div>
          <div className="lstep"><span>2</span><b>You get ranked buys.</b> Four risk tabs — from safest to aggressive — each with a target, stop, and confidence.</div>
          <div className="lstep"><span>3</span><b>We grade ourselves.</b> Every past call is checked against what actually happened. You see the real record.</div>
        </div>
        <div className="landing-cta" style={{ justifyContent: "center" }}>
          <Link to="/login" className="btn-primary">Create your free account</Link>
        </div>
      </section>

      <p className="disclaimer" style={{ textAlign: "center", maxWidth: 720, margin: "24px auto" }}>
        Educational / research tool — <b>not financial advice</b>. Past performance doesn't guarantee future
        results, and you can lose money. See our <Link to="/legal">Terms &amp; Privacy</Link>.
      </p>
    </div>
  );
}
