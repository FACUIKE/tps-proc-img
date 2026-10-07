/*
 * Document Scanner — TP 2 (frontend)
 *
 * This file does NOT need to be modified: it consumes the API defined in the assignment.
 *
 * Where it looks for the API:
 *   - served by the backend (http://localhost:8765) → same origin;
 *   - opened as a file (file://) → http://localhost:8765;
 *   - for any other case, add ?api=http://host:port to the URL (it is remembered).
 */

"use strict";

const API_BASE = (() => {
  try {
    const param = new URLSearchParams(location.search).get("api");
    if (param) localStorage.setItem("apiBase", param);
    const saved = param || localStorage.getItem("apiBase");
    if (saved) return saved.replace(/\/$/, "");
  } catch { /* storage blocked */ }
  return location.protocol.startsWith("http") ? "" : "http://localhost:8765";
})();

/* ------------------------------------------------------------------------ */
/* Options (must match the backend)                                          */
/* ------------------------------------------------------------------------ */

const DEFAULT_OPTIONS = { color_mode: "color", color_correction: true, soften_colors: 0 };

const COLOR_MODES = {
  color: { label: "Color", help: "Keeps the colors of the document." },
  grayscale: { label: "Grayscale", help: "Shades of gray, a single channel." },
  bw: { label: "B&W", help: "Pure black and white, like a photocopy. Best for text." },
};

/* ------------------------------------------------------------------------ */
/* State                                                                     */
/* ------------------------------------------------------------------------ */

const state = {
  scans: [],           // list returned by GET /api/scans
  galleryError: null,  // ApiError if the listing failed
  source: null,        // photo being scanned: { name, url, file?, width, height }
  detection: null,     // { status: "pending" | "ok" | "missing" | "unavailable", corners?, width?, height?, error? }
  result: null,        // ScanOut of the scan being shown
  scanError: null,     // ApiError of the last failed scan
  options: { ...DEFAULT_OPTIONS },
  busy: false,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v === true) node.setAttribute(k, "");
    else if (v !== false && v != null) node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null) node.append(c);
  return node;
};
const svg = (tag, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};

/* ------------------------------------------------------------------------ */
/* HTTP client                                                               */
/* ------------------------------------------------------------------------ */

class ApiError extends Error {
  constructor(status, code, title, message) {
    super(message);
    this.status = status;
    this.code = code;
    this.title = title;
  }
  get notImplemented() { return this.code === "NOT_IMPLEMENTED"; }
  get documentNotFound() { return this.code === "DOCUMENT_NOT_FOUND"; }
}

function errorMessage(status, body) {
  const detail = body && body.detail !== undefined ? body.detail : body;
  if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.message) return detail.message;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors (422)
    return detail.map((e) => `${(e.loc || []).filter((p) => p !== "body").join(".") || "request"}: ${e.msg}`).join(" · ");
  }
  return `The server responded ${status}.`;
}

function errorTitle(status, code) {
  if (code === "DOCUMENT_NOT_FOUND") return "No document detected";
  if (code === "NOT_IMPLEMENTED") return "Not implemented yet";
  if (code === "UNSUPPORTED_FORMAT") return "Unsupported format";
  if (code === "INVALID_FILE") return "Invalid file";
  if (status === 0) return "No connection to the server";
  if (status === 404) return "Not found";
  if (status === 400 || status === 422) return "Invalid request";
  if (status === 413) return "File too large";
  if (status >= 500) return "Server error";
  return `Error ${status}`;
}

async function api(method, path, { formData } = {}) {
  let response;
  try {
    response = await fetch(API_BASE + path, { method, body: formData });
  } catch {
    const msg = `Could not connect to ${API_BASE || location.origin}. Is the backend running?`;
    throw new ApiError(0, null, errorTitle(0), msg);
  }

  const text = await response.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }

  if (!response.ok) {
    let code = body?.detail?.code ?? null;
    let msg = errorMessage(response.status, body);
    // An endpoint the backend does not have yet: FastAPI answers 404/405 with a plain string.
    if ((response.status === 404 || response.status === 405) && typeof body?.detail === "string") {
      code = "NOT_IMPLEMENTED";
      msg = `The backend does not implement ${method} ${path.split("?")[0]} yet.`;
    }
    throw new ApiError(response.status, code, errorTitle(response.status, code), msg);
  }
  return body;
}

