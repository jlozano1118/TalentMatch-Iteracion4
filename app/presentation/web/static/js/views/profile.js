import { api } from "../api.js";
import { setResult, state } from "../state.js";
import { $, $$, animateIn, esc, ICONS, ring, SOURCE_LABEL, toast } from "../ui.js";

const EDU = ["No especificado", "Bachiller", "Técnico", "Tecnólogo", "Profesional (pregrado)", "Especialización", "Maestría", "Doctorado"];
const EDU_STATUS = ["", "Graduado", "En curso", "Incompleto"];

function confClass(c) { return c >= 0.9 ? "" : c >= 0.75 ? "c2" : "c3"; }

function skillChip(s, editing) {
  const tip = `${s.source} · confianza ${Math.round(s.confidence * 100)}% · “${s.evidence}”`;
  return `<span class="chip" data-tip="${esc(tip)}" data-key="${esc(s.name)}"><span class="dot ${confClass(s.confidence)}"></span>${esc(s.name)}
    ${editing ? `<button class="x" data-rm aria-label="Quitar ${esc(s.name)}">×</button>` : ""}</span>`;
}

// ---------- utilidades de fechas (AAAA-MM) ----------
const thisMonth = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };
const ymIdx = (s) => { const m = /^(\d{4})-(\d{2})$/.exec(s || ""); return m ? (+m[1]) * 12 + (+m[2]) : 0; };
const prevMonth = (s) => { const i = ymIdx(s) - 1; if (i <= 0) return ""; const y = Math.floor((i - 1) / 12), m = ((i - 1) % 12) + 1; return `${y}-${String(m).padStart(2, "0")}`; };
const fmtYM = (s) => { const m = /^(\d{4})-(\d{2})$/.exec(s || ""); return m ? `${m[2]}/${m[1]}` : ""; };

function totalYears(entries) {
  const now = ymIdx(thisMonth());
  const spans = entries.map((e) => [ymIdx(e.start), e.current ? now : (ymIdx(e.end) || ymIdx(e.start))])
    .filter(([s, f]) => s && f >= s).sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [s, f] of spans) {
    if (merged.length && s <= merged[merged.length - 1][1]) merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], f);
    else merged.push([s, f]);
  }
  return merged.length ? Math.round((merged.reduce((a, [s, f]) => a + (f - s), 0) / 12) * 10) / 10 : null;
}

function splitRole(role, company) {
  if (!role || company) return [role || "", company || ""];
  const m = /^(.{2,}?)\s+(?:-|–|\||@|at|en)\s+(.{2,})$/.exec(role);
  return m ? [m[1].trim(), m[2].trim()] : [role, ""];
}
const normExp = (e) => { const [role, company] = splitRole(e.role, e.company); return { role, company, start: e.start || "", end: e.end || "",
  current: !!e.current, years: e.years || 0, period: e.period || "", source: e.source || "" }; };
const normEdu = (e) => ({ title: e.title || e.text || "", institution: e.institution || "", level: e.level || 0, status: e.status || "" });
const normCert = (x) => (typeof x === "string" ? { name: x, issuer: "", year: null, internal: false }
  : { name: x.name || "", issuer: x.issuer || "", year: x.year ?? null, internal: !!x.internal });

