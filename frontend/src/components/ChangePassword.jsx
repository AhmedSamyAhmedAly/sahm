import { useState } from "react";
import { api, setToken } from "../api.js";

// Change-your-own-password dialog. Requires the current password, and on success
// swaps in the fresh token the API returns so the session stays signed in.
export default function ChangePassword({ onClose }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (next.length < 8) return setErr("New password must be at least 8 characters.");
    if (next !== confirm) return setErr("The two new passwords don’t match.");
    setBusy(true);
    try {
      const r = await api.changePassword(current, next);
      setToken(r.access_token);   // keep this session valid
      setDone(true);
      setTimeout(onClose, 1200);
    } catch (e2) {
      setErr(e2.message || "Could not change the password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="section-title" style={{ marginTop: 0 }}>Change password</div>
        {done ? (
          <p className="up" style={{ margin: "12px 0" }}>✓ Password changed.</p>
        ) : (
          <form onSubmit={submit} className="modal-form">
            <label>
              Current password
              <input type="password" autoFocus value={current} autoComplete="current-password"
                onChange={(e) => setCurrent(e.target.value)} />
            </label>
            <label>
              New password
              <input type="password" value={next} autoComplete="new-password"
                onChange={(e) => setNext(e.target.value)} />
            </label>
            <label>
              Confirm new password
              <input type="password" value={confirm} autoComplete="new-password"
                onChange={(e) => setConfirm(e.target.value)} />
            </label>
            {err && <div className="error" style={{ margin: 0 }}>{err}</div>}
            <div className="modal-actions">
              <button type="button" className="ghost" onClick={onClose}>Cancel</button>
              <button type="submit" className="primary" disabled={busy || !current || !next}>
                {busy ? "Saving…" : "Change password"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
