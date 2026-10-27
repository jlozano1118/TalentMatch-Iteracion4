import { api } from "../api.js";
import { setRole, state } from "../state.js";
import { $, $$, animateIn, DECISION_LABEL, esc, fmtDate, ICONS, modal, ring, scoreColor, scoreLabel, toast } from "../ui.js";

const W_LABEL = { tecnico: "Técnico", power: "Power skills", experiencia: "Experiencia", educacion: "Educación" };

export function renderResults(el, go, refreshResult) {
  const r = state.result, d = state.role;
  if (!r || !d) { go(r ? "proyectos" : "cargar"); return; }
  const m = d.match, c = r.candidate;
  const w = m.weights;
  const reqYears = m.min_years || 0;
  const maxYears = Math.max(reqYears * 1.6, c.years_experience * 1.15, 2);
  const decisions = r.decisions.filter((x) => x.role_id === m.role_id);
  const allTech = [...m.matched_tech.map((x) => ({ ...x, st: "ok" })), ...m.partial_tech.map((x) => ({ ...x, st: "part" })), ...m.missing_tech.map((x) => ({ ...x, st: "miss" }))];

  el.innerHTML = `
    <div class="page-head">
      <div><span class="kicker">Paso 4 de 5 · ${esc(m.project)}</span><h1>${esc(m.title)}</h1>
      <p>${esc(m.category_es)} · ID ${m.job_id} en JobsDatasetProcessed.csv · ${esc(c.name)} (${esc(c.code)})</p></div>
      <div class="actions"><button class="btn" data-go="proyectos">${ICONS.back} Proyectos</button><button class="btn primary" data-go="plan">Plan de capacitación ${ICONS.arrow}</button></div>
    </div>

    <div class="grid g2" style="align-items:start">
      <div class="card reveal">
        <div class="score-hero">
          ${ring(m.score, 150, 10, 34)}
          <div style="flex:1;width:100%">
            <span class="kicker" style="color:${scoreColor(m.score)}">${scoreLabel(m.score)} · posición ${m.rank} de ${r.projects.reduce((a, p) => a + p.roles.length, 0)}</span>
            <div class="bars" style="margin-top:14px">
              ${[["tecnico", m.tech_score], ["power", m.soft_score], ["experiencia", m.exp_score], ["educacion", m.edu_score]].map(([k, v]) => `
              <div class="bar-row"><div class="top"><span>${W_LABEL[k]} <span class="dim">· peso ${Math.round(w[k] * 100)}%</span></span><span>${v}%</span></div>
              <div class="hbar"><i data-w="${v}" style="background:${scoreColor(v)}"></i></div></div>`).join("")}
            </div>
          </div>
        </div>
        <div class="notice" style="margin-top:18px;border-color:var(--line-2);background:var(--card-2)">${ICONS.note}
          <div><b>¿Por qué este resultado?</b><ul class="explain" style="margin:6px 0 0;padding-left:18px">${m.explanation.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div>
      </div>

      <div class="card reveal">
        <div class="card-title"><h3>Ponderación dinámica</h3><span class="tag">${esc(w.naturaleza || "")}</span></div>
        <p class="muted" style="font-size:13.5px;margin:-4px 0 14px">Ajusta la importancia de cada dimensión según la naturaleza del rol (técnico vs. power skills). Los pesos se normalizan a 100%.</p>
        ${Object.keys(W_LABEL).map((k) => `
        <div class="slider-row"><label for="w-${k}">${W_LABEL[k]}</label><input type="range" id="w-${k}" min="0" max="100" value="${Math.round(w[k] * 100)}"><span class="mono" id="wv-${k}">${Math.round(w[k] * 100)}%</span></div>`).join("")}
        <label class="check" style="border:0;padding:4px 0 10px"><input type="checkbox" id="w-role"><span>Guardar como perfil de pesos del cargo<small>Se recalcula para todos los candidatos de este cargo${d.role.weights_updated_by ? ` · último ajuste: ${esc(d.role.weights_updated_by)}` : ""}.</small></span></label>
        <div class="actions"><button class="btn primary" id="w-apply">Recalcular y guardar</button><button class="btn ghost" id="w-reset">Restablecer</button></div>
      </div>
    </div>

    <div class="grid g2" style="margin-top:18px;align-items:start">
      <div class="card reveal">
        <div class="card-title"><h3>Análisis de brecha técnica</h3><span class="tag">${m.matched_tech.length} ✓ · ${m.partial_tech.length} ≈ · ${m.missing_tech.length} ✕</span></div>
        <table class="req-table"><tbody>
          ${allTech.map((s) => `<tr><td>${esc(s.name)}${s.weight < 1 ? ' <span class="dim" style="font-size:11px">(específica)</span>' : ""}</td>
            <td style="text-align:right">${s.st === "ok" ? '<span class="status ok">cumple</span>' : s.st === "part" ? `<span class="status part" title="por ${esc(s.by || "")}">parcial · ${esc(s.by || "")}</span>` : '<span class="status miss">brecha</span>'}</td></tr>`).join("")}
        </tbody></table>
      </div>
      <div class="grid" style="gap:18px">
        <div class="card reveal">
          <div class="card-title"><h3>Experiencia demostrable</h3><span class="tag">${reqYears ? `requiere ${reqYears} años` : "no especificada"}</span></div>
          <div class="gauge"><i data-w="${Math.min(100, (c.years_experience / maxYears) * 100)}"></i>
            ${reqYears ? `<span class="mark" style="left:${Math.min(100, (reqYears / maxYears) * 100)}%">requerido ${reqYears}a</span>` : ""}</div>
          <p style="margin:12px 0 0;font-size:14px">Acredita <b>${c.years_experience} años</b>. ${reqYears ? (c.years_experience >= reqYears ? '<span style="color:var(--mint)">Cumple la experiencia solicitada.</span>'
            : (reqYears - c.years_experience <= 1 ? `<span style="color:var(--amber)">Está muy cerca: le faltan ${(reqYears - c.years_experience).toFixed(1)} años.</span>`
            : `<span style="color:var(--red)">Le faltan ${(reqYears - c.years_experience).toFixed(1)} años.</span>`)) : "La oferta no fija años mínimos."}</p>
          <p class="dim" style="font-size:12.5px;margin:6px 0 0">Formación requerida: ${esc(m.education_label)} · acreditada: ${esc(c.education_label)}</p>
        </div>
        <div class="card reveal">
          <div class="card-title"><h3>Power skills</h3><span class="tag">${m.matched_soft.length}/${m.matched_soft.length + m.missing_soft.length}</span></div>
          <div class="chips">${m.matched_soft.map((s) => `<span class="chip ok">✓ ${esc(s.name)}</span>`).join("")}${m.missing_soft.map((s) => `<span class="chip miss">✕ ${esc(s.name)}</span>`).join("")}</div>
        </div>
        <div class="card reveal">
          <div class="card-title"><h3>Decisión de Talento Humano</h3><span class="tag amber">supervisión humana</span></div>
          <p class="muted" style="font-size:13.5px;margin:-4px 0 12px">TalentMatch recomienda; una persona decide y justifica. Sistema de IA de alto riesgo según el AI Act (Anexo III): ninguna asignación es automática.</p>
          <div class="decision-btns">
            <button class="btn sm primary" data-dec="asignar">Asignar al cargo</button>
            <button class="btn sm" data-dec="en_revision">Dejar en revisión</button>
            <button class="btn sm danger" data-dec="descartar">Descartar</button>
          </div>
          ${decisions.length ? `<div class="history">${decisions.map((x) => `<div><b>${DECISION_LABEL[x.decision] || x.decision}</b> · ${fmtDate(x.created_at)} · puntaje ${x.score}%<br><span class="muted">${esc(x.justification)}</span></div>`).join("")}</div>` : ""}
        </div>
      </div>
    </div>
    <div class="card reveal" style="margin-top:18px"><span class="label">Descripción de la oferta (dataset)</span><p class="muted" style="margin:0;font-size:13.5px">${esc(m.summary)}</p></div>`;

  // --- sliders
  const keys = Object.keys(W_LABEL);
  const sync = () => {
    const vals = keys.map((k) => +$(`#w-${k}`, el).value);
    const tot = vals.reduce((a, b) => a + b, 0) || 1;
    keys.forEach((k, i) => { $(`#wv-${k}`, el).textContent = Math.round((vals[i] / tot) * 100) + "%"; });
  };
  keys.forEach((k) => $(`#w-${k}`, el).addEventListener("input", sync));
  sync();
  $("#w-reset", el).addEventListener("click", () => {
    const def = d.role.weights_default || w;
    keys.forEach((k) => { $(`#w-${k}`, el).value = Math.round((def[k] || 0) * 100); });
    sync();
  });
  $("#w-apply", el).addEventListener("click", async (e) => {
    const vals = Object.fromEntries(keys.map((k) => [k, +$(`#w-${k}`, el).value / 100]));
    if (Object.values(vals).every((v) => v === 0)) { toast("Al menos un peso debe ser mayor a cero", "err"); return; }
    e.target.disabled = true; e.target.textContent = "Recalculando…";
    try {
      const res = await api.reweight(c.id, m.role_id, { ...vals, apply_to_role: $("#w-role", el).checked });
      setRole(m.role_id, res);
      await refreshResult();
      toast(`Nuevo puntaje: ${res.match.score}% (guardado en la base de datos)`);
      renderResults(el, go, refreshResult);
    } catch (err) { toast(err.message, "err"); e.target.disabled = false; e.target.textContent = "Recalcular y guardar"; }
  });

  // --- decisiones humanas
  $$("[data-dec]", el).forEach((b) => b.addEventListener("click", () => {
    const dec = b.dataset.dec;
    modal(`<span class="kicker">Decisión humana · ${esc(m.title)}</span><h3>${DECISION_LABEL[dec]}</h3>
      <p class="muted">Registra la justificación. Queda en la bitácora de auditoría junto con el puntaje actual (${m.score}%).</p>
      <textarea class="input" id="dec-just" rows="4" maxlength="1000" placeholder="Ej.: Se valida con el líder del proyecto la experiencia en ${esc(m.missing_tech[0]?.name || "las brechas")}…"></textarea>
      <div class="actions" style="justify-content:flex-end;margin-top:14px"><button class="btn" data-close>Cancelar</button><button class="btn primary" id="dec-ok">Registrar decisión</button></div>`,
    (box, close) => {
      $("#dec-ok", box).addEventListener("click", async () => {
        const j = $("#dec-just", box).value.trim();
        if (j.length < 15) { toast("La justificación debe tener al menos 15 caracteres", "err"); return; }
        try {
          await api.decide(c.id, m.role_id, { decision: dec, justification: j });
          close();
          await refreshResult();
          toast("Decisión registrada");
          renderResults(el, go, refreshResult);
        } catch (err) { toast(err.message, "err"); }
      });
    });
  }));
  animateIn(el);
}
