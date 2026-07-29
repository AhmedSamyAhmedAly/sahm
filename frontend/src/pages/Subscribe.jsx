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
  const sdkReady = usePayPalSdk(cat?.paypal_client_id);

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

  const plans = cat?.plans || [];
  const expired = user?.plan && user?.needs_payment;

  return (
    <div className="container">
      <h2 style={{ marginBottom: 4 }}>{expired ? "Your subscription has ended" : "Choose your plan"}</h2>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        {expired
          ? "Renew to get your daily signals back. Your positions and settings are untouched."
          : "Pick the market you trade. Cancel any time — access runs to the end of the paid period."}
      </p>

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
              <div className="plan-name">{p.label}</div>
              <div className="plan-price">
                ${price}<small>/{period === "annual" ? "yr" : "mo"}</small>
              </div>
              {period === "annual" && p.annual_saving > 0 && (
                <div className="plan-save">Save ${p.annual_saving} vs monthly</div>
              )}
              <p className="plan-blurb">{p.blurb}</p>
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
        ) : !cat.paypal_configured ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>
            💳 Payments aren’t switched on yet. Ask the admin to enable your account.
          </p>
        ) : busy ? (
          <p style={{ margin: 0 }}>Confirming your payment…</p>
        ) : !sdkReady ? (
          <p style={{ color: "var(--muted)", margin: 0 }}>Loading PayPal…</p>
        ) : (
          <>
            <div className="section-title" style={{ marginTop: 0 }}>
              Pay with PayPal — {plans.find((p) => p.code === chosen)?.label} ·{" "}
              ${period === "annual"
                ? plans.find((p) => p.code === chosen)?.annual
                : plans.find((p) => p.code === chosen)?.monthly}
              /{period === "annual" ? "yr" : "mo"}
            </div>
            <PayPalButton
              planId={plans.find((p) => p.code === chosen)?.[
                period === "annual" ? "paypal_plan_annual" : "paypal_plan_monthly"
              ]}
              onApproved={approve}
              onError={setErr}
            />
            <p className="disclaimer" style={{ marginTop: 10 }}>
              Billing is handled by PayPal — we never see your card details. Renews
              automatically; cancel any time from your account menu.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