const absoluteUrl = (url) => (/^(https?:|blob:|data:)/.test(url) ? url : API_BASE + url);
const publicUrl = (url) => new URL(absoluteUrl(url), location.href).href;

/* ------------------------------------------------------------------------ */
/* Notifications                                                             */
/* ------------------------------------------------------------------------ */

function toast(kind, title, message) {
  const node = el("div", { class: `toast ${kind}`, role: "status" },
    el("div", {}, el("strong", {}, title), message ? el("p", {}, message) : null));
  const container = $("#toasts");
  container.append(node);
  while (container.children.length > 3) container.firstElementChild.remove();
  setTimeout(() => {
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 250);
  }, kind === "ok" ? 3000 : 6000);
}

function toastError(err) {
  if (err instanceof ApiError) {
    toast(err.notImplemented || err.documentNotFound ? "warn" : "err", err.title, err.message);
  } else {
    console.error(err);
    toast("err", "Unexpected error", String(err.message || err));
  }
}

/* ------------------------------------------------------------------------ */
/* Server                                                                    */
/* ------------------------------------------------------------------------ */

async function checkServer() {
  const pill = $("#server-status");
  try {
    const r = await fetch(API_BASE + "/api/health");
    if (!r.ok) throw new Error();
    pill.dataset.status = "ok";
    pill.querySelector(".status-text").textContent = "Server connected";
  } catch {
    pill.dataset.status = "error";
    pill.querySelector(".status-text").textContent = "Server disconnected";
  }
}

/* ------------------------------------------------------------------------ */
/* Gallery                                                                   */
/* ------------------------------------------------------------------------ */

async function loadGallery() {
  try {
    state.scans = await api("GET", "/api/scans");
    state.galleryError = null;
  } catch (err) {
    state.scans = [];
    state.galleryError = err;
  }
  renderGallery();
}

const formatDate = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString([], { dateStyle: "short", timeStyle: "short" });
};

function renderGallery() {
  const gallery = $("#gallery");
  const error = state.galleryError;
  if (error) {
    const cls = error.notImplemented ? "notice notice-warn" : "notice notice-err";
    gallery.replaceChildren(el("div", { class: cls }, el("strong", {}, error.title + ". "), error.message));
    return;
  }
  if (!state.scans.length) {
    gallery.replaceChildren(el("div", { class: "notice" }, "No scans saved yet."));
    return;
  }
  gallery.replaceChildren(...state.scans.map((scan) => {
    const active = state.result?.id === scan.id;
    const mode = COLOR_MODES[scan.options?.color_mode]?.label ?? scan.options?.color_mode ?? "";
    return el("div", {
      class: `item${active ? " active" : ""}`, role: "button", tabindex: "0",
      title: scan.original_name,
      onclick: () => selectScan(scan),
      onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectScan(scan); } },
    },
      el("img", { class: "item-thumb", src: absoluteUrl(scan.url), alt: "", loading: "lazy" }),
      el("div", { class: "item-info" },
        el("div", { class: "item-name" }, scan.original_name),
        el("div", { class: "item-detail" },
          el("span", { class: "badge badge-op" }, mode), ` ${formatDate(scan.created_at)}`)),
      el("button", {
        class: "item-delete", title: "Delete", "aria-label": `Delete scan of ${scan.original_name}`,
        onclick: (e) => { e.stopPropagation(); deleteScan(scan); },
      }, "×"),
    );
  }));
}

