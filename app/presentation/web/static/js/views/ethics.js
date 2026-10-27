import { api } from "../api.js";
import { state } from "../state.js";
import { $, animateIn, esc, ICONS, SOURCE_LABEL } from "../ui.js";
import { policyModal } from "./upload.js";

export async function renderEthics(el) {
  el.innerHTML = `
    <div class="page-head">
      <div><span class="kicker">Unidad 5 · Evaluación crítica, ética y responsabilidad en IA</span><h1>Ética y privacidad</h1>
      <p>Tarjeta de Evaluación Ética del prototipo, métricas medidas con evidencia, cumplimiento normativo (Ley 1581, RGPD, AI Act) y bitácora de auditoría.</p></div>
      <div class="actions"><button class="btn" id="pol">${ICONS.shield} Política de tratamiento</button></div>
    </div>
    <div id="eth-body"><div class="card skeleton" style="height:240px"></div></div>`;
  $("#pol", el).addEventListener("click", policyModal);

  let e, au;
  try { [e, au] = await Promise.all([api.ethics(), api.audit()]); } catch { return; }
  const L = e.live, B = e.benchmark;
  const srcRows = Object.entries(L.puntaje_promedio_por_fuente);

  $("#eth-body", el).innerHTML = `
    <span class="label">Tarjeta de Evaluación Ética · TalentMatch</span>
    <div class="card ethic-card reveal">
      <div><span class="kicker">¿Qué hace el sistema?</span><h4>Matching interno de talento</h4><ul>
        <li>Propósito: visibilizar la movilidad interna y objetivar la asignación de personal a cargos de proyectos.</li>
        <li>Usuarios: analistas de Talento Humano (4 cuentas autorizadas @talentmatch.co).</li>
        <li>Salida: compatibilidad explicable + plan de capacitación. <b>No decide</b>: recomienda.</li></ul></div>
      <div><span class="kicker">¿Qué datos usa?</span><h4>CV con autorización + datasets públicos</h4><ul>
        <li>CV de colaboradores con autorización previa, expresa e informada (versión de política registrada).</li>
        <li>3.000 ofertas (JobsDatasetProcessed), 3.522 cursos Coursera y 9.968 Udemy.</li>
        <li>Sesgo posible: ofertas en inglés de EE. UU.; se mitiga con sinónimos ES↔EN y edición humana.</li></ul></div>
      <div><span class="kicker">¿Cómo se evaluó?</span><h4>Métricas definidas antes de construir</h4><ul>
        ${B ? `<li>Precisión de extracción técnica: <b>${B.precision_tecnica}%</b> · exhaustividad: <b>${B.recall_tecnica}%</b>.</li>
        <li>Línea base ingenua (sólo lista de habilidades): exhaustividad ${B.baseline_recall_tecnica}% → mejora de ${(B.recall_tecnica - B.baseline_recall_tecnica).toFixed(1)} pts.</li>
        <li>Conjunto de prueba: ${B.n} CV (PDF texto, escaneado, imagen, 2 JSON). Limitación: conjunto pequeño y sintético.</li>`
          : "<li>Ejecutando el banco de pruebas de extracción… recarga en unos segundos.</li>"}</ul></div>
      <div><span class="kicker">¿Qué riesgos tiene?</span><h4>Riesgo crítico: decisiones injustas sobre personas</h4><ul>
        <li>Errores de OCR que penalicen CV escaneados → indicador de equidad por fuente.</li>
        <li>Sobre-confianza en el puntaje → supervisión humana obligatoria con justificación.</li>
        <li>Mitigación: evidencia literal por habilidad, datos sensibles excluidos, edición del perfil y auditoría.</li></ul></div>
    </div>

    <div class="grid g4" style="margin-top:18px">
      <div class="card stat reveal"><div class="v" data-count="${L.candidatos}" data-suffix="">0</div><div class="k">hojas de vida tratadas con autorización</div></div>
      <div class="card stat reveal"><div class="v" data-count="${L.habilidades_con_evidencia_pct}">0</div><div class="k">habilidades con evidencia literal (anti-alucinación)</div></div>
      <div class="card stat reveal"><div class="v" data-count="${L.movilidad_interna_pct}">0</div><div class="k">colaboradores con ≥1 cargo ≥ 60% (impacto social: movilidad interna)</div></div>
      <div class="card stat reveal"><div class="v" data-count="${L.decisiones_humanas}" data-suffix="">0</div><div class="k">decisiones humanas registradas con justificación</div></div>
    </div>

    <div class="grid g2" style="margin-top:18px;align-items:start">
      <div class="card reveal">
        <div class="card-title"><h3>Calidad de la extracción vs. línea base</h3><span class="tag">conjunto etiquetado</span></div>
        ${B ? `<div class="bars">${[["Precisión técnica", B.precision_tecnica], ["Exhaustividad técnica", B.recall_tecnica], ["Línea base (exhaustividad)", B.baseline_recall_tecnica],
          ["Precisión power skills", B.precision_power], ["Exhaustividad power skills", B.recall_power]].map(([k, v]) => `
          <div class="bar-row"><div class="top"><span>${k}</span><span>${v}%</span></div><div class="hbar"><i data-w="${v}" style="background:${k.startsWith("Línea") ? "var(--dim)" : "var(--mint)"}"></i></div></div>`).join("")}</div>
          <p class="dim" style="font-size:12.5px;margin:12px 0 0">Años de experiencia correctos: ${B.anos_ok}/${B.n} · nivel educativo: ${B.educacion_ok}/${B.n} · datos sensibles descartados: ${B.sensibles_ok}/${B.n}</p>`
          : '<p class="muted">Calculando… (incluye OCR de documentos escaneados)</p>'}
      </div>
      <div class="card reveal">
        <div class="card-title"><h3>Indicador de equidad · tipo de CV</h3>${L.alerta_equidad ? '<span class="tag red">alerta</span>' : '<span class="tag mint">dentro del umbral</span>'}</div>
        <p class="muted" style="font-size:13.5px;margin:-4px 0 14px">Quien sólo tiene un CV escaneado o en imagen no debe recibir peor puntaje por limitaciones del OCR. Umbral: diferencia ≤ 10 puntos entre fuentes.</p>
        ${srcRows.length ? `<div class="bars">${srcRows.map(([k, v]) => `<div class="bar-row"><div class="top"><span>${esc(SOURCE_LABEL[k] || k)} <span class="dim">· ${L.por_fuente[k]} CV</span></span><span>${v}%</span></div><div class="hbar"><i data-w="${v}"></i></div></div>`).join("")}</div>
          <p style="margin:12px 0 0;font-size:14px">Brecha entre fuentes: <b style="color:${L.alerta_equidad ? "var(--red)" : "var(--mint)"}">${L.brecha_equidad_fuente} pts</b>${L.alerta_equidad ? " — revisar manualmente los perfiles escaneados." : ""}</p>`
          : '<p class="muted">Se calcula cuando haya CV en el banco.</p>'}
        <p class="dim" style="font-size:12.5px;margin:10px 0 0">Confianza promedio de extracción: ${L.confianza_promedio}% · completitud promedio: ${L.completitud_promedio}%</p>
      </div>
    </div>

    <div style="margin:30px 0 12px" class="reveal"><span class="kicker">Principios de IA responsable</span></div>
    <div class="principles reveal">
      <div class="card hover"><span class="tag mint">Equidad</span><h4>Sin variables discriminatorias</h4><p>El puntaje sólo usa habilidades, experiencia y formación. Edad, género, foto, estado civil u origen se descartan.</p></div>
      <div class="card hover"><span class="tag blue">Transparencia</span><h4>Puntaje explicable</h4><p>Desglose por dimensión, pesos visibles, brecha requisito por requisito y evidencia literal de cada habilidad.</p></div>
      <div class="card hover"><span class="tag violet">Seguridad y privacidad</span><h4>Privacidad por diseño</h4><p>Cifrado de contacto, archivo original no almacenado, bcrypt, sesión HttpOnly, CSP y bloqueo de cuenta.</p></div>
      <div class="card hover"><span class="tag amber">Responsabilidad</span><h4>Humano en el circuito</h4><p>Cada asignación la decide y justifica una persona identificada; todo queda en la bitácora.</p></div>
      <div class="card hover"><span class="tag mint">Beneficencia social</span><h4>Crecer, no excluir</h4><p>Cada brecha se convierte en un plan de capacitación: el sistema impulsa la movilidad, no el reemplazo.</p></div>
    </div>

    <div class="card reveal" style="margin-top:18px">
      <div class="card-title"><h3>Cumplimiento normativo</h3><span class="tag">marcos regulatorios clave</span></div>
      <div style="overflow-x:auto"><table class="compliance"><thead><tr><th>Marco</th><th>Exigencia</th><th>Cómo lo cumple TalentMatch</th></tr></thead><tbody>
        <tr><td>Ley 1581 de 2012 · Decreto 1377 de 2013</td><td>Autorización previa, expresa e informada; finalidad; prueba de la autorización</td><td>Módulo de consentimiento por finalidades antes de cada carga; se guarda versión de política, finalidades, fecha y responsable.</td></tr>
        <tr><td>Ley 1581 · habeas data (art. 8)</td><td>Conocer, actualizar, rectificar, suprimir, revocar</td><td>Edición del perfil (rectificación), reporte descargable del titular (acceso), supresión con revocatoria y borrado en cascada.</td></tr>
        <tr><td>Ley 1581 · datos sensibles (art. 5–6)</td><td>Tratamiento restringido</td><td>Detección automática y descarte de identificación, nacimiento, edad, género, estado civil, religión, salud, origen, foto y referencias.</td></tr>
        <tr><td>RGPD art. 5 · 17 · 20 · 22 · 25</td><td>Minimización, derecho al olvido, portabilidad, no decisiones solo automatizadas, privacidad por diseño</td><td>No se guarda el archivo (sólo huella SHA-256); retención de ${esc(state.policy?.retencion?.match(/\d+/)?.[0] || "365")} días con purga automática; exportación; decisión humana obligatoria.</td></tr>
        <tr><td>AI Act (UE) 2024/1689</td><td>IA para selección y gestión de personal = alto riesgo (Anexo III, 4): supervisión humana, transparencia, registros, calidad de datos</td><td>Panel de decisión humana, explicación del puntaje, bitácora de eventos, evaluación con métricas y línea base. Sin reconocimiento de emociones ni biometría (prácticas prohibidas).</td></tr>
        <tr><td>Datos en el prompt</td><td>Evitar enviar datos confidenciales a APIs externas</td><td>Procesamiento local por defecto. IA externa sólo con casilla independiente y texto anonimizado; se rechaza todo lo que no tenga evidencia literal.</td></tr>
      </tbody></table></div>
    </div>

    <div class="grid g2" style="margin-top:18px;align-items:start">
      <div class="card reveal">
        <div class="card-title"><h3>Riesgos y mitigaciones</h3></div>
        <details class="acc" open><summary>Alucinación</summary><ul><li>Extracción determinista con evidencia; la IA externa (opcional) sólo aporta habilidades verificables en el texto.</li></ul></details>
        <details class="acc"><summary>Sesgo de datos</summary><ul><li>Ofertas de EE. UU. en inglés: sinónimos ES↔EN y crédito parcial por habilidades relacionadas; RR. HH. puede ajustar pesos y perfil.</li></ul></details>
        <details class="acc"><summary>Reidentificación</summary><ul><li>Seudónimo TM-XXXX en bitácora y matching; contacto cifrado y enmascarado, revelarlo queda auditado.</li></ul></details>
        <details class="acc"><summary>Impacto organizacional</summary><ul><li>No automatiza empleos: apoya decisiones y orienta la capacitación (plan de transición), evitando dependencia ciega del puntaje.</li></ul></details>
        <details class="acc"><summary>Seguridad</summary><ul><li>Sólo 4 cuentas autorizadas; bcrypt (coste 12), JWT en cookie HttpOnly/SameSite=Strict, bloqueo tras 5 intentos, CSP y escape de todo contenido del CV.</li></ul></details>
      </div>
      <div class="card reveal">
        <div class="card-title"><h3>Bitácora de auditoría</h3><span class="tag">sin datos personales</span></div>
        <div class="audit"><table><tbody>${au.events.map((x) => `<tr><td>${new Date(x.when).toLocaleString("es-CO")}</td><td>${esc(x.user.split("@")[0])}</td><td style="color:var(--text)">${esc(x.action)}</td><td>${esc(x.ref)}</td></tr>`).join("")}</tbody></table></div>
      </div>
    </div>
    <p class="dim" style="font-size:12px;margin-top:18px">Motor OCR: ${e.ocr ? "disponible" : "no instalado"} · IA externa: ${e.external_ai ? "configurada (requiere autorización del titular)" : "desactivada (procesamiento 100% local)"}</p>`;
  animateIn($("#eth-body", el));
  if (e.benchmark_running) setTimeout(() => { if (document.body.contains(el) && !el.classList.contains("hidden")) renderEthics(el); }, 9000);
}
