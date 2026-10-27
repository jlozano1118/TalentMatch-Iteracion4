import { api } from "../api.js";
import { state } from "../state.js";
import { $, animateIn, esc, typeWriter, ICONS } from "../ui.js";

const C = { mint: "#19e3a1", blue: "#4da3ff", violet: "#a07bff", amber: "#f5a524", grid: "rgba(255,255,255,.06)", text: "#93a0b6" };

function chartDefaults() {
  if (!window.Chart) return;
  Chart.defaults.color = C.text;
  Chart.defaults.font.family = '"DM Sans", system-ui, sans-serif';
  Chart.defaults.borderColor = C.grid;
  Chart.defaults.plugins.tooltip.backgroundColor = "#050912";
  Chart.defaults.plugins.tooltip.borderColor = "#2a3856";
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
}

export async function renderHome(el, go) {
  const name = (state.user?.name || "").split(" ")[0];
  el.innerHTML = `
    <div class="hero">
      <span class="kicker">Hola, ${esc(name)} · Iteración 04 — datos reales, FastAPI y base de datos local</span>
      <h1>Visibiliza la <em>movilidad interna</em> y asigna talento con criterios objetivos</h1>
      <div class="typed" id="typed"></div>
      <div class="actions" style="margin-top:22px">
        <button class="btn primary" data-go="cargar">${ICONS.upload.replace('width="26" height="26"', 'width="16" height="16"')} Analizar hojas de vida</button>
        <button class="btn" data-go="banco">Ver banco de CV</button>
      </div>
    </div>
    <div class="grid g4" id="stats">${'<div class="card stat skeleton" style="height:96px"></div>'.repeat(4)}</div>

    <div style="margin:38px 0 14px" class="reveal"><span class="kicker">Cómo funciona</span></div>
    <div class="flow reveal">
      <div class="card hover"><h4>Carga con consentimiento</h4><p>PDF con texto, PDF escaneado, imagen o JSON — previa autorización del titular (Ley 1581).</p></div>
      <div class="card hover"><h4>Extracción con evidencia</h4><p>OCR cuando hace falta. Cada habilidad guarda el fragmento literal del CV que la respalda.</p></div>
      <div class="card hover"><h4>Matching explicable</h4><p>Compatibilidad con los cargos reales del dataset, con pesos dinámicos técnico vs. power skills.</p></div>
      <div class="card hover"><h4>Brechas y experiencia</h4><p>Qué cumple, qué cumple parcialmente y qué tan cerca está de la experiencia exigida.</p></div>
      <div class="card hover"><h4>Plan de capacitación</h4><p>Cursos de Coursera y Udemy con calificación &gt; 4.0, priorizados por brecha.</p></div>
    </div>

    <div class="grid g2" style="margin-top:22px">
      <div class="card reveal"><div class="card-title"><h3>Habilidades técnicas más demandadas</h3><span class="tag">3.000 ofertas</span></div><div class="chart-box"><canvas id="ch-tech"></canvas></div></div>
      <div class="card reveal"><div class="card-title"><h3>Power skills más solicitadas</h3><span class="tag mint">transversales</span></div><div class="chart-box"><canvas id="ch-soft"></canvas></div></div>
    </div>
    <div class="grid g2" style="margin-top:18px">
      <div class="card reveal"><div class="card-title"><h3>Cursos recomendables (calificación &gt; 4.0)</h3><span class="tag">Coursera · Udemy</span></div><div class="chart-box" style="height:250px"><canvas id="ch-courses"></canvas></div></div>
      <div class="card reveal">
        <span class="label">Retroalimentación · Experto en Recursos Humanos</span>
        <p class="quote">“TalentMatch ofrece un valor estratégico excepcional al visibilizar la movilidad interna y objetivar la asignación de personal.”</p>
        <p class="muted" style="font-size:14px;margin:0 0 12px">Recomendaciones incorporadas en esta iteración:</p>
        <div class="grid" style="gap:10px">
          <div class="notice mint">${ICONS.shield}<div><b>Módulo de consentimiento explícito</b><br><span class="muted">Autorización previa, expresa e informada (Ley 1581 de 2012) antes de cada análisis, con finalidades separadas.</span></div></div>
          <div class="notice mint">${ICONS.note}<div><b>Ponderación dinámica de pesos</b><br><span class="muted">Técnico vs. power skills según la naturaleza de cada rol, ajustable por Talento Humano.</span></div></div>
        </div>
      </div>
    </div>

    <div class="grid g2" style="margin-top:18px">
      <div class="card reveal">
        <span class="label">Equipo del proyecto</span>
        <div class="team-list">
          ${["Juan Sebastián Lozano Calderón", "Andrés Favid Rojas Villamil", "Juan Sebastián López Urrego", "Jeison Oswaldo Romero Cajamarca"]
            .map((n) => `<div class="m"><span class="avatar">${n.split(" ").slice(0, 2).map((w) => w[0]).join("")}</span><span>${n}</span></div>`).join("")}
        </div>
      </div>
      <div class="card reveal">
        <span class="label">Contexto académico</span>
        <h3 class="serif" style="font-size:28px;margin:0 0 8px">Problem Discovery &amp; Solution Design with Artificial Intelligence</h3>
        <p class="muted" style="margin:0 0 10px">Electiva de programa · Ingeniería de Sistemas y Computación · Universidad Católica de Colombia</p>
        <p style="margin:0">Docente: <b>Juan Carlos Navarro Beltrán</b></p>
        <p class="muted" style="font-size:13.5px;margin-top:12px">Las power skills son herramientas transversales que, gracias a la neuroplasticidad, evolucionan con el tiempo: el pensamiento crítico, la empatía y la comunicación son irremplazables (isEazy, s. f.).</p>
      </div>
    </div>`;

  typeWriter($("#typed", el), [
    "Analiza CV en PDF, escaneados o JSON en segundos.",
    "Compara cada perfil con los cargos reales de 8 proyectos.",
    "Explica cada puntaje: nada de cajas negras.",
    "Recomienda cursos con calificación superior a 4.0.",
  ]);
  animateIn(el);

  let data;
  try { data = await api.insights(); } catch { return; }
  const s = data.stats, b = data.bank;
  $("#stats", el).innerHTML = [
    [s.jobs, "ofertas laborales analizadas"], [s.courses_over_4, "cursos con calificación > 4.0"],
    [b.roles, `cargos en ${b.projects} proyectos`], [b.cvs, "hojas de vida en el banco"],
  ].map(([v, k]) => `<div class="card stat hover"><div class="v" data-count="${v}" data-suffix="">0</div><div class="k">${k}</div></div>`).join("");
  animateIn($("#stats", el));

  if (!window.Chart) return;
  chartDefaults();
  state.charts.push(new Chart($("#ch-tech", el), {
    type: "bar",
    data: { labels: data.top_tech.map((t) => t[0]), datasets: [{ data: data.top_tech.map((t) => t[1]), backgroundColor: C.mint, borderRadius: 5, barThickness: 14 }] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: C.grid } }, y: { grid: { display: false } } } },
  }));
  state.charts.push(new Chart($("#ch-soft", el), {
    type: "polarArea",
    data: { labels: data.top_soft.map((t) => t[0]), datasets: [{ data: data.top_soft.map((t) => t[1]),
      backgroundColor: ["#19e3a1cc", "#4da3ffcc", "#a07bffcc", "#f5a524cc", "#19e3a188", "#4da3ff88", "#a07bff88", "#f5a52488"], borderColor: "#0a0f1a" }] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: "right", labels: { boxWidth: 10 } } }, scales: { r: { grid: { color: C.grid }, ticks: { display: false } } } },
  }));
  state.charts.push(new Chart($("#ch-courses", el), {
    type: "bar",
    data: { labels: data.rating_bins, datasets: [
      { label: "Coursera", data: data.rating_dist.Coursera, backgroundColor: C.blue, borderRadius: 5 },
      { label: "Udemy", data: data.rating_dist.Udemy, backgroundColor: C.violet, borderRadius: 5 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 10 } } }, scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, grid: { color: C.grid } } } },
  }));
}
