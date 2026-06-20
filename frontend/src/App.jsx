import { Link, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import StockDetail from "./pages/StockDetail.jsx";
import TrackRecord from "./pages/TrackRecord.jsx";
import Admin from "./pages/Admin.jsx";
import Portfolio from "./pages/Portfolio.jsx";
import Legal from "./pages/Legal.jsx";

function Nav() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="nav">
      <div className="brand">
        صاعد <span>Saaed</span>
      </div>
      <NavLink to="/" className={({ isActive }) => "link" + (isActive ? " active" : "")} end>
        Dashboard
      </NavLink>
      <NavLink to="/portfolio" className={({ isActive }) => "link" + (isActive ? " active" : "")}>
        Portfolio
      </NavLink>
      <NavLink to="/track-record" className={({ isActive }) => "link" + (isActive ? " active" : "")}>
        Track Record
      </NavLink>
      {user.role === "admin" && (
        <NavLink to="/admin" className={({ isActive }) => "link" + (isActive ? " active" : "")}>
          Admin
        </NavLink>
      )}
      <div className="spacer" />
      <span className="pill">{user.email}</span>
      <button className="ghost" onClick={logout}>
        Logout
      </button>
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
        <Route
          path="/"
          element={
            <Protected>
              <Dashboard />
            </Protected>
          }
        />
        <Route
          path="/stocks/:ticker"
          element={
            <Protected>
              <StockDetail />
            </Protected>
          }
        />
        <Route
          path="/portfolio"
          element={
            <Protected>
              <Portfolio />
            </Protected>
          }
        />
        <Route
          path="/track-record"
          element={
            <Protected>
              <TrackRecord />
            </Protected>
          }
        />
        <Route
          path="/admin"
          element={
            <Protected adminOnly>
              <Admin />
            </Protected>
          }
        />
        <Route path="/terms" element={<Legal />} />
        <Route path="/privacy" element={<Legal />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Footer />
    </>
  );
}

function Footer() {
  return (
    <div className="footer">
      <span>صاعد Saaed · educational tool, not financial advice</span>
      <span className="spacer" />
      <Link to="/terms" className="link">Terms</Link>
      <Link to="/privacy" className="link">Privacy</Link>
    </div>
  );
}
