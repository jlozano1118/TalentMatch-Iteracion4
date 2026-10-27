import { state } from "../state.js";
import { $$, animateIn, esc, ICONS, ring, scoreLabel } from "../ui.js";

const STATUS_TAG = { "Activo": "mint", "Próximo": "amber", "Planificación": "blue" };

export function renderProjects(el, go, openRole) {
  const r = state.result;
  if (!r) { go("cargar"); return; }
  const best = r.best;
  el.innerHTML = `
    <div class="page-head">
      <div><span class="kicker">Paso 3 de 5 · ${esc(r.candidate.code)} · ${esc(r.candidate.name)}</span><h1>Proyectos TI activos</h1>
      <p>Compatibilidad con los ${r.projects.reduce((a, p) => a + p.roles.length, 0)} cargos de ${r.projects.length} proyectos. Los cargos y sus requisitos provienen del dataset de ofertas laborales. Expande un proyecto y selecciona un cargo para el análisis detallado.</p></div>
      <div class="actions"><button class="btn" data-go="perfil">${ICONS.back} Perfil</button></div>
    </div>
    ${best ? `<div class="card best-banner reveal">${ring(best.score, 76, 6)}
      <div style="flex:1;min-width:200px"><span class="kicker">Mejor encaje · ${esc(scoreLabel(best.score))}</span>
        <h3 style="margin:6px 0 2px;font-size:21px">${esc(best.title)}</h3>
        <div class="muted">${esc(best.project)} · ${esc(best.category_es)}</div></div>
      <button class="btn primary" data-role="${best.role_id}">Ver análisis ${ICONS.arrow}</button></div>` : ""}
    <div class="grid" style="gap:14px">
      ${r.projects.map((p, i) => `
      <div class="card proj reveal ${i === 0 ? "open" : ""}">
        <div class="proj-head" data-toggle>
          <div style="flex:1">
            <span class="tag ${STATUS_TAG[p.status] || ""}">${esc(p.status)}</span> <span class="tag">${esc(p.area)}</span>
            <h3>${esc(p.name)}</h3><p>${esc(p.description)}</p>
            <div class="meta">${esc(p.start)} → ${esc(p.end)} · ${p.roles.length} cargos · promedio ${p.avg_score}%</div>
          </div>
          <div class="right">${ring(p.score, 62, 5)}<span class="ring-cap">mejor encaje</span>${ICONS.chev}</div>
        </div>
        <div class="proj-body"><div class="roles">
          ${p.roles.map((m) => `
          <div class="role">
            ${ring(m.score, 52, 4, 12)}
            <div style="flex:1;min-width:0">
              <h4>${esc(m.title)} ${m.is_best ? '<span class="tag mint">mejor encaje</span>' : ""} ${m.viewed ? '<span class="tag">consultado</span>' : ""}</h4>
              <span class="tag">${esc(m.category_es)}</span> <span class="dim mono" style="font-size:11px">ID dataset ${m.job_id}</span>
              <div class="chips">
                ${m.matched_tech.slice(0, 5).map((s) => `<span class="chip ok">✓ ${esc(s.name)}</span>`).join("")}
                ${m.partial_tech.slice(0, 2).map((s) => `<span class="chip part">≈ ${esc(s.name)}</span>`).join("")}
                ${m.missing_tech.slice(0, 4).map((s) => `<span class="chip miss">✕ ${esc(s.name)}</span>`).join("")}
              </div>
            </div>
            <button class="btn sm" data-role="${m.role_id}">Ver detalle ${ICONS.arrow}</button>
          </div>`).join("")}
        </div></div>
      </div>`).join("")}
    </div>
    ${r.market.length ? `
    <div style="margin:34px 0 12px" class="reveal"><span class="kicker">Movilidad ampliada</span>
      <h2 class="serif" style="font-size:32px;margin:6px 0 4px;font-weight:400">Otros cargos compatibles del dataset</h2>
      <p class="muted" style="margin:0">Las 3.000 ofertas del dataset revelan trayectorias posibles más allá de los proyectos actuales.</p></div>
    <div class="market reveal">${r.market.map((m) => `
      <div class="card hover"><div style="display:flex;gap:12px;align-items:center">${ring(m.score, 48, 4, 11)}
        <div style="min-width:0"><b style="font-size:14px">${esc(m.title)}</b><div class="dim" style="font-size:12px">${esc(m.category)} · ID ${m.job_id}</div></div></div>
        <div class="chips" style="margin-top:10px">${m.matched.slice(0, 4).map((s) => `<span class="chip ok">${esc(s)}</span>`).join("")}</div></div>`).join("")}
    </div>` : ""}`;

  $$("[data-toggle]", el).forEach((h) => h.addEventListener("click", () => h.parentElement.classList.toggle("open")));
  $$("[data-role]", el).forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); openRole(+b.dataset.role); }));
  animateIn(el);
}
