// Tiny API client. Token is kept in localStorage and attached as Bearer.
const BASE = import.meta.env.VITE_API_URL || "";

export function getToken() {
  return localStorage.getItem("sahm_token");
}
export function setToken(t) {
  if (t) localStorage.setItem("sahm_token", t);
  else localStorage.removeItem("sahm_token");
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && getToken()) headers["Authorization"] = `Bearer ${getToken()}`;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  register: (email, password, invite_code) =>
    request("/api/auth/register", { method: "POST", auth: false, body: { email, password, invite_code } }),
  login: (email, password) =>
    request("/api/auth/login", { method: "POST", auth: false, body: { email, password } }),
  me: () => request("/api/auth/me"),
  picks: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/api/picks${q ? `?${q}` : ""}`);
  },
  stock: (ticker) => request(`/api/stocks/${encodeURIComponent(ticker)}`),
  trackRecord: () => request("/api/track-record", { auth: false }),

  // ---- admin ----
  adminStats: () => request("/api/admin/stats"),
  adminUsers: () => request("/api/admin/users"),
  adminCreateUser: (body) =>
    request("/api/admin/users", { method: "POST", body }),
  adminUpdateUser: (id, patch) =>
    request(`/api/admin/users/${id}`, { method: "PATCH", body: patch }),
  adminDeleteUser: (id) => request(`/api/admin/users/${id}`, { method: "DELETE" }),
};
