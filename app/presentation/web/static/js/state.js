// Estado de la sesión de trabajo. Sólo se guarda en sessionStorage el ID seudónimo (nunca datos personales).
export const state = {
  user: null,
  policy: null,
  result: null,      // análisis completo del candidato activo
  role: null,        // { match, plan, role } del cargo seleccionado
  roleId: null,
  charts: [],
};

export function setResult(res) {
  state.result = res;
  try { sessionStorage.setItem("tm_cid", String(res.candidate.id)); } catch { /* almacenamiento no disponible */ }
}

export function setRole(roleId, data) {
  state.roleId = roleId;
  state.role = data;
  try { sessionStorage.setItem("tm_rid", String(roleId)); } catch { /* noop */ }
}

export function clearWork() {
  state.result = null; state.role = null; state.roleId = null;
  try { sessionStorage.removeItem("tm_cid"); sessionStorage.removeItem("tm_rid"); } catch { /* noop */ }
}

export function savedIds() {
  try { return { cid: sessionStorage.getItem("tm_cid"), rid: sessionStorage.getItem("tm_rid") }; } catch { return {}; }
}

export function destroyCharts() {
  state.charts.forEach((c) => c.destroy());
  state.charts = [];
}
