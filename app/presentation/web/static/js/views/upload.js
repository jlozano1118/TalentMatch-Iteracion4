import { api } from "../api.js";
import { setResult, state } from "../state.js";
import { $, $$, esc, ICONS, modal, toast } from "../ui.js";

const ACCEPT = [".pdf", ".json", ".png", ".jpg", ".jpeg"];
const STEPS = [
  "Leyendo el documento",
  "Detectando si es escaneado (OCR)",
  "Descartando datos sensibles",
  "Identificando habilidades técnicas",
  "Identificando power skills y experiencia",
  "Calculando compatibilidad con los cargos",
  "Generando plan de capacitación",
  "Guardando en la base de datos local",
];

export function policyModal() {
  const p = state.policy;
  if (!p) return;
  modal(`
    <span class="kicker">Política ${esc(p.version)}</span>
    <h3>Tratamiento de datos personales</h3>
    <p class="muted" style="margin-top:0">${esc(p.responsable)}</p>
    <details class="acc" open><summary>Finalidades</summary><ul>${Object.values(p.finalidades).map((f) => `<li>${esc(f)}</li>`).join("")}<li><i>Opcional:</i> ${esc(p.finalidad_opcional)}</li></ul></details>
    <details class="acc"><summary>Datos tratados y datos excluidos</summary><ul>${p.datos_tratados.concat(p.datos_excluidos).map((f) => `<li>${esc(f)}</li>`).join("")}</ul></details>
    <details class="acc"><summary>Derechos del titular (habeas data)</summary><ul>${p.derechos.map((f) => `<li>${esc(f)}</li>`).join("")}</ul></details>
    <details class="acc"><summary>Seguridad y conservación</summary><ul><li>${esc(p.seguridad)}</li><li>${esc(p.retencion)}</li></ul></details>
    <div style="text-align:right;margin-top:14px"><button class="btn primary" data-close>Entendido</button></div>`);
}

