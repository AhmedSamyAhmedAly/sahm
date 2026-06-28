import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth.jsx";

function Avatar({ u, size = 34 }) {
  const style = {
    width: size, height: size, borderRadius: "50%", flex: "0 0 auto",
    display: "grid", placeItems: "center", background: "var(--card-2)",
    border: "1px solid var(--border)", color: "var(--accent)", fontWeight: 800,
    fontSize: size * 0.4,
  };
  return <div style={style}>{(u.email || "?")[0].toUpperCase()}</div>;
}

export default function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!user) return null;

  return (
    <div className="profile-menu" ref={ref}>
      <button className="avatar-btn" onClick={() => setOpen((o) => !o)} title="Account">
        <Avatar u={user} />
      </button>
      {open && (
        <div className="dropdown">
          <div className="dropdown-head">
            <Avatar u={user} size={40} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                Your account
              </div>
              <div style={{ color: "var(--muted)", fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user.email}
              </div>
            </div>
          </div>
          <button className="dropdown-item danger" onClick={logout}>↩ Logout</button>
        </div>
      )}
    </div>
  );
}
