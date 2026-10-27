// TalentMatch · capa de presentación (SPA). Enrutamiento por hash, sesión y navegación.
import { api } from "./api.js";
import { clearWork, destroyCharts, savedIds, setResult, setRole, state } from "./state.js";
import { $, $$, ICONS, particles, toast } from "./ui.js";
import { renderBank } from "./views/bank.js";
import { renderEthics } from "./views/ethics.js";
import { renderHome } from "./views/home.js";
import { renderPlan } from "./views/plan.js";
import { renderProfile } from "./views/profile.js";
import { renderProjects } from "./views/projects.js";
import { renderResults } from "./views/results.js";
import { renderUpload } from "./views/upload.js";

const VIEWS = ["inicio", "cargar", "perfil", "proyectos", "resultados", "plan", "banco", "etica"];
const STEP_ORDER = ["cargar", "perfil", "proyectos", "resultados", "plan"];

// ---------------------------------------------------------------- navegación
function go(view) {
  if (!VIEWS.includes(view)) view = "inicio";
  if (location.hash !== `#/${view}`) history.pushState(null, "", `#/${view}`);
  show(view);
}

function show(view) {
  destroyCharts();
  VIEWS.forEach((v) => $(`#view-${v}`).classList.toggle("hidden", v !== view));
  const el = $(`#view-${view}`);
  el.classList.remove("view"); void el.offsetWidth; el.classList.add("view");   // reinicia animación
  updateNav(view);
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  $("#nav").classList.remove("open");
  const render = {
    inicio: () => renderHome(el, go),
    cargar: () => renderUpload(el, go),
    perfil: () => renderProfile(el, go),
    proyectos: () => renderProjects(el, go, openRole),
    resultados: () => renderResults(el, go, refreshResult),
    plan: () => renderPlan(el, go),
    banco: () => renderBank(el, go, openCandidate),
    etica: () => renderEthics(el),
  }[view];
  render();
}

function updateNav(view) {
  const avail = { cargar: true, perfil: !!state.result, proyectos: !!state.result, resultados: !!state.role, plan: !!state.role };
  const idx = STEP_ORDER.indexOf(view);
  $$(".step").forEach((b) => {
    const v = b.dataset.go, i = STEP_ORDER.indexOf(v);
    b.disabled = !avail[v];
    b.classList.toggle("active", v === view);
    b.classList.toggle("done", avail[v] && v !== view && (idx === -1 ? avail[v] && v !== "cargar" : i < idx));
    const n = b.querySelector(".n");
    n.textContent = b.classList.contains("done") ? "✓" : String(i + 1);
  });
  $$(".navlink").forEach((b) => b.classList.toggle("active", b.dataset.go === view));
}

async function openRole(roleId) {
  try {
    const data = await api.role(state.result.candidate.id, roleId);
    setRole(roleId, data);
    await refreshResult(true);
    go("resultados");
  } catch (err) { toast(err.message, "err"); }
}

async function openCandidate(cid) {
  try {
    const res = await api.candidate(cid);
    setResult(res);
    state.role = null; state.roleId = null;
    go("perfil");
  } catch (err) { toast(err.message, "err"); }
}

async function refreshResult(silent = false) {
  if (!state.result) return;
  try { setResult(await api.candidate(state.result.candidate.id)); } catch (err) { if (!silent) toast(err.message, "err"); }
}

