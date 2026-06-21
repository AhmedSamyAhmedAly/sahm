import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function AdminMessages() {
  const [messages, setMessages] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.adminMessages().then(setMessages).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const wrap = async (fn) => {
    setErr(""); setBusy(true);
    try { await fn(); await load(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const resolveMsg = (m) => wrap(() => api.resolveMessage(m.id));
  const del = (m) => {
    if (window.confirm(`Delete this message ("${m.title}")? This cannot be undone.`))
      wrap(() => api.deleteMessage(m.id));
  };

  return (
    <div className="container">
      <h2 style={{ marginTop: 0 }}>Messages</h2>
      {err && <div className="error">{err}</div>}

      <div className="card" style={{ padding: 16 }}>
        {messages.length === 0 && <p style={{ color: "var(--muted)", margin: 0 }}>No messages yet.</p>}
        {messages.map((m) => (
          <div key={m.id} style={{ borderBottom: "1px solid var(--border)", padding: "12px 0" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <b>{m.title}</b>
              {m.resolved && <span className="pill" style={{ color: "var(--green)" }}>resolved</span>}
              <span style={{ color: "var(--muted)", fontSize: 12 }}>
                {m.email}{m.contact ? ` · reply: ${m.contact}` : ""}
                {m.created_at ? ` · ${new Date(m.created_at).toLocaleString()}` : ""}
              </span>
              <div style={{ flex: 1 }} />
              <button className="iconbtn" disabled={busy} onClick={() => resolveMsg(m)}>
                {m.resolved ? "Reopen" : "Resolve"}
              </button>
              <button className="iconbtn" disabled={busy} onClick={() => del(m)}
                style={{ color: "var(--red)", borderColor: "var(--red)" }}>Delete</button>
            </div>
            {m.description && <p style={{ margin: "6px 0", whiteSpace: "pre-wrap" }}>{m.description}</p>}
            {m.attachments?.length > 0 && (
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                {m.attachments.map((a, i) => (
                  <a key={i} className="link" download={a.name}
                    href={`data:${a.type || "application/octet-stream"};base64,${a.data}`}>📎 {a.name}</a>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
