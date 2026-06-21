import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Onboarding from "./components/Onboarding.jsx";
import ProfileMenu from "./components/ProfileMenu.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import StockDetail from "./pages/StockDetail.jsx";
import TrackRecord from "./pages/TrackRecord.jsx";
import AdminUsers from "./pages/AdminUsers.jsx";
import AdminMessages from "./pages/AdminMessages.jsx";
import Portfolio from "./pages/Portfolio.jsx";
import Legal from "./pages/Legal.jsx";
import Contact from "./pages/Contact.jsx";
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
          <NavLink to="/admin/messages" className={item}>✉️ Messages</NavLink>
          <NavLink to="/track-record" className={item}>📊 Track Record</NavLink>
        </div>
      )}
    </div>
  );
}

function Nav({ onHelp }) {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="nav">
      <div className="brand"><Logo /></div>
      <NavLink to="/" className={({ isActive }) => "link" + (isActive ? " active" : "")} end>
        Suggestions
      </NavLink>
      <NavLink to="/portfolio" className={({ isActive }) => "link" + (isActive ? " active" : "")}>
        Portfolio
      </NavLink>
      {user.role === "admin" && <AdminDropdown />}
      <div className="spacer" />
      <button className="helpbtn" title="How Saaed works" onClick={onHelp}>?</button>
      <ProfileMenu />
    </div>
  );
}

function Protected({ children, adminOnly = false, requireBudget = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  // Budget is mandatory: until it's set, everything routes to Portfolio.
  if (requireBudget && !user.budget) return <Navigate to="/portfolio" replace />;
  return children;
}

export default function App() {
  const { user } = useAuth();
  const [onb, setOnb] = useState(false);

  // Auto-open the tour on first login (no budget set yet, not seen in this browser).
  useEffect(() => {
    if (user && !user.budget && !localStorage.getItem("sahm_onb_seen")) setOnb(true);
  }, [user]);

  const closeOnb = () => { localStorage.setItem("sahm_onb_seen", "1"); setOnb(false); };

  return (
    <>
      <Nav onHelp={() => setOnb(true)} />
      <Onboarding open={onb} onClose={closeOnb} />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected requireBudget><Dashboard /></Protected>} />
        <Route path="/stocks/:ticker" element={<Protected requireBudget><StockDetail /></Protected>} />
        <Route path="/portfolio" element={<Protected><Portfolio /></Protected>} />
        <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
        <Route path="/admin/users" element={<Protected adminOnly requireBudget><AdminUsers /></Protected>} />
        <Route path="/admin/messages" element={<Protected adminOnly requireBudget><AdminMessages /></Protected>} />
        <Route path="/track-record" element={<Protected adminOnly requireBudget><TrackRecord /></Protected>} />
        <Route path="/legal" element={<Legal />} />
        <Route path="/terms" element={<Legal />} />
        <Route path="/privacy" element={<Legal />} />
        <Route path="/contact" element={<Contact />} />
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
      <Link to="/contact" className="link">Contact</Link>
      <Link to="/legal" className="link">Terms &amp; Privacy</Link>
    </div>
  );
}
