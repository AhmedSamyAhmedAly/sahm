import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

export default function Contact() {
  const { user } = useAuth();
  const [title, setTitle] = useState("");
  const [reply, setReply] = useState("");
  const [desc, setDesc] = useState("");
  const [files, setFiles] = useState([]); // [{name, type, data(base64)}]
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);

  const onFiles = (e) => {
    const list = Array.from(e.target.files || []).slice(0, 3);
    Promise.all(list.map((f) => new Promise((res) => {
      const r = new FileReader();
      r.onload = () => res({ name: f.name, type: f.type, data: String(r.result).split(",").pop() });
      r.readAsDataURL(f);
    }))).then(setFiles);
    e.target.value = "";
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!user) { setErr("Please log in to send a message."); return; }
    if (!title.trim()) { setErr("Title is required"); return; }
    setErr(""); setBusy(true);
    try {
      await api.contact(title, desc, reply, files);
      setDone(true); setTitle(""); setReply(""); setDesc(""); setFiles([]);
    } catch (e2) { setErr(e2.message); } finally { setBusy(false); }
  };

  return (
    <div className="container" style={{ maxWidth: 720 }}>
      <Link to="/" className="link">← Back</Link>
      <h1 style={{ marginTop: 12 }}>Contact us</h1>
      <div className="card" style={{ padding: 20 }}>
        {done ? (
          <p className="up">✓ Thanks! Your message was sent — the admin team will get back to you.</p>
        ) : (
          <>
            {err && <div className="error">{err}</div>}
            <p style={{ color: "var(--muted)", marginTop: 0 }}>
              Questions, account help, or feedback? Send us a message — add screenshots if it helps.
            </p>
            <form onSubmit={submit}>
              <div className="field">
                <label>Title</label>
                <input value={title} required maxLength={256}
                  onChange={(e) => setTitle(e.target.value)} placeholder="Short summary" />
              </div>
              <div className="field">
                <label>Email or mobile (so we can reply)</label>
                <input value={reply} maxLength={256}
                  onChange={(e) => setReply(e.target.value)} placeholder="you@example.com or 01x xxxx xxxx" />
              </div>
              <div className="field">
                <label>Description</label>
                <textarea value={desc} rows={5} onChange={(e) => setDesc(e.target.value)}
                  placeholder="Tell us what's going on…"
                  style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)",
                    color: "var(--text)", borderRadius: 9, padding: "11px 12px", fontSize: 15, resize: "vertical" }} />
              </div>
              <div className="field">
                <label>Attachments (optional — up to 3, ~1MB each)</label>
                <input type="file" multiple onChange={onFiles} />
                {files.length > 0 && (
                  <ul className="reasons" style={{ marginTop: 6 }}>
                    {files.map((f, i) => <li key={i}>{f.name}</li>)}
                  </ul>
                )}
              </div>
              <button className="primary" disabled={busy}>{busy ? "Sending…" : "Send message"}</button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