async function deleteScan(scan) {
  try {
    await api("DELETE", `/api/scans/${encodeURIComponent(scan.id)}`);
    toast("ok", "Scan deleted", scan.original_name);
    if (state.result?.id === scan.id) {
      state.result = null;
      if (!state.source?.file) { setSource(null); state.detection = null; }
      render();
    }
    await loadGallery();
  } catch (err) {
    toastError(err);
  }
}

async function selectScan(item) {
  if (state.busy) return;
  // Requests the stored version from the server (exercises GET /api/scans/{id}).
  let scan = item;
  try {
    scan = await api("GET", `/api/scans/${encodeURIComponent(item.id)}`);
  } catch (err) {
    toastError(err);
  }
  setSource({ name: scan.original_name, url: absoluteUrl(scan.original_url) });
  state.detection = { status: "ok", corners: scan.corners };
  state.result = scan;
  state.scanError = null;
  state.options = { ...DEFAULT_OPTIONS, ...scan.options };
  renderOptions();
  render();
  renderGallery();
  measureSource();
}

/* ------------------------------------------------------------------------ */
/* Upload, detection and scan                                                */
/* ------------------------------------------------------------------------ */

const FORMATS = ["image/png", "image/jpeg", "image/webp", "image/bmp"];
const MAX_BYTES = 10 * 1024 * 1024;

function setSource(source) {
  if (state.source?.file) URL.revokeObjectURL(state.source.url);
  state.source = source;
}

async function uploadFile(file) {
  if (!file || state.busy) return;
  if (!FORMATS.includes(file.type)) {
    toast("err", "Unsupported format", `${file.name} (${file.type || "unknown"}). Use PNG, JPG, WEBP or BMP.`);
    return;
  }
  if (file.size > MAX_BYTES) {
    toast("err", "File too large", "The maximum is 10 MB.");
    return;
  }

  setSource({ name: file.name, url: URL.createObjectURL(file), file });
  state.result = null;
  state.scanError = null;
  state.detection = { status: "pending" };
  render();
  renderGallery();
  measureSource();

  const found = await detect();
  if (found) await runScan();
}

