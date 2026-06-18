import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((r) => {
        setToken(r.access_token);
        setUser({ email: r.email, role: r.role });
      })
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const finish = (r) => {
    setToken(r.access_token);
    setUser({ email: r.email, role: r.role });
    return r;
  };

  const value = {
    user,
    loading,
    login: (email, password) => api.login(email, password).then(finish),
    register: (email, password, code) => api.register(email, password, code).then(finish),
    logout: () => {
      setToken(null);
      setUser(null);
    },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
