import { useEffect, useRef, useState } from "react";
import { api, setToken } from "../api.js";
import { useAuth } from "../auth.jsx";

const PERIODS = [
  { key: "monthly", label: "Monthly" },
  { key: "annual", label: "Annual", hint: "save more" },
];

// Load the PayPal JS SDK once, in subscription mode.
function usePayPalSdk(clientId) {
  const [ready, setReady] = useState(!!window.paypal);
  useEffect(() => {
    if (!clientId || window.paypal) { setReady(!!window.paypal); return; }
    const s = document.createElement("script");
    s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&vault=true&intent=subscription`;
    s.async = true;
    s.onload = () => setReady(true);
    s.onerror = () => setReady(false);
    document.body.appendChild(s);
  }, [clientId]);
  return ready;
}

function PayPalButton({ planId, onApproved, onError }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!window.paypal || !ref.current || !planId) return;
    ref.current.innerHTML = "";
    try {
      window.paypal.Buttons({
        style: { layout: "vertical", color: "gold", shape: "pill", label: "subscribe" },
        createSubscription: (_d, actions) => actions.subscription.create({ plan_id: planId }),
        onApprove: (data) => onApproved(data.subscriptionID),
        onError: (e) => onError(String(e?.message || e)),
      }).render(ref.current);
    } catch (e) {
      onError(String(e?.message || e));
    }
  }, [planId]);
  return <div ref={ref} />;
}

export default function Subscribe() {
  const { user, refresh } = useAuth();
  const [cat, setCat] = useState(null);
  const [period, setPeriod] = useState("monthly");
  const [chosen, setChosen] = useState(user?.plan || "both");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => { api.plans().then(setCat).catch((e) => setErr(e.message)); }, []);

  // Returning from a hosted checkout: the webhook may take a few seconds, so poll
  // briefly rather than telling the user it failed.
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).get("paid")) return;
    let tries = 0;
    setBusy(true);
    const t = setInterval(async () => {
      tries += 1;
      const me = await api.me().catch(() => null);
      if (me && !me.needs_payment) {
        setToken(me.access_token);
        await refresh?.();
        clearInterval(t); setBusy(false); setDone(true);
        setTimeout(() => { window.location.href = "/"; }, 1200);
      } else if (tries >= 12) {
        clearInterval(t); setBusy(false);
        setErr("Payment received but access hasn't activated yet. Give it a minute and reload — if it persists, contact support.");
      }
    }, 2500);
    return () => clearInterval(t);
  }, []);
  const sdkReady = usePayPalSdk(cat?.paypal_client_id);

  // Lemon Squeezy (Merchant of Record): the server builds a signed checkout link
  // with our user id attached, and the webhook grants access after payment.
  const startCheckout = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api.checkout(chosen, period, `${window.location.origin}/subscribe?paid=1`);
      window.location.href = r.url;
    } catch (e) {
      setErr(e.message || "Could not start checkout.");
      setBusy(false);
    }
  };

  const approve = async (subscriptionId) => {
    setBusy(true); setErr("");
    try {
      const r = await api.activateSubscription(subscriptionId);
      const me = await api.me();          // fresh token carries the new entitlement
      setToken(me.access_token);
      await refresh?.();
      setDone(true);
      setTimeout(() => { window.location.href = "/"; }, 1500);
    } catch (e) {
      setErr(e.message || "We couldn't confirm the payment. Contact support with your PayPal id.");
    } finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="container">
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 40 }}>✅</div>
          <h2>You're subscribed!</h2>
          <p style={{ color: "var(--muted)" }}>Taking you to your suggestions…</p>
        </div>
      </div>
    );
  }

  const cancelSub = async () => {
    if (!window.confirm(
      "Stop future billing? You keep access until the end of the period you've already paid for."
    )) return;
    setBusy(true); setErr("");
    try { await api.cancelSubscription(); await refresh?.(); }
    catch (e) { setErr(e.message || "Could not cancel — try again."); }
    finally { setBusy(false); }
  };

  const stats = cat?.market_stats || {};
  const daysLeft = user?.planUntil
    ? Math.ceil((new Date(user.planUntil) - Date.now()) / 86400000) : null;
  const plans = cat?.plans || [];
  const priceOf = (code) => {
    const p = plans.find((x) => x.code === code);
    return p ? (period === "annual" ? p.annual : p.monthly) : "";
  };
  const expired = user?.plan && user?.needs_payment;

  return (
    <div className="container">
      <h2 style={{ marginBottom: 4 }}>{expired ? "Your subscription has ended" : "Choose your plan"}</h2>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        {expired
          ? "Renew to get your daily signals back. Your positions and settings are untouched."
          : "Pick the market you trade. Cancel any time — access runs to the end of the paid period."}
      </p>

      {user && (
        <div className="card" style={{ padding: 14, marginBottom: 14 }}>
          <div className="sub-status">
            <div>
              <span className="plan-label-sm">Your account</span>
              <div><b>{user.email}</b></div>
            </div>
            <div>
              <span className="plan-label-sm">Current access</span>
              <div>
                {user.role === "admin" || user.role === "staff" ? (
                  <b className="up">Full access ({user.role})</b>
                ) : user.needsPayment ? (
                  <b className="down">{user.plan ? "Expired" : "No plan"}</b>
                ) : (
                  <b className="up">{(user.plan || "").toUpperCase()}</b>
                )}
              </div>
            </div>
            <div>
              <span className="plan-label-sm">Markets unlocked</span>
              <div>
                {(user.markets || []).length
                  ? user.markets.map((m) => (
                      <span key={m} className="pill" style={{ marginRight: 4 }}>{m}</span>
                    ))
                  : <span style={{ color: "var(--muted)" }}>none yet</span>}
              </div>
            </div>
            {daysLeft != null && !user.needsPayment && (
              <div>
                <span className="plan-label-sm">Renews / ends</span>
                <div>
                  <b>{String(user.planUntil).slice(0, 10)}</b>
                  <small style={{ display: "block", color: "var(--muted)" }}>
                    {daysLeft} day{daysLeft === 1 ? "" : "s"} left
                  </small>
                </div>
              </div>
            )}
            {!user.needsPayment && user.role === "member" && (
              <button type="button" className="iconbtn" disabled={busy}
                onClick={cancelSub} style={{ alignSelf: "center" }}>
                Cancel renewal
              </button>
            )}
          </div>
        </div>
      )}

      <div className="tabs" style={{ marginBottom: 14 }}>
        {PERIODS.map((p) => (
          <button key={p.key} type="button"
            className={`tab ${period === p.key ? "active" : ""}`}
            onClick={() => setPeriod(p.key)}>
            {p.label}{p.hint ? ` · ${p.hint}` : ""}
          </button>
        ))}
      </div>

      {err && <div className="error">{err}</div>}

      <div className="plan-grid">
        {plans.map((p) => {
          const price = period === "annual" ? p.annual : p.monthly;
          const active = chosen === p.code;
          return (
            <div key={p.code} className={"plan-card" + (active ? " active" : "")}
              onClick={() => setChosen(p.code)}>
              <div className="plan-name">
                {p.label}
                {user?.plan === p.code && !user?.needsPayment && (
                  <span className="pill" style={{ marginLeft: 6 }}>current</span>
                )}
                {p.code === "both" && user?.plan !== "both" && (
                  <span className="pill best" style={{ marginLeft: 6 }}>best value</span>
                )}
              </div>
              <div className="plan-price">
                ${price}<small>/{period === "annual" ? "yr" : "mo"}</small>
              </div>
              {period === "annual" && p.annual_saving > 0 && (
                <div className="plan-save">Save ${p.annual_saving} vs monthly</div>
              )}
              <p className="plan-blurb">{p.blurb}</p>
              {p.markets.some((m) => stats[m]) && (
                <div className="plan-live">
                  {p.markets.map((m) => stats[m] && (
                      <div key={m}>
                        <b>{stats[m].buy_signals}</b> buy signals in {m} today
                        <small style={{ display: "block", color: "var(--muted)" }}>
                          {stats[m].tracked.toLocaleString()} stocks tracked
                          {stats[m].scan_date ? ` · scanned ${stats[m].scan_date}` : ""}
                        </small>
                      </div>
                    ))}
                </div>
              )}
              <ul className="plan-feats">
                <li>✓ Daily ranked buy signals</li>
                <li>✓ Entry / target / stop + position sizing</li>
                <li>✓ Exit alerts on your positions</li>
                <li>✓ {p.markets.join(" + ")} market{p.markets.length > 1 ? "s" : ""}</li>
              </ul>
              <div className="plan-pick">{active ? "● Selected" : "○ Select"}</div>
            </div>
          );
        })}
      </div>

      <div className="card" style={{ padding: 16, marginTop: 14 }}>
        {!cat ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>Loading plans…</p>
        ) : !cat.payments_ready ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>
            💳 Payments aren’t switched on yet. Ask the admin to enable your account.
          </p>
        ) : busy ? (
          <p style={{ margin: 0 }}>Working… please don’t close this page.</p>
        ) : cat.provider === "lemonsqueezy" ? (
          <>
            <div className="section-title" style={{ marginTop: 0 }}>
              {plans.find((p) => p.code === chosen)?.label} · ${priceOf(chosen)}
              /{period === "annual" ? "yr" : "mo"}
            </div>
            <button type="button" className="primary" onClick={startCheckout}>
              {user?.plan && !user?.needsPayment && user.plan !== chosen
                ? "Switch plan — continue to checkout →"
                : "Continue to secure checkout →"}
            </button>
            <p className="disclaimer" style={{ marginTop: 10 }}>
              Card, PayPal, Apple&nbsp;Pay and Google&nbsp;Pay accepted. Payment is handled by
              Lemon Squeezy — we never see your card details. Renews automatically; cancel any
              time from your account menu.
            </p>
          </>
        ) : !sdkReady ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>Loading PayPal…</p>
        ) : (
          <>
            <div className="section-title" style={{ marginTop: 0 }}>
              Pay with PayPal — {plans.find((p) => p.code === chosen)?.label} ·{" "}
              ${priceOf(chosen)}/{period === "annual" ? "yr" : "mo"}
            </div>
            <PayPalButton
              planId={plans.find((p) => p.code === chosen)?.[
                period === "annual" ? "paypal_plan_annual" : "paypal_plan_monthly"
              ]}
              onApproved={approve}
              onError={setErr}
            />
            <p className="disclaimer" style={{ marginTop: 10 }}>
              Billing is handled by PayPal — we never see your card details.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
