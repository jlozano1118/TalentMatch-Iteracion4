import { api } from "../api.js";
import { clearWork, state } from "../state.js";
import { $, $$, animateIn, esc, fmtDate, ICONS, modal, ring, SOURCE_LABEL, toast } from "../ui.js";

export async function renderBank(el, go, openCandidate) {
  el.innerHTML = `
    <div class="page-head">
      <div><span class="kicker">Base de datos local · SQLite</span><h1>Banco de hojas de vida</h1>
      <p>Todas las hojas de vida analizadas con su mejor cargo, la compatibilidad con los demás proyectos y sus planes de capacitación. Desde aquí se atienden los derechos del titular: acceso y supresión.</p></div>
      <div class="actions"><button class="btn primary" data-go="cargar">${ICONS.upload.replace('width="26" height="26"', 'width="16" height="16"')} Cargar más</button></div>
    </div>
    <div class="toolbar">
      <input class="input" id="q" placeholder="Buscar por nombre, código, cargo o proyecto" autocomplete="off">
      <select class="input" id="src" style="max-width:200px"><option value="">Todas las fuentes</option>${Object.entries(SOURCE_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select>
    </div>
    <div class="grid" id="bank-list" style="gap:10px">${'<div class="card skeleton" style="height:74px"></div>'.repeat(3)}</div>`;

  let items = [];
  try { items = (await api.bank()).candidates; } catch (err) { toast(err.message, "err"); return; }

  const draw = () => {
    const q = $("#q", el).value.trim().toLowerCase(), src = $("#src", el).value;
    const list = items.filter((c) => (!src || c.source_type === src) &&
      (!q || [c.name, c.code, c.headline, c.best?.title, c.best?.project].join(" ").toLowerCase().includes(q)));
    $("#bank-list", el).innerHTML = list.length ? list.map((c) => `
      <div class="card bank-row hover">
        <span class="avatar">${esc(c.initials)}</span>
        <div style="min-width:0"><div class="nm">${esc(c.name)} <span class="tag mint">${esc(c.code)}</span></div>
          <div class="sub">${esc(c.headline || "—")} · ${c.years_experience} años · ${esc(c.education_label)} · ${esc(SOURCE_LABEL[c.source_type] || c.source_type)} · ${fmtDate(c.created_at)}</div></div>
        <div style="min-width:0">${c.best ? `<div style="display:flex;gap:10px;align-items:center">${ring(c.best.score, 44, 4, 11)}<div style="min-width:0"><b style="font-size:13.5px">${esc(c.best.title)}</b><div class="sub">${esc(c.best.project)}</div></div></div>` : '<span class="dim">Sin análisis</span>'}</div>
        <div class="dim" style="font-size:11.5px" title="Fecha límite de conservación">conservar hasta<br>${esc(c.retention_until)}</div>
        <div class="actions">
          <button class="btn sm" data-open="${c.id}">Abrir</button>
          <a class="btn sm ghost" href="${api.exportUrl(c.id)}" title="Reporte de datos del titular (habeas data)">${ICONS.download}</a>
          <button class="btn sm danger" data-del="${c.id}" title="Suprimir datos (derecho al olvido)">${ICONS.trash}</button>
        </div>
      </div>`).join("") : `<div class="card empty"><div class="serif">${items.length ? "Sin resultados" : "El banco está vacío"}</div>
        <p>${items.length ? "Ajusta la búsqueda o el filtro." : "Analiza la primera hoja de vida para comenzar."}</p>
        ${items.length ? "" : '<button class="btn primary" data-go="cargar">Cargar hoja de vida</button>'}</div>`;
    $$("[data-open]", el).forEach((b) => b.addEventListener("click", () => openCandidate(+b.dataset.open)));
    $$("[data-del]", el).forEach((b) => b.addEventListener("click", () => confirmDelete(items.find((c) => c.id === +b.dataset.del))));
    animateIn($("#bank-list", el));
  };

  const confirmDelete = (c) => modal(`
    <span class="kicker">Derecho de supresión · Ley 1581 art. 8e · RGPD art. 17</span><h3>Suprimir ${esc(c.code)}</h3>
    <p class="muted">Se eliminarán de forma definitiva la hoja de vida, la compatibilidad con todos los cargos, los planes de capacitación y las decisiones asociadas. La autorización quedará marcada como revocada y la bitácora conservará sólo el código seudónimo.</p>
    <div class="field"><label for="del-reason">Motivo</label><select class="input" id="del-reason">
      <option>Solicitud del titular</option><option>Revocatoria de la autorización</option><option>Datos cargados por error</option><option>Fin de la finalidad</option></select></div>
    <div class="actions" style="justify-content:flex-end"><button class="btn" data-close>Cancelar</button><button class="btn danger" id="del-ok">${ICONS.trash} Suprimir definitivamente</button></div>`,
  (box, close) => $("#del-ok", box).addEventListener("click", async () => {
    try {
      await api.remove(c.id, $("#del-reason", box).value);
      items = items.filter((x) => x.id !== c.id);
      if (state.result?.candidate.id === c.id) clearWork();
      close(); draw(); toast(`${c.code} suprimido de la base de datos`);
    } catch (err) { toast(err.message, "err"); }
  }));

  $("#q", el).addEventListener("input", draw);
  $("#src", el).addEventListener("change", draw);
  draw();
}
