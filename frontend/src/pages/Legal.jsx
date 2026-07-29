import { Link } from "react-router-dom";

// Terms of Service + Privacy Policy. Written to match what the app ACTUALLY does —
// if you change data handling or billing, change this page too.
// Placeholders in {{ }} must be filled in before charging real money.
const CONTACT_EMAIL = "support@saeed.app";
const OPERATOR = "Saeed";
const JURISDICTION = "Egypt";

function H({ children }) {
  return <h3 style={{ marginTop: 26, marginBottom: 6 }}>{children}</h3>;
}

export default function Legal() {
  const updated = "30 July 2026";
  return (
    <div className="container" style={{ maxWidth: 820 }}>
      <h2 style={{ marginBottom: 4 }}>Terms of Service &amp; Privacy Policy</h2>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>Last updated: {updated}</p>

      <div className="card" style={{ padding: 18, lineHeight: 1.65 }}>
        <div className="trade-note" style={{ marginBottom: 18 }}>
          <b>The short version:</b> Saeed is a research tool, not a financial adviser. Our
          signals are algorithmic estimates that are often wrong. We never touch your money
          or place trades. You decide and execute every trade, and you carry every loss.
          We charge a subscription; you can cancel any time.
        </div>

        <H>1. What Saeed is — and is not</H>
        <p>
          Saeed analyses end-of-day market data and publishes ranked, algorithmically
          generated stock ideas with suggested entry, target and stop levels, historical
          success rates, and position-size arithmetic.
        </p>
        <p>
          <b>Saeed is not financial, investment, tax or legal advice</b>, and is not a
          recommendation to buy or sell any security. We are not a licensed broker, dealer,
          investment adviser or portfolio manager. Nothing here is personalised to your
          circumstances, risk tolerance or objectives. We do not hold client funds, have no
          access to your brokerage account, and cannot place, modify or cancel any order.
        </p>

        <H>2. Risk — please read this part</H>
        <p>
          Trading shares involves a real risk of losing money, including your entire
          investment. Our published success rates are measured on historical data and
          out-of-sample tests; <b>past performance does not predict future results</b>.
          Even our strongest-rated signals fail a large share of the time — roughly half of
          the high-target calls do not reach their target. Signals are computed from
          end-of-day prices, so the price you actually pay at the next open can differ
          materially from the levels shown. Thinly traded stocks can cost you a significant
          amount in spread alone. Never trade money you cannot afford to lose.
        </p>

        <H>3. Eligibility and your account</H>
        <p>
          You must be at least 18 and legally able to enter a contract. You are responsible
          for keeping your password confidential and for everything done through your
          account. One account per person; do not share access or resell, redistribute or
          scrape our data. Tell us promptly at {CONTACT_EMAIL} if you suspect unauthorised
          use. We may suspend or terminate accounts that breach these terms.
        </p>

        <H>4. Subscriptions, billing and cancellation</H>
        <ul>
          <li>Paid plans unlock market data for the markets in the plan you choose.</li>
          <li>
            Payments are processed by <b>PayPal</b>. We never see or store your card
            details. Subscriptions renew automatically each period until cancelled.
          </li>
          <li>
            <b>Cancel any time</b> — from your account menu, or in PayPal. Cancelling stops
            future charges; your access continues to the end of the period you already paid
            for.
          </li>
          <li>
            <b>Refunds:</b> if you are unhappy, contact us within <b>14 days</b> of a charge
            and we will refund that period. Beyond that, payments are non-refundable except
            where the law requires otherwise.
          </li>
          <li>
            Prices may change; we will give notice before a change affects your renewal, and
            you can cancel instead.
          </li>
          <li>
            Failed payments may pause access until resolved. Admin-granted access can be
            changed or withdrawn at any time.
          </li>
        </ul>

        <H>5. Availability</H>
        <p>
          We aim to publish before each market opens, but we do not guarantee uptime,
          timeliness, or that any scan will run. Market data comes from third-party
          providers and may be delayed, incomplete or wrong. Maintenance, provider outages
          and errors happen. Do not rely on Saeed as your only input for a trade.
        </p>

        <H>6. Privacy — what we collect</H>
        <ul>
          <li><b>Your email address</b> — to identify your account and contact you about it.</li>
          <li>
            <b>A hash of your password</b> — we cannot read your actual password (bcrypt,
            one-way).
          </li>
          <li><b>Subscription records</b> — plan, expiry, and payment references from PayPal.</li>
          <li><b>Sign-in timestamps</b> — for security and support.</li>
          <li>
            <b>Your tracked positions</b> — these stay in <b>your browser's local
            storage</b>, not on our servers. Clearing your browser data deletes them.
          </li>
        </ul>
        <p>
          We do <b>not</b> collect your name, address, phone number, bank or card details,
          brokerage credentials, or trading history from any broker.
        </p>

        <H>7. Who we share data with</H>
        <ul>
          <li><b>PayPal</b> — to take payment and verify your subscription (their privacy policy applies).</li>
          <li><b>Our hosting and database provider</b> — to run the service.</li>
          <li><b>Market-data and news providers</b> — we send them stock symbols, never anything about you.</li>
          <li><b>Advertising networks</b>, if ads are enabled — they may set cookies and collect usage data on the pages where ads appear. Paying subscribers are not shown ads.</li>
        </ul>
        <p>We do not sell your personal data.</p>

        <H>8. Cookies and local storage</H>
        <p>
          We use your browser's local storage for your sign-in token, your selected market,
          and your tracked positions — all necessary for the app to work. If advertising is
          enabled, ad networks may set their own cookies.
        </p>

        <H>9. Your rights over your data</H>
        <p>
          Email {CONTACT_EMAIL} to access, correct, export or delete your account and its
          data. We will act within 30 days. Deleting your account removes your email,
          password hash and subscription records; anonymous, aggregated statistics may be
          retained. Cancel billing separately in PayPal (or ask us and we will).
        </p>

        <H>10. Intellectual property</H>
        <p>
          The signals, scores, models, and the site itself belong to {OPERATOR}. Your
          personal use is licensed to you while your account is active. You may not
          redistribute, republish, resell or automate bulk extraction of our output.
        </p>

        <H>11. Limitation of liability</H>
        <p>
          The service is provided “as is”, without warranties of any kind. To the maximum
          extent permitted by law, {OPERATOR} is not liable for any trading losses, lost
          profits, or indirect or consequential damages arising from your use of Saeed —
          including losses following a signal, a missed signal, incorrect data, or downtime.
          Where liability cannot be excluded, it is limited to the amount you paid us in the
          previous 12 months.
        </p>

        <H>12. Changes to these terms</H>
        <p>
          We may update this page; the “last updated” date will change. Material changes
          affecting your subscription will be notified by email or in-app. Continuing to use
          Saeed after a change means you accept it.
        </p>

        <H>13. Governing law and contact</H>
        <p>
          These terms are governed by the laws of {JURISDICTION}. Questions, refunds,
          deletion requests: <b>{CONTACT_EMAIL}</b>.
        </p>

        <p className="disclaimer" style={{ marginTop: 22 }}>
          This document is provided in good faith and describes our actual practices, but it
          is <b>not legal advice</b> and has not been reviewed by a lawyer. If you are the
          operator: have a qualified lawyer in your jurisdiction review it, and confirm
          whether publishing stock signals for payment requires a financial-services licence
          where you and your customers are based.
        </p>
      </div>

      <p style={{ marginTop: 16 }}><Link to="/">← Back</Link></p>
    </div>
  );
}