async function measureSource() {
  const source = state.source;
  if (!source) return;
  const size = await new Promise((ok) => {
    const img = new Image();
    img.onload = () => ok({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => ok(null);
    img.src = source.url;
  });
  if (size && state.source === source) {
    Object.assign(source, size);
    renderPhoto();
  }
}

function formWithFile(file, name, options) {
  const fd = new FormData();
  fd.append("file", file, name);
  if (options) {
    fd.append("color_mode", options.color_mode);
    fd.append("color_correction", String(options.color_correction));
    fd.append("soften_colors", String(options.soften_colors));
  }
  return fd;
}

/** Asks the backend where the document is. Returns false if it is certain there is none. */
async function detect() {
  const source = state.source;
  try {
    const body = await api("POST", "/api/detect", { formData: formWithFile(source.file, source.name) });
    if (state.source !== source) return false;
    state.detection = { status: "ok", ...body };
    render();
    return true;
  } catch (err) {
    if (state.source !== source) return false;
    if (err.notImplemented) {
      // No detection endpoint yet: try the scan anyway.
      state.detection = { status: "unavailable" };
      toastError(err);
      render();
      return true;
    }
    state.detection = { status: "missing", error: err };
    state.scanError = err;
    if (!err.documentNotFound) toastError(err);
    render();
    return false;
  }
}

async function sourceFile() {
  const source = state.source;
  if (source.file) return source.file;
  // A stored scan: the original photo is downloaded again to scan it with other options.
  const r = await fetch(source.url);
  if (!r.ok) throw new ApiError(r.status, null, "Original photo not available", `GET ${source.url} responded ${r.status}.`);
  return r.blob();
}

async function runScan() {
  const source = state.source;
  if (!source || state.busy) return;
  state.busy = true;
  state.scanError = null;
  render();
  try {
    const file = await sourceFile();
    const scan = await api("POST", "/api/scans", { formData: formWithFile(file, source.name, state.options) });
    state.result = scan;
    state.detection = { ...state.detection, status: "ok", corners: scan.corners };
    toast("ok", "Document scanned", `${scan.width}×${scan.height} · ${COLOR_MODES[scan.options?.color_mode]?.label ?? ""}`);
    await loadGallery();
  } catch (err) {
    state.scanError = err;
    if (err.documentNotFound) state.detection = { status: "missing", error: err };
    else toastError(err);
  } finally {
    state.busy = false;
    render();
  }
}

/* ------------------------------------------------------------------------ */
/* View                                                                      */
/* ------------------------------------------------------------------------ */

const formatBytes = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

function problemBox(err) {
  if (err.documentNotFound) {
    return el("div", { class: "problem warn", role: "alert" },
      el("strong", {}, "No document detected"),
      el("p", {}, err.message),
      el("ul", {},
        el("li", {}, "Show the whole page, with its four corners."),
        el("li", {}, "Use a background that contrasts with the paper."),
        el("li", {}, "Avoid strong shadows and reflections.")));
  }
  const cls = err.notImplemented ? "problem warn" : "problem";
  return el("div", { class: cls, role: "alert" }, el("strong", {}, err.title), el("p", {}, err.message));
}

function overlay(corners, width, height) {
  const r = Math.max(width, height) * 0.012;
  const layer = svg("svg", { viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: "none", "aria-hidden": "true" });
  layer.append(svg("polygon", {
    class: "outline", points: corners.map(([x, y]) => `${x},${y}`).join(" "), "vector-effect": "non-scaling-stroke",
  }));
  for (const [x, y] of corners) {
    layer.append(svg("circle", { class: "corner", cx: x, cy: y, r, "vector-effect": "non-scaling-stroke" }));
  }
  return layer;
}

function renderPhoto() {
  const frame = $("#photo-frame");
  const source = state.source;
  const detection = state.detection;
  frame.classList.toggle("loading", detection?.status === "pending");
  $("#photo-meta").textContent = source
    ? [source.width ? `${source.width}×${source.height}` : null, source.name].filter(Boolean).join(" · ")
    : "";
  if (!source) {
    frame.replaceChildren(el("div", { class: "empty" }, "Upload a photo or pick a scan to get started"));
    return;
  }

  const width = detection?.width || source.width;
  const height = detection?.height || source.height;
  const children = [];
  if (width && height) {
    const stage = el("div", { class: "stage", style: `--ar: ${width} / ${height}` },
      el("img", { src: source.url, alt: source.name }));
    if (detection?.status === "ok" && detection.corners?.length === 4) stage.append(overlay(detection.corners, width, height));
    children.push(stage);
  } else {
    children.push(el("div", { class: "empty" }, "Loading photo…"));
  }

  const stamp = {
    ok: ["badge-op", "Document detected"],
    missing: ["badge-warn", state.detection?.error?.documentNotFound ? "No document found" : "Could not read the photo"],
    unavailable: ["badge-warn", "Detection not available"],
  }[detection?.status];
  if (stamp) children.push(el("span", { class: `badge stamp ${stamp[0]}` }, stamp[1]));
  frame.replaceChildren(...children);
}

function renderScan() {
  const frame = $("#scan-frame");
  const scan = state.result;
  frame.classList.toggle("loading", state.busy);
  $("#scan-actions").hidden = !scan || Boolean(state.scanError);

  if (state.scanError) {
    $("#scan-meta").textContent = "";
    frame.replaceChildren(problemBox(state.scanError));
    return;
  }
  if (!scan) {
    $("#scan-meta").textContent = "";
    const text = state.busy ? "Scanning…" : "The scanned document will appear here";
    frame.replaceChildren(el("div", { class: "empty" }, text));
    return;
  }

  const mode = COLOR_MODES[scan.options?.color_mode]?.label ?? scan.options?.color_mode;
  $("#scan-meta").textContent = [`${scan.width}×${scan.height}`, "PNG", scan.size_bytes ? formatBytes(scan.size_bytes) : null]
    .filter(Boolean).join(" · ");
  frame.replaceChildren(
    el("img", { src: absoluteUrl(scan.url), alt: `Scan of ${scan.original_name}` }),
    el("span", { class: "badge stamp badge-op" }, mode));

  const a = $("#btn-download");
  a.href = absoluteUrl(scan.url);
  a.download = `${scan.original_name.replace(/\.[^.]+$/, "") || "scan"}-scan.png`;
  $("#btn-json").href = absoluteUrl(`/api/scans/${encodeURIComponent(scan.id)}`);
}

function renderScanButton() {
  const button = $("#btn-scan");
  const blocked = state.detection?.status === "pending";
  button.disabled = state.busy || !state.source || blocked;
  button.textContent = state.busy ? "Scanning…" : state.result ? "Scan again" : "Scan document";
}

function render() {
  renderPhoto();
  renderScan();
  renderScanButton();
}

/* ------------------------------------------------------------------------ */
/* Options                                                                   */
/* ------------------------------------------------------------------------ */

function renderOptions() {
  const o = state.options;
  for (const button of document.querySelectorAll("#color-mode button")) {
    button.setAttribute("aria-pressed", String(button.dataset.value === o.color_mode));
  }
  $("#color-mode-help").textContent = COLOR_MODES[o.color_mode]?.help ?? "";
  $("#color-correction").checked = Boolean(o.color_correction);
  $("#soften-colors").value = o.soften_colors;
  $("#soften-value").textContent = Number(o.soften_colors) === 0 ? "off" : Number(o.soften_colors).toFixed(2);
  renderCurl();
}

function renderCurl() {
  const o = state.options;
  const base = API_BASE || location.origin;
  $("#curl").textContent = [
    `curl -F "file=@photo.jpg" \\`,
    `     -F "color_mode=${o.color_mode}" \\`,
    `     -F "color_correction=${o.color_correction}" \\`,
    `     -F "soften_colors=${o.soften_colors}" \\`,
    `     ${base}/api/scans`,
  ].join("\n");
}

async function copyLink() {
  if (!state.result) return;
  const url = publicUrl(state.result.url);
  try {
    await navigator.clipboard.writeText(url);
    toast("ok", "Link copied", url);
  } catch {
    toast("warn", "Could not copy automatically", url);
  }
}

/* ------------------------------------------------------------------------ */
/* Events                                                                    */
/* ------------------------------------------------------------------------ */

function bindEvents() {
  $("#file-input").addEventListener("change", (e) => {
    uploadFile(e.target.files[0]);
    e.target.value = "";
  });

  const zone = $("#dropzone");
  ["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, () => zone.classList.remove("dragging")));
  zone.addEventListener("drop", (e) => { e.preventDefault(); uploadFile(e.dataTransfer.files[0]); });

  $("#btn-refresh").addEventListener("click", loadGallery);

  for (const button of document.querySelectorAll("#color-mode button")) {
    button.addEventListener("click", () => { state.options.color_mode = button.dataset.value; renderOptions(); });
  }
  $("#color-correction").addEventListener("change", (e) => { state.options.color_correction = e.target.checked; renderOptions(); });
  $("#soften-colors").addEventListener("input", (e) => { state.options.soften_colors = Number(e.target.value); renderOptions(); });

  $("#btn-reset").addEventListener("click", () => { state.options = { ...DEFAULT_OPTIONS }; renderOptions(); });
  $("#options-form").addEventListener("submit", (e) => { e.preventDefault(); runScan(); });
  $("#btn-copy").addEventListener("click", copyLink);
}

function init() {
  $("#link-docs").href = (API_BASE || "") + "/docs";
  renderOptions();
  render();
  bindEvents();
  checkServer();
  loadGallery();
}

init();
