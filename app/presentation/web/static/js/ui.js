// Utilidades de interfaz: escape seguro, anillos, toasts, modales, animaciones.
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// Todo dato proveniente de un CV es no confiable: siempre se escapa antes de insertarlo.
export function esc(v) {
  return String(v ?? "").replace(/[&<>"'`]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" }[c]));
}

export function safeUrl(u) {
  try {
    const url = new URL(u);
    return ["https:", "http:"].includes(url.protocol) ? url.href : "#";
  } catch { return "#"; }
}

export function scoreColor(s) {
  return s >= 75 ? "var(--mint)" : s >= 55 ? "var(--amber)" : "var(--red)";
}
export function scoreLabel(s) {
  return s >= 75 ? "Encaje alto" : s >= 55 ? "Encaje medio" : "Encaje bajo";
}

export function ring(score, size = 64, stroke = 5, fontSize = null) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const fs = fontSize || Math.round(size * 0.24);
  const shown = size < 70 ? Math.round(score) : score;
  return `<div class="ring" style="width:${size}px;height:${size}px">
    <svg width="${size}" height="${size}"><circle class="track" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke-width="${stroke}"/>
    <circle class="bar" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${scoreColor(score)}" stroke-width="${stroke}"
      stroke-dasharray="${c}" stroke-dashoffset="${c}" data-target="${c * (1 - Math.max(0, Math.min(100, score)) / 100)}"/></svg>
    <span class="val" style="font-size:${fs}px;color:${scoreColor(score)}" data-count="${shown}">0%</span></div>`;
}

export function animateIn(root = document) {
  requestAnimationFrame(() => {
    $$(".ring .bar[data-target]", root).forEach((el) => { el.style.strokeDashoffset = el.dataset.target; });
    $$("[data-count]", root).forEach((el) => countUp(el, parseFloat(el.dataset.count), el.dataset.suffix ?? "%"));
    $$(".hbar > i[data-w], .gauge > i[data-w]", root).forEach((el) => { el.style.width = el.dataset.w + "%"; });
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.08 });
    $$(".reveal", root).forEach((el) => io.observe(el));
  });
}

export function countUp(el, target, suffix = "") {
  const dec = Number.isInteger(target) ? 0 : 1;
  const t0 = performance.now();
  const dur = 1100;
  const step = (t) => {
    const p = Math.min(1, (t - t0) / dur);
    const v = target * (1 - Math.pow(1 - p, 3));
    el.textContent = v.toLocaleString("es-CO", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suffix;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function toast(msg, type = "ok") {
  const box = $("#toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type === "ok" ? "✓" : type === "err" ? "✕" : "i"}</span><span>${esc(msg)}</span>`;
  box.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .4s"; }, 4200);
  setTimeout(() => el.remove(), 4700);
}

export function modal(html, onMount) {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal" role="dialog" aria-modal="true"><div class="card">${html}</div></div>`;
  const close = () => { root.innerHTML = ""; document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  $(".modal", root).addEventListener("click", (e) => { if (e.target.classList.contains("modal")) close(); });
  $$("[data-close]", root).forEach((b) => b.addEventListener("click", close));
  if (onMount) onMount($(".modal .card", root), close);
  return close;
}

export function stars(r) {
  const full = Math.round(r);
  return "★".repeat(full) + "☆".repeat(5 - full);
}

export function fmtDate(iso) {
  try { return new Date(iso).toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" }); } catch { return iso; }
}

export const SOURCE_LABEL = { "pdf-texto": "PDF texto", "pdf-escaneado": "PDF escaneado", imagen: "Imagen", json: "JSON" };
export const DECISION_LABEL = { asignar: "Asignado", en_revision: "En revisión", descartar: "Descartado" };

export function typeWriter(el, phrases, speed = 38) {
  let i = 0, j = 0, del = false;
  const tick = () => {
    if (!document.body.contains(el)) return;
    const p = phrases[i];
    el.textContent = p.slice(0, j);
    if (!del && j < p.length) j++;
    else if (!del) { del = true; return setTimeout(tick, 1800); }
    else if (j > 0) j--;
    else { del = false; i = (i + 1) % phrases.length; }
    setTimeout(tick, del ? speed / 2 : speed);
  };
  tick();
}

export function particles(canvas) {
  const ctx = canvas.getContext("2d");
  let w, h, pts;
  const resize = () => {
    w = canvas.width = canvas.offsetWidth * devicePixelRatio;
    h = canvas.height = canvas.offsetHeight * devicePixelRatio;
    pts = Array.from({ length: 46 }, () => ({ x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35 }));
  };
  resize();
  window.addEventListener("resize", resize);
  const loop = () => {
    if (!document.body.contains(canvas) || canvas.offsetParent === null) return requestAnimationFrame(loop);
    ctx.clearRect(0, 0, w, h);
    for (const p of pts) {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > w) p.vx *= -1;
      if (p.y < 0 || p.y > h) p.vy *= -1;
      ctx.fillStyle = "rgba(25,227,161,.7)";
      ctx.beginPath(); ctx.arc(p.x, p.y, 1.6 * devicePixelRatio, 0, 7); ctx.fill();
    }
    for (let a = 0; a < pts.length; a++) for (let b = a + 1; b < pts.length; b++) {
      const d = Math.hypot(pts[a].x - pts[b].x, pts[a].y - pts[b].y);
      if (d < 140 * devicePixelRatio) {
        ctx.strokeStyle = `rgba(25,227,161,${0.18 * (1 - d / (140 * devicePixelRatio))})`;
        ctx.beginPath(); ctx.moveTo(pts[a].x, pts[a].y); ctx.lineTo(pts[b].x, pts[b].y); ctx.stroke();
      }
    }
    requestAnimationFrame(loop);
  };
  loop();
}

export const ICONS = {
  upload: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>',
  file: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg>',
  shield: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
  ext: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>',
  chev: '<svg class="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>',
  edit: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/></svg>',
  arrow: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>',
  back: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>',
  trash: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>',
  download: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>',
  eye: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  note: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex:none;margin-top:2px"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
  music: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
};
