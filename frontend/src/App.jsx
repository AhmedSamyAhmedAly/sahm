import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import { useMarket } from "./market.jsx";
import ProfileMenu from "./components/ProfileMenu.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import StockDetail from "./pages/StockDetail.jsx";
import Positions from "./pages/Positions.jsx";
import Subscribe from "./pages/Subscribe.jsx";
import TrackRecord from "./pages/TrackRecord.jsx";
import AdminUsers from "./pages/AdminUsers.jsx";
import Landing from "./pages/Landing.jsx";
import Legal from "./pages/Legal.jsx";
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
  const { user } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  // Markets outside the plan are shown but locked — seeing what you're missing is
  // the point of a paywall.
  const covered = (code) => (user?.markets || []).includes(code);
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
          {markets.map((m) => {
            const locked = !covered(m.code);
            return (
              <button
                key={m.code}
                type="button"
                className={"dropdown-item" + (m.code === market ? " active" : "")}
                onClick={() => {
                  setOpen(false);
                  if (locked) nav("/subscribe");
                  else setMarket(m.code);
                }}
              >
                <span aria-hidden>{m.flag}</span> {m.label} {locked && <span title="Not in your plan">🔒</span>}
                <small style={{ display: "block", color: "var(--muted)", fontWeight: 500 }}>
                  {locked ? "Upgrade to unlock" : m.name}
                </small>
              </button>
            );
          })}
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
        Stocks
      </NavLink>
      <NavLink to="/positions" className={({ isActive }) => "link" + (isActive ? " active" : "")}>
        My positions
      </NavLink>
      {user.role === "admin" && (
        <NavLink to="/track-record" className={({ isActive }) => "link" + (isActive ? " active" : "")}>
          Track record
        </NavLink>
      )}
      <MarketsDropdown />
      {user.role === "admin" && <AdminDropdown />}
      <div className="spacer" />
      <ProfileMenu />
    </div>
  );
}

function Protected({ children, adminOnly = false, needsPlan = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  // Market data requires an active plan (admins/staff are exempt server-side, which
  // is reflected in `needsPayment`).
  if (needsPlan && user.needsPayment) return <Navigate to="/subscribe" replace />;
  return children;
}

// Home: the public landing page for visitors, the Dashboard for logged-in users,
// and the subscribe page for anyone whose plan has lapsed.
function Home() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading…</div>;
  if (!user) return <Landing />;
  return user.needsPayment ? <Navigate to="/subscribe" replace /> : <Dashboard />;
}

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Home />} />
        <Route path="/stocks/:ticker" element={<Protected needsPlan><StockDetail /></Protected>} />
        <Route path="/positions" element={<Protected><Positions /></Protected>} />
        <Route path="/subscribe" element={<Protected><Subscribe /></Protected>} />
        <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
        <Route path="/admin/users" element={<Protected adminOnly><AdminUsers /></Protected>} />
        {/* Admin-only: the raw model metrics are internal. The pill colours still
            work for everyone — they read the same endpoint directly. */}
        <Route path="/legal" element={<Legal />} />
        <Route path="/track-record" element={<Protected adminOnly><TrackRecord /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Footer />
    </>
  );
}

function Footer() {
  return (
    <div className="footer">
      <span>Saeed · educational tool, not financial advice</span>
      <span className="spacer" />
      <NavLink to="/legal" className="link">Terms &amp; Privacy</NavLink>
    </div>
  );
}
