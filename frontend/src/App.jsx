import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import ProfileMenu from "./components/ProfileMenu.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import StockDetail from "./pages/StockDetail.jsx";
import TrackRecord from "./pages/TrackRecord.jsx";
import AdminUsers from "./pages/AdminUsers.jsx";
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
          <NavLink to="/track-record" className={item}>📊 Track Record</NavLink>
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

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected><Dashboard /></Protected>} />
        <Route path="/stocks/:ticker" element={<Protected><StockDetail /></Protected>} />
        <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
        <Route path="/admin/users" element={<Protected adminOnly><AdminUsers /></Protected>} />
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
      <span>Saaed · educational tool, not financial advice</span>
      <span className="spacer" />
    </div>
  );
}
