import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import Logo from "../components/Logo.jsx";

export default function Login() {
  const { user, login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  // Plan chosen at signup — carried to the subscribe step after the account exists.
  const [plan, setPlan] = useState("both");
  const [period, setPeriod] = useState("monthly");
  const [cat, setCat] = useState(null);
  useEffect(() => { api.plans().then(setCat).catch(() => {}); }, []);
  // When signup is public there is no invite code to ask for.
  const openReg = cat?.open_registration !== false;

  if (user) {
    nav("/", { replace: true });
    return null;
  }

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, openReg ? "" : invite, plan, period);
      nav("/", { replace: true });
    } catch (e2) {
      setErr(e2.message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1><Logo /></h1>
        <p className="sub">EGX &amp; US signals with honest, backtested success rates.</p>

        {err && <div className="error">{err}</div>}

        <form onSubmit={submit}>
          <div className="field">
            <label>Email</label>
            <input type="email" value={email} required onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              required
              minLength={8}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {mode === "register" && (
            <>
              {!openReg && (
                <div className="field">
                  <label>Invite code</label>
                  <input value={invite} required onChange={(e) => setInvite(e.target.value)} />
                </div>
              )}
              <div className="field">
                <label>Choose your plan</label>
                <div className="plan-mini">
                  {(cat?.plans || []).map((p) => (
                    <button key={p.code} type="button"
                      className={"plan-mini-item" + (plan === p.code ? " active" : "")}
                      onClick={() => setPlan(p.code)}>
                      <b>{p.label}</b>
                      <span>${period === "annual" ? p.annual : p.monthly}
                        /{period === "annual" ? "yr" : "mo"}</span>
                    </button>
                  ))}
                </div>
                <div className="plan-mini" style={{ marginTop: 6 }}>
                  {["monthly", "annual"].map((k) => (
                    <button key={k} type="button"
                      className={"plan-mini-item" + (period === k ? " active" : "")}
                      onClick={() => setPeriod(k)}>{k === "annual" ? "Annual" : "Monthly"}</button>
                  ))}
                </div>
                <small style={{ color: "var(--muted)" }}>
                  You'll complete payment right after creating the account.
                </small>
              </div>
            </>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>

        <div className="switch">
          {mode === "login" ? (
            <>
              No account?{" "}
              <a onClick={() => { setMode("register"); setErr(""); }}>Create an account</a>
            </>
          ) : (
            <>
              Have an account? <a onClick={() => { setMode("login"); setErr(""); }}>Log in</a>
            </>
          )}
        </div>

        <p className="disclaimer">
          Educational/research tool — <b>not financial advice</b>. Signals are transparent
          algorithmic estimates that <b>may be inaccurate</b>; trading carries risk of loss. You
          decide and execute every trade.
        </p>
      </div>
    </div>
  );
}
