import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { user, login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

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
      else await register(email, password, invite);
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
        <h1>
          سهم <span style={{ color: "var(--accent)" }}>Sahm</span>
        </h1>
        <p className="sub">EGX signals with honest, backtested success rates.</p>

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
            <div className="field">
              <label>Invite code</label>
              <input value={invite} required onChange={(e) => setInvite(e.target.value)} />
            </div>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>

        <div className="switch">
          {mode === "login" ? (
            <>
              No account?{" "}
              <a onClick={() => { setMode("register"); setErr(""); }}>Register with invite</a>
            </>
          ) : (
            <>
              Have an account? <a onClick={() => { setMode("login"); setErr(""); }}>Log in</a>
            </>
          )}
        </div>

        <p className="disclaimer">
          Educational/research tool — <b>not financial advice</b>. Signals are transparent
          algorithmic estimates; trading carries risk of loss. You decide and execute every trade.
        </p>
      </div>
    </div>
  );
}