// ---------------------------------------------------------------- sesión
async function enterApp(user) {
  state.user = user;
  $("#login-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-avatar").textContent = user.initials;
  $("#user-name").textContent = user.name;
  $("#user-email").textContent = user.email;
  $("#user-role").textContent = user.role;
  try { state.policy = await api.policy(); } catch { state.policy = null; }
  // Restaurar el trabajo en curso (sólo IDs seudónimos en sessionStorage)
  const { cid, rid } = savedIds();
  if (cid) {
    try {
      setResult(await api.candidate(+cid));
      if (rid) setRole(+rid, await api.role(+cid, +rid));
    } catch { clearWork(); }
  }
  const view = (location.hash.match(/^#\/(\w+)/) || [])[1];
  show(VIEWS.includes(view) ? view : "inicio");
  setupMusic();
}

function showLogin() {
  $("#app").classList.add("hidden");
  $("#login-screen").classList.remove("hidden");
  const f = $("#login-form");
  f.reset();
  $$("[data-unlock]", f).forEach((i) => i.setAttribute("readonly", ""));
  particles($("#particles"));
}

function bindLogin() {
  const f = $("#login-form"), msg = $("#login-msg");
  $$("[data-unlock]", f).forEach((i) => i.addEventListener("focus", () => i.removeAttribute("readonly")));
  $("#toggle-pass").addEventListener("click", () => {
    const p = $("#login-pass");
    p.type = p.type === "password" ? "text" : "password";
  });
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.textContent = ""; msg.className = "form-msg";
    const email = $("#login-email").value.trim().toLowerCase(), pass = $("#login-pass").value;
    if (!/^[a-z0-9._-]+@talentmatch\.co$/.test(email)) {
      msg.textContent = "Ingrese su correo corporativo @talentmatch.co"; msg.classList.add("err");
      f.classList.add("shake"); setTimeout(() => f.classList.remove("shake"), 450); return;
    }
    const btn = f.querySelector("button[type=submit]");
    btn.disabled = true; btn.textContent = "Verificando…";
    try {
      const { user } = await api.login(email, pass);
      $("#login-pass").value = "";
      enterApp(user);
    } catch (err) {
      msg.textContent = err.message; msg.classList.add("err");
      $("#login-pass").value = "";
      f.classList.add("shake"); setTimeout(() => f.classList.remove("shake"), 450);
    } finally { btn.disabled = false; btn.textContent = "Ingresar al sistema"; }
  });
}

// ---------------------------------------------------------------- música (opcional)
// Si el equipo coloca un archivo propio en /static/audio/theme.mp3 aparece un botón para reproducirlo.
async function setupMusic() {
  if ($(".music-btn")) return;
  try {
    const r = await fetch("/static/audio/theme.mp3", { method: "HEAD" });
    if (!r.ok) return;
  } catch { return; }
  const audio = $("#theme-audio");
  audio.src = "/static/audio/theme.mp3";
  audio.volume = 0.35;
  const b = document.createElement("button");
  b.className = "btn sm music-btn"; b.innerHTML = `${ICONS.music} Música`;
  b.addEventListener("click", () => {
    if (audio.paused) { audio.play(); b.innerHTML = `${ICONS.music} Pausar`; } else { audio.pause(); b.innerHTML = `${ICONS.music} Música`; }
  });
  document.body.appendChild(b);
}

// ---------------------------------------------------------------- arranque
function bindGlobal() {
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-go]");
    if (t && !t.disabled) { e.preventDefault(); go(t.dataset.go); }
  });
  window.addEventListener("popstate", () => {
    const v = (location.hash.match(/^#\/(\w+)/) || [])[1];
    if (state.user) show(VIEWS.includes(v) ? v : "inicio");
  });
  const chip = $("#user-chip"), menu = $("#user-menu");
  chip.addEventListener("click", (e) => { if (!e.target.closest("#logout-btn")) menu.classList.toggle("hidden"); });
  document.addEventListener("click", (e) => { if (!chip.contains(e.target)) menu.classList.add("hidden"); });
  $("#logout-btn").addEventListener("click", async () => {
    try { await api.logout(); } catch { /* sesión ya expirada */ }
    clearWork(); state.user = null; menu.classList.add("hidden");
    history.replaceState(null, "", "/");
    showLogin();
  });
  $("#burger").addEventListener("click", () => $("#nav").classList.toggle("open"));
  window.addEventListener("tm:unauthorized", () => {
    if (state.user) { toast("La sesión expiró. Ingrese nuevamente.", "err"); state.user = null; }
    showLogin();
  });
}

(async function main() {
  bindGlobal();
  bindLogin();
  try {
    const { user } = await api.me();
    enterApp(user);
  } catch {
    showLogin();
  }
})();

