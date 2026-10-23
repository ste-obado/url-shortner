const BASE = import.meta.env.VITE_API_URL || "";
const KEY = "kata_session";

export const session = {
  get: () => { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } },
  set: (s) => localStorage.setItem(KEY, JSON.stringify(s)),
  clear: () => localStorage.removeItem(KEY),
};

async function request(path, { method = "GET", body } = {}) {
  const s = session.get();
  const res = await fetch(BASE + path, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(s ? { Authorization: `Bearer ${s.access_token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && s && !path.startsWith("/api/auth/")) {
    session.clear();
    window.location.reload(); // token expired: back to the sign-in screen
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const err = new Error(readError(data, res.status)); err.status = res.status; throw err; }
  return data;
}

// FastAPI sends {detail: "text"} or {detail: [{msg: "..."}]} for validation errors
function readError(data, status) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg.replace("Value error, ", "")).join(". ");
  return `Something went wrong (${status}). Try again.`;
}

export const api = {
  register: (b) => request("/api/auth/register", { method: "POST", body: b }),
  login: (b) => request("/api/auth/login", { method: "POST", body: b }),
  links: () => request("/api/links"),
  createLink: (b) => request("/api/links", { method: "POST", body: b }),
  updateLink: (code, b) => request(`/api/links/${code}`, { method: "PATCH", body: b }),
  deleteLink: (code) => request(`/api/links/${code}`, { method: "DELETE" }),
  stats: (code) => request(`/api/stats/${code}`),
  plans: () => request("/api/billing/plans"),
  billing: () => request("/api/billing/me"),
  checkout: (b) => request("/api/billing/checkout", { method: "POST", body: b }),
  payment: (id) => request(`/api/billing/payments/${id}`),
};
