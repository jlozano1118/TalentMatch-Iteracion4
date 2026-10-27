// Cliente HTTP de la capa de presentación. La sesión viaja en cookie HttpOnly (no accesible desde JS).
async function request(method, url, body, isForm = false) {
  const opts = { method, credentials: "same-origin", headers: {} };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  }
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) {
    let msg = (data && data.detail) || (
      [502, 503, 504].includes(res.status)
        ? "El servidor se reinició o está despertando (plan gratuito). Espera unos segundos e inténtalo de nuevo."
        : `Error ${res.status}`);
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join(". ");
    const err = new Error(msg);
    err.status = res.status;
    if (res.status === 401 && !url.endsWith("/login")) window.dispatchEvent(new CustomEvent("tm:unauthorized"));
    throw err;
  }
  return data;
}

export const api = {
  login: (email, password) => request("POST", "/api/auth/login", { email, password }),
  logout: () => request("POST", "/api/auth/logout"),
  me: () => request("GET", "/api/auth/me"),
  policy: () => request("GET", "/api/privacy/policy"),
  insights: () => request("GET", "/api/insights"),
  projects: () => request("GET", "/api/projects"),
  analyze: (file, consent) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("consent", JSON.stringify(consent));
    return request("POST", "/api/candidates/analyze", fd, true);
  },
  bank: () => request("GET", "/api/candidates"),
  candidate: (id) => request("GET", `/api/candidates/${id}`),
  contact: (id) => request("GET", `/api/candidates/${id}/contact`),
  editProfile: (id, body) => request("PUT", `/api/candidates/${id}/profile`, body),
  role: (id, roleId) => request("GET", `/api/candidates/${id}/roles/${roleId}`),
  reweight: (id, roleId, body) => request("POST", `/api/candidates/${id}/roles/${roleId}/weights`, body),
  decide: (id, roleId, body) => request("POST", `/api/candidates/${id}/roles/${roleId}/decision`, body),
  remove: (id, reason) => request("POST", `/api/candidates/${id}/delete`, { reason }),
  ethics: () => request("GET", "/api/ethics"),
  audit: () => request("GET", "/api/audit"),
  exportUrl: (id) => `/api/candidates/${id}/export`,
};
