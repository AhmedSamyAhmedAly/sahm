import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Identity + entitlement travel together, so the UI can gate markets without
  // an extra round-trip on every page.
  const fromResp = (r) => ({
    email: r.email,
    role: r.role,
    plan: r.plan ?? null,
    planUntil: r.plan_until ?? null,
    markets: r.markets ?? [],
    needsPayment: !!r.needs_payment,
  });

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((r) => {
        setToken(r.access_token);
        setUser(fromResp(r));
      })
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const finish = (r) => {
    setToken(r.access_token);
    setUser(fromResp(r));
    return r;
  };

  // Re-read entitlement after paying / an admin grant.
  const refresh = () =>
    api.me().then((r) => { setToken(r.access_token); setUser(fromResp(r)); return r; })
      .catch(() => null);

  const value = {
    user,
    loading,
    refresh,
    login: (email, password) => api.login(email, password).then(finish),
    register: (email, password, code, plan, period) =>
      api.register(email, password, code, plan, period).then(finish),
    logout: () => {
      setToken(null);
      setUser(null);
    },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
