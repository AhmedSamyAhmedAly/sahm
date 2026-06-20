import { Link } from "react-router-dom";

export default function Legal() {
  return (
    <div className="container" style={{ maxWidth: 820 }}>
      <Link to="/" className="link">← Back</Link>
      <h1 style={{ marginTop: 12 }}>Terms &amp; Privacy</h1>
      <p style={{ color: "var(--muted)" }}>Saaed — last updated June 2026.</p>

      <div className="card" style={{ padding: 20, marginTop: 16, lineHeight: 1.7 }}>
        <h2>Terms &amp; Conditions</h2>

        <h3>1. What Saaed is — and isn't</h3>
        <p>
          Saaed is an <b>educational / research tool</b>. It produces algorithmic estimates and
          AI-generated summaries about stocks on the Egyptian Exchange (EGX). <b>These are
          suggestions only.</b> They are <b>not</b> financial, investment, legal, or tax advice,
          and <b>not</b> a recommendation, solicitation, or offer to buy or sell any security.
        </p>

        <h3>2. No guarantee of accuracy</h3>
        <p>
          The predictions, "Success %" figures, signals, price targets, stop levels, and news
          sentiment <b>may be wrong, incomplete, delayed, or out of date.</b> Past or backtested
          performance does <b>not</b> guarantee future results. Market data is end-of-day and is
          provided by third parties; AI-generated theses can contain mistakes. Treat everything you
          see here critically and verify independently before acting.
        </p>

        <h3>3. You make your own decisions</h3>
        <p>
          You are solely responsible for your own trading and investment decisions and for any
          orders you place (which you execute yourself in your own brokerage app). <b>Trading
          stocks carries risk, including the risk of losing your entire capital.</b> Only risk money
          you can afford to lose. Consider consulting a licensed financial advisor.
        </p>

        <h3>4. No liability</h3>
        <p>
          Saaed and its operators provide the service "as is", without warranties of any kind, and
          accept <b>no liability</b> for any loss or damage arising from your use of the service or
          reliance on its content.
        </p>

        <h3>5. Access</h3>
        <p>
          Access is invite-only and personal to you. Don't share your login. We may suspend or
          remove accounts at our discretion. We may change or discontinue features at any time.
        </p>

        <hr style={{ borderColor: "var(--border)", margin: "24px 0" }} />

        <h2>Privacy Policy</h2>

        <h3>What we store</h3>
        <ul>
          <li>Your <b>email</b> and a <b>securely hashed</b> password (we never store it in plain text).</li>
          <li>Your <b>watchlist</b> and <b>portfolio</b> entries, if you create them.</li>
          <li>Basic activity such as your last login time.</li>
          <li>A login token is kept in your browser's local storage to keep you signed in.</li>
        </ul>

        <p className="disclaimer" style={{ marginTop: 20 }}>
          By using Saaed you acknowledge that you have read and understood the above, and that all
          content is provided as <b>suggestions that may be inaccurate</b> — not financial advice.
        </p>
      </div>
    </div>
  );
}
