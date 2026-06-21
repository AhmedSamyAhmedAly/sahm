import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth.jsx";

function initials(u) {
  const fn = (u.first_name || "").trim(), ln = (u.last_name || "").trim();
  if (fn || ln) return `${fn[0] || ""}${ln[0] || ""}`.toUpperCase();
  return (u.email || "?")[0].toUpperCase();
}

function Avatar({ u, size = 34 }) {
  const style = { width: size, height: size, borderRadius: "50%", flex: "0 0 auto" };
  if (u.avatar) return <img src={u.avatar} alt="avatar" style={{ ...style, objectFit: "cover" }} />;
  return (
    <div style={{ ...style, display: "grid", placeItems: "center", background: "var(--card-2)",
      border: "1px solid var(--border)", color: "var(--accent)", fontWeight: 800,
      fontSize: size * 0.4 }}>
      {initials(u)}
    </div>
  );
}

export default function ProfileMenu() {
  const { user, updateProfile, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!user) return null;
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ");

  return (
    <div className="profile-menu" ref={ref}>
      <button className="avatar-btn" onClick={() => setOpen((o) => !o)} title="Profile">
        <Avatar u={user} />
      </button>
      {open && (
        <div className="dropdown">
          <div className="dropdown-head">
            <Avatar u={user} size={40} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {fullName || "Your account"}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user.email}
              </div>
            </div>
          </div>
          <button className="dropdown-item" onClick={() => { setEditing(true); setOpen(false); }}>
            ✏️ Edit information
          </button>
          <button className="dropdown-item danger" onClick={logout}>↩ Logout</button>
        </div>
      )}
      {editing && (
        <EditProfile user={user} onClose={() => setEditing(false)} updateProfile={updateProfile} />
      )}
    </div>
  );
}

function EditProfile({ user, onClose, updateProfile }) {
  const [f, setF] = useState({
    first_name: user.first_name || "", last_name: user.last_name || "",
    email: user.email || "", mobile: user.mobile || "",
  });
  const [avatar, setAvatar] = useState(user.avatar || "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const pickFile = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 1.5 * 1024 * 1024) { setErr("Image too large (max ~1.5 MB)."); return; }
    const reader = new FileReader();
    reader.onload = () => setAvatar(String(reader.result));
    reader.readAsDataURL(file);
  };

  const save = async () => {
    setErr(""); setBusy(true);
    try {
      await updateProfile({
        first_name: f.first_name, last_name: f.last_name, email: f.email,
        mobile: f.mobile, avatar: avatar === (user.avatar || "") ? undefined : (avatar || ""),
      });
      onClose();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 460 }}>
        <h3>Edit information</h3>
        {err && <div className="error">{err}</div>}
        <div style={{ display: "flex", gap: 14, alignItems: "center", marginBottom: 14 }}>
          <Avatar u={{ ...user, avatar, first_name: f.first_name, last_name: f.last_name }} size={64} />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="iconbtn" onClick={() => fileRef.current?.click()}>Upload photo</button>
            {avatar && <button className="iconbtn" onClick={() => setAvatar("")}>Remove</button>}
            <input ref={fileRef} type="file" accept="image/*" onChange={pickFile} style={{ display: "none" }} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <div className="field" style={{ flex: "1 1 140px" }}>
            <label>First name</label>
            <input value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} />
          </div>
          <div className="field" style={{ flex: "1 1 140px" }}>
            <label>Last name</label>
            <input value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} />
          </div>
        </div>
        <div className="field"><label>Email</label>
          <input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
        <div className="field"><label>Mobile number</label>
          <input type="tel" placeholder="+20…" value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value })} /></div>
        <div className="modal-actions">
          <div className="grow" />
          <button className="ghost" disabled={busy} onClick={onClose}>Cancel</button>
          <button className="primary" style={{ width: "auto", padding: "11px 18px" }} disabled={busy} onClick={save}>Save</button>
        </div>
      </div>
    </div>
  );
}
