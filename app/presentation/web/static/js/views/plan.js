import { state } from "../state.js";
import { animateIn, esc, ICONS, ring, safeUrl, stars } from "../ui.js";

export function renderPlan(el, go) {
  const r = state.result, d = state.role;
  if (!r || !d) { go(r ? "proyectos" : "cargar"); return; }
  const m = d.match, p = d.plan;
  if (!p) {
    el.innerHTML = `<div class="page-head"><div><span class="kicker">Paso 5 de 5</span><h1>Plan de capacitación</h1></div></div>
      <div class="card empty"><div class="serif">Sin plan de capacitación</div>
      <p>El titular no autorizó la finalidad de capacitación para esta hoja de vida, por lo que no se generan recomendaciones.</p>
      <button class="btn" data-go="resultados">${ICONS.back} Volver a resultados</button></div>`;
    return;
  }
  const techN = p.skills.filter((s) => s.type === "tecnica").length;
  el.innerHTML = `
    <div class="page-head">
      <div><span class="kicker">Paso 5 de 5 · guardado en la base de datos</span><h1>Plan de capacitación</h1>
      <p>Para el cargo <b>${esc(m.title)}</b> en <b>${esc(m.project)}</b>. Cursos de Coursera y Udemy con calificación superior a 4.0, priorizados por la importancia de cada brecha.</p></div>
      <div class="actions"><button class="btn" data-go="resultados">${ICONS.back} Resultados</button></div>
    </div>
    <div class="grid g4">
      <div class="card kpi hover"><div class="v" data-count="${p.skills.length}" data-suffix="">0</div><div class="k">brechas con curso (${techN} técnicas · ${p.skills.length - techN} power)</div></div>
      <div class="card kpi hover"><div class="v" data-count="${p.n_courses}" data-suffix="">0</div><div class="k">cursos recomendados</div></div>
      <div class="card kpi hover"><div class="v" data-count="${p.total_hours}" data-suffix=" h">0</div><div class="k">dedicación total aprox. · ${p.weeks} semanas a 6 h/sem</div></div>
      <div class="card kpi hover" style="display:flex;gap:14px;align-items:center">${ring(p.projected_score, 64, 5)}
        <div><div class="k">compatibilidad proyectada</div><div class="mono" style="font-size:13px">${m.score}% → <b style="color:var(--mint)">${p.projected_score}%</b></div></div></div>
    </div>
    <div style="margin-top:26px">
      ${p.skills.map((s, i) => `
      <div class="plan-step reveal">
        <div class="num">${String(i + 1).padStart(2, "0")}</div>
        <div class="card" style="padding:18px">
          <div class="card-title" style="margin-bottom:4px"><h3>${esc(s.skill)}</h3><span class="tag ${s.type === "tecnica" ? "red" : "violet"}">${s.type === "tecnica" ? "Brecha técnica" : "Power skill"}</span></div>
          ${s.courses.map((c) => `
          <div class="course">
            <div class="plat ${c.platform.toLowerCase()}">${c.platform === "Coursera" ? "C" : "U"}</div>
            <div style="min-width:0;flex:1">
              <div class="ct">${esc(c.title)}</div>
              <div class="cm"><span>${esc(c.platform)} · ${esc(c.provider)}</span><span class="stars">${stars(c.rating)}</span><span>${c.rating.toFixed(1)}</span>
                <span>${esc(c.level)}</span><span>${c.hours} h${c.hours_estimated ? " (estimado)" : ""}</span></div>
            </div>
            <a class="btn sm primary" href="${esc(safeUrl(c.url))}" target="_blank" rel="noopener noreferrer">Ver curso ${ICONS.ext}</a>
          </div>`).join("")}
        </div>
      </div>`).join("")}
      ${!p.skills.length ? '<div class="card empty"><div class="serif">¡Sin brechas relevantes!</div><p>El perfil ya cubre los requisitos principales del cargo.</p></div>' : ""}
    </div>
    <div class="card cta reveal" style="margin-top:10px">
      <div><h3 class="serif" style="font-size:30px;margin:0;font-weight:400">¿Listo para crecer?</h3>
      <p class="muted" style="margin:4px 0 0">Al completar este plan, ${esc(r.candidate.name.split(" ")[0])} podría alcanzar ${p.projected_score}% de compatibilidad con ${esc(m.title)}.</p></div>
      <button class="btn" data-go="proyectos">Ver otros proyectos ${ICONS.arrow}</button>
    </div>`;
  animateIn(el);
}