export function renderProfile(el, go) {
  const r = state.result;
  if (!r) { go("cargar"); return; }
  const c = r.candidate;
  let editing = false;
  let tech, soft, exp, edu, certs;
  const form = {};
  const reset = () => {
    tech = c.tech_skills.slice(); soft = c.soft_skills.slice();
    exp = c.experience.map(normExp); edu = c.education.map(normEdu); certs = c.certifications.map(normCert);
    Object.assign(form, { name: c.name, head: c.headline, years: c.years_experience, edu: c.education_level, yearsManual: false, eduManual: false });
  };
  reset();

  // ---------- vistas de solo lectura ----------
  const expView = () => (c.experience.length ? `<ul class="timeline">${c.experience.map((e) => {
    const x = normExp(e);
    const period = x.start ? `${fmtYM(x.start)} – ${x.current ? "Actual" : fmtYM(x.end)}` : x.period;
    const tag = /ascenso/i.test(x.source) ? ' <span class="tag mint">ascenso interno</span>' : (/manual/i.test(x.source) ? ' <span class="tag">editado</span>' : "");
    return `<li><div class="t">${esc(x.role || "Cargo")}${x.company && !x.role.includes(x.company) ? ` · <span class="muted">${esc(x.company)}</span>` : ""}${tag}</div>
      <div class="p">${esc(period)}${x.years ? ` · ${x.years} años` : ""}</div></li>`;
  }).join("")}</ul>` : '<p class="muted">Sin experiencia identificada. Usa <b>Editar perfil</b> para registrarla.</p>');

  const eduView = () => (c.education.length ? `<ul class="timeline">${c.education.map((e) => {
    const x = normEdu(e);
    return `<li><div class="t" style="font-weight:500">${esc(e.text || x.title)}</div>${x.level ? `<div class="p">${esc(EDU[x.level])}${x.status ? ` · ${esc(x.status)}` : ""}</div>` : ""}</li>`;
  }).join("")}</ul>` : '<p class="muted">Sin formación identificada. Usa <b>Editar perfil</b> para registrarla.</p>');

  const certView = () => (c.certifications.length ? `<div class="chips">${c.certifications.map(normCert).map((x) =>
    `<span class="chip ${x.internal ? "ok" : ""}">${esc(x.name)}${x.year ? ` · ${x.year}` : ""}${x.internal ? " · interna" : ""}</span>`).join("")}</div>`
    : '<p class="muted" style="margin:0">Sin certificaciones registradas.</p>');

  // ---------- editores ----------
  const expEditor = () => `
    <div id="exp-rows">${exp.map((e, i) => `
      <div class="edit-row exp" data-i="${i}">
        <input class="input" data-f="role" value="${esc(e.role)}" placeholder="Cargo (ej. Líder técnico)" maxlength="140" aria-label="Cargo">
        <input class="input" data-f="company" value="${esc(e.company)}" placeholder="Empresa / área" maxlength="120" aria-label="Empresa">
        <label class="mini"><span>Inicio</span><input class="input" type="month" data-f="start" value="${esc(e.start)}" max="${thisMonth()}"></label>
        <label class="mini"><span>Fin</span><input class="input" type="month" data-f="end" value="${esc(e.current ? "" : e.end)}" ${e.current ? "disabled" : ""} max="${thisMonth()}"></label>
        <label class="mini-check"><input type="checkbox" data-f="current" ${e.current ? "checked" : ""}> Actual</label>
        <button class="icon-btn" data-del title="Quitar">${ICONS.trash}</button>
        ${!e.start && e.years ? `<div class="row-note">Sin fechas en el CV original (${e.years} años). Agrega inicio y fin para recalcular.</div>` : ""}
      </div>`).join("") || '<p class="muted">Aún no hay experiencia registrada.</p>'}</div>
    <div class="actions" style="margin-top:6px">
      <button class="btn sm" id="add-exp">+ Agregar experiencia</button>
      <button class="btn sm primary" id="promote">${ICONS.arrow} Registrar ascenso interno</button>
    </div>`;

  const eduEditor = () => `
    <div id="edu-rows">${edu.map((e, i) => `
      <div class="edit-row edu" data-i="${i}">
        <input class="input" data-f="title" value="${esc(e.title)}" placeholder="Título (ej. Ingeniería de Sistemas)" maxlength="200" aria-label="Título">
        <input class="input" data-f="institution" value="${esc(e.institution)}" placeholder="Institución" maxlength="120" aria-label="Institución">
        <select class="input" data-f="level" aria-label="Nivel">${EDU.map((x, j) => `<option value="${j}" ${j === +e.level ? "selected" : ""}>${x}</option>`).join("")}</select>
        <select class="input" data-f="status" aria-label="Estado">${EDU_STATUS.map((x) => `<option value="${x}" ${x === e.status ? "selected" : ""}>${x || "Estado"}</option>`).join("")}</select>
        <button class="icon-btn" data-del title="Quitar">${ICONS.trash}</button>
      </div>`).join("") || '<p class="muted">Aún no hay formación registrada.</p>'}</div>
    <button class="btn sm" id="add-edu" style="margin-top:6px">+ Agregar formación</button>`;

  const certEditor = () => `
    <div id="cert-rows">${certs.map((x, i) => `
      <div class="edit-row cert" data-i="${i}">
        <input class="input" data-f="name" value="${esc(x.name)}" placeholder="Certificación (ej. AWS Solutions Architect)" maxlength="160" aria-label="Certificación">
        <input class="input" data-f="issuer" value="${esc(x.issuer)}" placeholder="Emisor" maxlength="120" aria-label="Emisor">
        <input class="input" type="number" data-f="year" value="${x.year ?? ""}" placeholder="Año" min="1970" max="${new Date().getFullYear() + 1}" aria-label="Año">
        <label class="mini-check"><input type="checkbox" data-f="internal" ${x.internal ? "checked" : ""}> Interna</label>
        <button class="icon-btn" data-del title="Quitar">${ICONS.trash}</button>
      </div>`).join("") || '<p class="muted">Aún no hay certificaciones.</p>'}</div>
    <div class="actions" style="margin-top:6px">
      <button class="btn sm" id="add-cert">+ Agregar certificación</button>
      <button class="btn sm primary" id="add-cert-int">+ Certificación interna</button>
    </div>
    <p class="dim" style="font-size:12px;margin:10px 0 0">Las tecnologías que nombre una certificación (p. ej. “AWS”, “Kubernetes”) se suman automáticamente a las habilidades técnicas como evidencia.</p>`;

  const draw = () => {
    el.innerHTML = `
    <div class="page-head">
      <div><span class="kicker">Paso 2 de 5 · ${esc(c.code)}</span><h1>Tu perfil extraído</h1>
      <p>Revisa que la información sea correcta. Puedes editar habilidades, experiencia, formación y certificaciones (por ejemplo, ascensos o certificaciones internas): la compatibilidad se recalcula y queda registrada.</p></div>
      <div class="actions">
        ${editing ? `<button class="btn" id="cancel-edit">Cancelar</button><button class="btn primary" id="save-edit">Guardar y recalcular</button>`
                  : `<button class="btn" id="edit-btn">${ICONS.edit} Editar perfil</button><button class="btn primary" data-go="proyectos">Ver proyectos TI ${ICONS.arrow}</button>`}
      </div>
    </div>
    ${r.duplicate ? `<div class="notice amber" style="margin-bottom:16px">${ICONS.note}<span>Este archivo ya estaba en el banco de CV; se muestra el análisis almacenado (no se duplicó el registro).</span></div>` : ""}
    <div class="grid side">
      <div class="grid" style="gap:18px">
        <div class="card profile-card">
          <span class="avatar lg" style="margin:0 auto">${esc(c.initials)}</span>
          ${editing ? `<input class="input" id="e-name" value="${esc(form.name)}" style="margin-top:12px;text-align:center" maxlength="120">`
                    : `<div class="name">${esc(c.name)}</div>`}
          ${editing ? `<input class="input" id="e-head" value="${esc(form.head)}" placeholder="Cargo / titular" style="margin-top:8px;text-align:center" maxlength="200">`
                    : `<div class="muted" style="font-size:14px">${esc(c.headline || "Sin titular identificado")}</div>`}
          <div style="margin-top:10px"><span class="tag mint">${esc(c.code)}</span> <span class="tag">${esc(SOURCE_LABEL[c.source_type] || c.source_type)}</span>${c.edited ? ' <span class="tag amber">editado</span>' : ""}</div>
          <dl class="kv">
            <dt>Correo</dt><dd id="c-email">${esc(c.email || "—")}</dd>
            <dt>Teléfono</dt><dd id="c-phone">${esc(c.phone || "—")}</dd>
            <dt>Ubicación</dt><dd>${esc(c.location || "—")}</dd>
          </dl>
          ${c.email || c.phone ? `<button class="btn ghost sm" id="reveal" style="margin-top:10px">${ICONS.eye} Mostrar contacto (queda auditado)</button>` : ""}
          <div class="mini-stats">
            <div>${editing ? `<input class="input" id="e-years" type="number" min="0" max="50" step="0.1" value="${form.years}" style="padding:6px;text-align:center" title="Se calcula con las fechas de experiencia; puedes ajustarlo">` : `<b>${c.years_experience}</b>`}<span>años exp.</span></div>
            <div><b>${c.n_tech}</b><span>técnicas</span></div>
            <div><b>${c.n_soft}</b><span>power</span></div>
          </div>
          <div style="margin-top:12px;text-align:left"><span class="label" style="margin-bottom:6px">Nivel educativo</span>
            ${editing ? `<select class="input" id="e-edu">${EDU.map((e, i) => `<option value="${i}" ${i === +form.edu ? "selected" : ""}>${e}</option>`).join("")}</select>
                         <div class="dim" style="font-size:11.5px;margin-top:4px">Se toma el nivel más alto de la formación registrada.</div>`
                      : `<b>${esc(c.education_label)}</b>`}</div>
        </div>
        <div class="card">
          <div class="card-title"><h3>${ICONS.shield} Privacidad</h3>${ring(c.quality.completeness || 0, 56, 4, 12)}</div>
          <p class="muted" style="font-size:13px;margin:-6px 0 12px">Completitud del perfil extraído</p>
          ${c.sensitive_discarded.length ? `<span class="label">Datos sensibles descartados (no usados ni guardados)</span>
            <div class="chips">${c.sensitive_discarded.map((s) => `<span class="chip miss">${esc(s)}</span>`).join("")}</div>`
            : `<div class="notice mint">${ICONS.shield}<span>No se detectaron datos sensibles en el documento.</span></div>`}
          <p class="dim" style="font-size:12px;margin:12px 0 0">Autorización ${esc(c.consent.version)} · finalidades: ${esc(c.consent.purposes.join(", "))}${c.consent.external_ai ? " · IA externa autorizada" : ""}</p>
          <p class="dim" style="font-size:12px;margin:4px 0 0">Método: ${esc(c.extraction_method)}</p>
        </div>
      </div>
      <div class="grid" style="gap:18px">
        ${(c.quality.warnings || []).length && !editing ? `<div class="notice amber">${ICONS.note}<div>${c.quality.warnings.map(esc).join("<br>")}</div></div>` : ""}
        <div class="card">
          <div class="card-title"><h3>Habilidades técnicas</h3><span class="tag mint">${tech.length} identificadas</span></div>
          <div class="chips" id="tech-chips">${tech.map((s) => skillChip(s, editing)).join("") || '<span class="muted">Sin habilidades técnicas</span>'}</div>
          ${editing ? `<div class="add-row"><input class="input" id="add-tech" placeholder="Agregar habilidad técnica (ej. Kubernetes)" maxlength="60"><button class="btn sm primary" id="add-tech-btn">Agregar</button></div>` : ""}
          <p class="dim" style="font-size:12px;margin:12px 0 0">Pasa el cursor sobre una habilidad para ver la evidencia literal del CV · <span style="color:var(--mint)">●</span> alta <span style="color:var(--amber)">●</span> media <span style="color:var(--dim)">●</span> inferida</p>
        </div>
        <div class="card">
          <div class="card-title"><h3>Power skills</h3><span class="tag">${soft.length} identificadas</span></div>
          <div class="chips" id="soft-chips">${soft.map((s) => skillChip(s, editing)).join("") || '<span class="muted">Sin power skills explícitas</span>'}</div>
          ${editing ? `<div class="add-row"><input class="input" id="add-soft" placeholder="Agregar power skill (ej. Liderazgo)" maxlength="60"><button class="btn sm primary" id="add-soft-btn">Agregar</button></div>` : ""}
        </div>
        ${editing ? `
        <div class="card"><div class="card-title"><h3>Experiencia</h3><span class="tag" id="exp-total">${form.years} años</span></div>${expEditor()}</div>
        <div class="card"><div class="card-title"><h3>Formación</h3></div>${eduEditor()}</div>
        <div class="card"><div class="card-title"><h3>Certificaciones</h3><span class="tag mint">internas y externas</span></div>${certEditor()}</div>`
        : `
        <div class="grid g2">
          <div class="card"><div class="card-title"><h3>Experiencia</h3><span class="tag">${c.years_experience} años</span></div>${expView()}</div>
          <div class="card"><div class="card-title"><h3>Formación</h3></div>${eduView()}
            ${c.languages.length ? `<span class="label" style="margin-top:12px">Idiomas</span><div class="chips">${c.languages.map((l) => `<span class="chip">${esc(l.language)} · ${esc(l.level)}</span>`).join("")}</div>` : ""}
          </div>
        </div>
        <div class="card"><div class="card-title"><h3>Certificaciones</h3><span class="tag">${c.certifications.length}</span></div>${certView()}</div>`}
        ${c.summary && !editing ? `<div class="card"><span class="label">Resumen profesional</span><p style="margin:0" class="muted">${esc(c.summary)}</p></div>` : ""}
      </div>
    </div>`;
    bind();
    animateIn(el);
  };

  // Recalcula años y nivel educativo a partir de lo registrado (salvo ajuste manual)
  const syncDerived = () => {
    const t = totalYears(exp);
    if (t !== null && !form.yearsManual) {
      form.years = t;
      const inp = $("#e-years", el); if (inp) inp.value = t;
    }
    const tag = $("#exp-total", el); if (tag) tag.textContent = `${form.years} años`;
    const lv = Math.max(0, ...edu.map((e) => +e.level || 0));
    if (edu.length && !form.eduManual) {
      form.edu = lv;
      const sel = $("#e-edu", el); if (sel) sel.value = String(lv);
    }
  };

  const bindRows = (sel, arr, onChange) => {
    $$(`${sel} .edit-row`, el).forEach((row) => {
      const i = +row.dataset.i;
      $$("[data-f]", row).forEach((inp) => {
        const evt = inp.type === "checkbox" || inp.tagName === "SELECT" ? "change" : "input";
        inp.addEventListener(evt, () => {
          const f = inp.dataset.f;
          arr[i][f] = inp.type === "checkbox" ? inp.checked : (inp.type === "number" ? (inp.value === "" ? null : +inp.value) : inp.value);
          if (f === "current") { const end = $('[data-f="end"]', row); end.disabled = inp.checked; if (inp.checked) { end.value = ""; arr[i].end = ""; } }
          onChange?.();
        });
      });
      $("[data-del]", row).addEventListener("click", () => { arr.splice(i, 1); draw(); syncDerived(); });
    });
  };

  const bind = () => {
    $("#e-name", el)?.addEventListener("input", (e) => { form.name = e.target.value; });
    $("#e-head", el)?.addEventListener("input", (e) => { form.head = e.target.value; });
    $("#e-years", el)?.addEventListener("input", (e) => { form.years = e.target.value; form.yearsManual = true; });
    $("#e-edu", el)?.addEventListener("change", (e) => { form.edu = parseInt(e.target.value, 10); form.eduManual = true; });
    $("#edit-btn", el)?.addEventListener("click", () => { editing = true; draw(); });
    $("#cancel-edit", el)?.addEventListener("click", () => { editing = false; reset(); draw(); });
    $("#reveal", el)?.addEventListener("click", async (e) => {
      try {
        const d = await api.contact(c.id);
        $("#c-email", el).textContent = d.email || "—"; $("#c-phone", el).textContent = d.phone || "—"; e.target.remove();
      } catch (err) { toast(err.message, "err"); }
    });
    $$("#tech-chips [data-rm]", el).forEach((b) => b.addEventListener("click", () => { tech = tech.filter((s) => s.name !== b.parentElement.dataset.key); draw(); }));
    $$("#soft-chips [data-rm]", el).forEach((b) => b.addEventListener("click", () => { soft = soft.filter((s) => s.name !== b.parentElement.dataset.key); draw(); }));
    const adder = (inputId, btnId, arr) => {
      const inp = $(inputId, el), btn = $(btnId, el);
      if (!inp) return;
      const doAdd = () => {
        const v = inp.value.trim();
        if (!v) return;
        if (!arr().some((s) => s.name.toLowerCase() === v.toLowerCase()))
          arr().push({ name: v, confidence: 1, source: "Edición manual", evidence: "Agregada por Talento Humano" });
        draw();
        $(inputId, el)?.focus();
      };
      btn.addEventListener("click", doAdd);
      inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doAdd(); } });
    };
    adder("#add-tech", "#add-tech-btn", () => tech);
    adder("#add-soft", "#add-soft-btn", () => soft);

    if (editing) {
      bindRows("#exp-rows", exp, syncDerived);
      bindRows("#edu-rows", edu, syncDerived);
      bindRows("#cert-rows", certs);
      const focusLast = (sel) => { const rows = $$(`${sel} .edit-row`, el); rows[rows.length - 1]?.querySelector("input")?.focus(); };
      $("#add-exp", el).addEventListener("click", () => {
        exp.push({ role: "", company: "", start: "", end: "", current: false, years: 0, source: "Edición manual" });
        draw(); focusLast("#exp-rows");
      });
      $("#promote", el).addEventListener("click", () => {
        // Cierra el cargo actual el mes anterior y abre el nuevo cargo desde este mes
        const now = thisMonth();
        const cur = exp.find((e) => e.current);
        exp.forEach((e) => {
          if (!e.current) return;
          e.current = false;
          const pm = prevMonth(now);
          e.end = pm && ymIdx(pm) >= ymIdx(e.start) ? pm : (e.start || now);   // nunca antes de su inicio
        });
        exp.unshift({ role: "", company: cur?.company || "", start: now, end: "", current: true, years: 0, source: "Ascenso interno" });
        draw(); syncDerived();
        $("#exp-rows .edit-row input", el)?.focus();
        toast("Escribe el nuevo cargo. El cargo anterior quedó cerrado el mes pasado.", "info");
      });
      $("#add-edu", el).addEventListener("click", () => { edu.push({ title: "", institution: "", level: 0, status: "" }); draw(); focusLast("#edu-rows"); });
      $("#add-cert", el).addEventListener("click", () => { certs.push({ name: "", issuer: "", year: new Date().getFullYear(), internal: false }); draw(); focusLast("#cert-rows"); });
      $("#add-cert-int", el).addEventListener("click", () => { certs.push({ name: "", issuer: "Empresa (programa interno)", year: new Date().getFullYear(), internal: true }); draw(); focusLast("#cert-rows"); });
    }

    $("#save-edit", el)?.addEventListener("click", async (e) => {
      const badExp = exp.find((x) => (x.role || x.company) && x.start && !x.current && x.end && ymIdx(x.end) < ymIdx(x.start));
      if (badExp) { toast(`En «${badExp.role || badExp.company}» la fecha de fin es anterior a la de inicio`, "err"); return; }
      if (exp.some((x) => !x.role.trim() && !x.company.trim() && (x.start || x.current))) { toast("Hay una experiencia sin cargo ni empresa", "err"); return; }
      e.target.disabled = true; e.target.textContent = "Recalculando…";
      try {
        const res = await api.editProfile(c.id, {
          name: form.name, headline: form.head,
          tech_skills: tech.map((s) => s.name), soft_skills: soft.map((s) => s.name),
          years_experience: parseFloat(form.years || "0"), education_level: +form.edu,
          experience: exp.filter((x) => x.role.trim() || x.company.trim()).map((x) => ({
            role: x.role, company: x.company, start: x.start || null, end: x.current ? null : (x.end || null),
            current: x.current, years: x.start ? null : (x.years || null), source: x.source || null })),
          education: edu.filter((x) => x.title.trim() || x.institution.trim()).map((x) => ({ title: x.title, institution: x.institution, level: +x.level || 0, status: x.status || "" })),
          certifications: certs.filter((x) => x.name.trim()).map((x) => ({ name: x.name, issuer: x.issuer || "", year: x.year || null, internal: !!x.internal })),
        });
        setResult(res);
        toast("Perfil actualizado. Compatibilidad y plan recalculados.");
        renderProfile(el, go);
      } catch (err) { toast(err.message, "err"); e.target.disabled = false; e.target.textContent = "Guardar y recalcular"; }
    });
  };
  draw();
}
