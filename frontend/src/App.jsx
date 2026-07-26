import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import { useMarket } from "./market.jsx";
import ProfileMenu from "./components/ProfileMenu.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import StockDetail from "./pages/StockDetail.jsx";
import TrackRecord from "./pages/TrackRecord.jsx";
import AdminUsers from "./pages/AdminUsers.jsx";
import Landing from "./pages/Landing.jsx";
import Logo from "./components/Logo.jsx";

function AdminDropdown() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  const item = ({ isActive }) => "dropdown-item" + (isActive ? " active" : "");
  return (
    <div className={"navdrop" + (open ? " open" : "")} ref={ref}>
      <button className="link" onClick={() => setOpen((o) => !o)}>Admin ▾</button>
      {open && (
        <div className="dropdown" onClick={() => setOpen(false)}>
          <NavLink to="/admin/users" className={item}>👥 Users</NavLink>
        </div>
      )}
    </div>
  );
}

function MarketsDropdown() {
  const { market, setMarket, markets, current } = useMarket();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  return (
    <div className={"navdrop" + (open ? " open" : "")} ref={ref}>
      <button className="link" onClick={() => setOpen((o) => !o)} title="Switch market">
        <span aria-hidden>{current.flag}</span> {current.label} ▾
      </button>
      {open && (
        <div className="dropdown">
          <div className="dropdown-head" style={{ fontSize: 12, color: "var(--muted)" }}>Markets</div>
          {markets.map((m) => (
            <button
              key={m.code}
              type="button"
              className={"dropdown-item" + (m.code === market ? " active" : "")}
              onClick={() => { setMarket(m.code); setOpen(false); }}
            >
              <span aria-hidden>{m.flag}</span> {m.label}
              <small style={{ display: "block", color: "var(--muted)", fontWeight: 500 }}>{m.name}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Nav() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="nav">
      <div className="brand"><Logo /></div>
      <NavLink to="/" className={({ isActive }) => "link" + (isActive ? " active" : "")} end>
        Suggestions
      </NavLink>
      <NavLink to="/track-record" className={({ isActive }) => "link" + (isActive ? " active" : "")}>
        Track record
      </NavLink>
      <MarketsDropdown />
      {user.role === "admin" && <AdminDropdown />}
      <div className="spacer" />
      <ProfileMenu />
    </div>
  );
}

function Protected({ children, adminOnly = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  return children;
}

// Home: the public landing page for visitors, the Dashboard for logged-in users.
function Home() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading…</div>;
  return user ? <Dashboard /> : <Landing />;
}

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Home />} />
        <Route path="/stocks/:ticker" element={<Protected><StockDetail /></Protected>} />
        <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
        <Route path="/admin/users" element={<Protected adminOnly><AdminUsers /></Protected>} />
        <Route path="/track-record" element={<TrackRecord />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Footer />
    </>
  );
}

function Footer() {
  return (
    <div className="footer">
      <span>Saaed · educational tool, not financial advice</span>
      <span className="spacer" />
    </div>
  );
}