export function renderUpload(el, go) {
  const p = state.policy || {};
  const aiAvailable = !!p.external_ai_available;
  el.innerHTML = `
    <div class="page-head">
      <div><span class="kicker">Paso 1 de 5</span><h1>Carga la hoja de vida</h1>
      <p>Sube uno o varios CV en PDF (con texto o escaneados), imagen o JSON. Se extraen habilidades técnicas, power skills y experiencia para establecer en qué proyectos y cargos tiene mayor compatibilidad.</p></div>
    </div>
    <div class="grid g2" style="align-items:start">
      <div class="card">
        <div class="card-title"><h3>${ICONS.shield} Autorización del titular</h3><span class="tag mint">Ley 1581 de 2012</span></div>
        <label class="check"><input type="checkbox" checked disabled><span><b>Matching con cargos de proyectos internos</b><small>Finalidad principal y necesaria para el análisis.</small></span></label>
        <label class="check"><input type="checkbox" id="p-cap" checked><span><b>Plan de capacitación personalizado</b><small>Recomendación de cursos para cerrar brechas.</small></span></label>
        <label class="check"><input type="checkbox" id="p-ai" ${aiAvailable ? "" : "disabled"}><span><b>Enriquecimiento con IA externa (Claude API)</b>
          <small>${aiAvailable ? "Opcional. El texto se anonimiza antes del envío y sólo se aceptan habilidades con evidencia literal." : "No configurado en este servidor: todo el análisis se realiza localmente."}</small></span></label>
        <div class="legal" style="margin:12px 0">${esc(p.texto_autorizacion || "")}</div>
        <label class="check" style="border:0"><input type="checkbox" id="p-attest"><span><b>Confirmo que el titular otorgó su autorización previa, expresa e informada.</b>
          <small>Se registra la versión de la política, las finalidades y la fecha como prueba de la autorización.</small></span></label>
        <button class="btn ghost sm" id="see-policy" style="margin-top:6px">Ver política completa</button>
      </div>
      <div>
        <div class="card">
          <div class="dropzone" id="dropzone" tabindex="0" role="button" aria-label="Seleccionar archivos">
            <div class="big-ico">${ICONS.upload}</div>
            <b>Arrastra tus archivos aquí</b>
            <div class="muted" style="font-size:13px;margin-top:4px">o haz clic para seleccionarlos · PDF, JSON, PNG, JPG · máx. 10 MB</div>
            <input type="file" id="file-input" accept="${ACCEPT.join(",")}" multiple hidden>
          </div>
          <div class="file-list" id="file-list"></div>
          <button class="btn primary" id="analyze-btn" style="width:100%;margin-top:16px;padding:13px" disabled>Analizar hoja de vida ${ICONS.arrow}</button>
          <div class="dim" id="analyze-hint" style="font-size:12.5px;margin-top:8px;text-align:center">Selecciona al menos un archivo y confirma la autorización.</div>
        </div>
        <div class="grid g3" style="margin-top:14px">
          <div class="card hover" style="padding:16px"><span class="tag mint">PDF</span><p style="margin:8px 0 0;font-size:13px" class="muted">Texto embebido extraído con precisión.</p></div>
          <div class="card hover" style="padding:16px"><span class="tag amber">OCR</span><p style="margin:8px 0 0;font-size:13px" class="muted">PDF escaneado o imagen: OCR automático.</p></div>
          <div class="card hover" style="padding:16px"><span class="tag blue">JSON</span><p style="margin:8px 0 0;font-size:13px" class="muted">JSON Resume, ATS u otros esquemas.</p></div>
        </div>
      </div>
    </div>`;

  let files = [];
  const input = $("#file-input", el), dz = $("#dropzone", el), list = $("#file-list", el), btn = $("#analyze-btn", el);
  const attest = $("#p-attest", el);

  const refresh = () => {
    list.innerHTML = files.map((f, i) => `<div class="file-item" data-i="${i}">${ICONS.file}<span>${esc(f.name)}</span>
      <span class="dim" style="font-size:12px">${(f.size / 1024).toFixed(0)} KB</span><span class="st dim" data-st>listo</span>
      <button class="icon-btn" data-rm="${i}" aria-label="Quitar">✕</button></div>`).join("");
    $$("[data-rm]", list).forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); files.splice(+b.dataset.rm, 1); refresh(); }));
    btn.disabled = !(files.length && attest.checked);
    btn.innerHTML = files.length > 1 ? `Analizar ${files.length} hojas de vida ${ICONS.arrow}` : `Analizar hoja de vida ${ICONS.arrow}`;
    $("#analyze-hint", el).classList.toggle("hidden", !btn.disabled);
  };
  const add = (fl) => {
    for (const f of fl) {
      const ext = "." + f.name.split(".").pop().toLowerCase();
      if (!ACCEPT.includes(ext)) { toast(`${f.name}: formato no permitido`, "err"); continue; }
      if (f.size > 10 * 1024 * 1024) { toast(`${f.name}: supera 10 MB`, "err"); continue; }
      if (files.length >= 15) { toast("Máximo 15 archivos por lote", "err"); break; }
      files.push(f);
    }
    refresh();
  };
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") input.click(); });
  input.addEventListener("change", () => { add(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => add(e.dataTransfer.files));
  attest.addEventListener("change", refresh);
  $("#see-policy", el).addEventListener("click", policyModal);

  btn.addEventListener("click", async () => {
    const consent = {
      attested: attest.checked,
      purposes: ["matching", ...($("#p-cap", el).checked ? ["capacitacion"] : [])],
      external_ai: $("#p-ai", el).checked,
    };
    btn.disabled = true;
    const ov = showOverlay(files.length);
    let last = null, ok = 0;
    for (let i = 0; i < files.length; i++) {
      const row = $(`.file-item[data-i="${i}"] [data-st]`, list);
      ov.file(i, files[i].name);
      try {
        const res = await api.analyze(files[i], consent);
        last = res; ok++;
        if (row) { row.textContent = res.duplicate ? "ya existía" : "analizado"; row.style.color = "var(--mint)"; }
        if (res.duplicate) toast(`${files[i].name}: ya estaba en el banco (${res.candidate.code}); se reutiliza su análisis.`, "info");
      } catch (err) {
        if (row) { row.textContent = "error"; row.style.color = "var(--red)"; }
        toast(`${files[i].name}: ${err.message}`, "err");
      }
    }
    await ov.finish();
    if (!last) { btn.disabled = false; return; }
    if (files.length === 1) {
      setResult(last);
      toast("Perfil extraído y guardado en el banco de CV");
      go("perfil");
    } else {
      toast(`${ok} de ${files.length} hojas de vida analizadas y guardadas`);
      go("banco");
    }
  });
}

function showOverlay(total) {
  const root = $("#overlay-root");
  root.innerHTML = `<div class="overlay"><div class="card analyze-box">
      <div class="spinner"></div>
      <h3 class="serif" style="font-size:32px;margin:0">Analizando el perfil</h3>
      <div class="muted mono" style="font-size:12.5px" id="ov-file"></div>
      <ul class="steps-list">${STEPS.map((s) => `<li><span class="b">·</span>${s}</li>`).join("")}</ul>
      <div class="progress"><i id="ov-bar"></i></div>
      <div class="dim mono" style="font-size:12px;margin-top:8px" id="ov-pct">0%</div></div></div>`;
  const items = $$(".steps-list li", root);
  let k = 0, fileIdx = 0;
  const paint = () => {
    items.forEach((li, i) => {
      li.className = i < k ? "ok" : i === k ? "on" : "";
      li.querySelector(".b").textContent = i < k ? "✓" : i === k ? "›" : "·";
    });
    const pct = Math.round(((fileIdx + Math.min(k, STEPS.length) / STEPS.length) / total) * 100);
    $("#ov-bar", root).style.width = pct + "%";
    $("#ov-pct", root).textContent = pct + "%";
  };
  const timer = setInterval(() => { if (k < STEPS.length - 1) { k++; paint(); } }, 650);
  paint();
  return {
    file(i, name) { fileIdx = i; k = 0; $("#ov-file", root).textContent = total > 1 ? `Archivo ${i + 1} de ${total} · ${name}` : name; paint(); },
    async finish() {
      clearInterval(timer);
      fileIdx = total - 1; k = STEPS.length; paint();
      await new Promise((r) => setTimeout(r, 550));
      root.innerHTML = "";
    },
  };
}
