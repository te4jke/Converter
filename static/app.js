const MODES = {
  convert: {
    multi: true,
    go: "Конвертировать",
    hint: ["Бросьте файл на карту", "Станции подсветятся там, куда он может поехать.<br>Если прямой дороги нет, маршрут проложится через пересадки."],
    add: "Файлы",
  },
  merge: {
    multi: true,
    go: "Склеить в PDF",
    hint: ["Соберите всё в один PDF", "Картинки, текст, документы и другие PDF поедут к станции PDF<br>и склеятся в том порядке, в каком стоят в списке."],
    add: "Файлы",
  },
  split: {
    multi: false, only: ["pdf"],
    go: "Разбить",
    hint: ["Разберите PDF по страницам", "Бросьте один PDF — на выходе будет ZIP<br>с отдельным файлом на каждую страницу."],
    add: "PDF",
  },
  compress: {
    multi: false, only: ["jpg", "png", "webp"],
    go: "Сжать",
    hint: ["Уменьшите вес картинки", "Бросьте JPG, PNG или WEBP — станция обожмёт файл.<br>Формат останется прежним."],
    add: "Картинка",
  },
};

const $ = (id) => document.getElementById(id);
const fileInput = $("file"), filesBox = $("files"), routeBox = $("route"), toolsBox = $("tools");
const go = $("go"), save = $("save"), led = $("led"), statusText = $("statusText");
const hint = $("hint"), veil = $("veil"), addBtn = $("add");

let info = null, mode = "convert", items = [], target = null, resultUrl = null, busy = false;
let quality = 70, maxSide = 0;

/* ---------- утилиты ---------- */

function status(kind, text) {
  led.className = "led " + (kind || "");
  statusText.textContent = text;
}

function fmtSize(n) {
  if (n < 1024) return n + " Б";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " КБ";
  return (n / 1024 / 1024).toFixed(1) + " МБ";
}

function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return n + " " + one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return n + " " + few;
  return n + " " + many;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const fcolor = (fmt) => (Metro.NODES[fmt] ? Metro.colorOf(fmt) : "#14182B");

// Формат по первым байтам: расширению в имени верить нельзя. Сервер перепроверит
async function sniffClient(file) {
  const b = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  const s = (from, text) => [...text].every((ch, i) => b[from + i] === ch.charCodeAt(0));
  if (b[0] === 0x89 && s(1, "PNG")) return "png";
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpg";
  if (s(0, "GIF8")) return "gif";
  if (s(0, "RIFF") && s(8, "WEBP")) return "webp";
  if (s(0, "%PDF")) return "pdf";
  if (s(0, "BM") && file.size > 14) return "bmp";
  return null;
}

async function detect(file) {
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  const byExt = info.extensions[ext] || null;
  const byBytes = await sniffClient(file);
  if (byBytes && byBytes !== byExt) return { fmt: byBytes, note: "внутри " + byBytes.toUpperCase() };
  return { fmt: byExt, note: "" };
}

/* ---------- состояние ---------- */

function problem(it) {
  const m = MODES[mode];
  if (it.file.size > info.max_size) return "больше " + fmtSize(info.max_size);
  if (!it.fmt) return "формат не поддерживается";
  if (m.only && !m.only.includes(it.fmt)) return "нужен " + m.only.join("/").toUpperCase();
  if (mode === "merge" && it.fmt !== "pdf" && !(info.routes[it.fmt] || {}).pdf) return "в PDF не превратить";
  if (mode === "convert" && !Object.keys(info.routes[it.fmt] || {}).length) return "некуда конвертировать";
  return "";
}

const goodItems = () => items.filter((it) => !problem(it));

// Куда можно доехать хотя бы из одного файла; остальные файлы пачки пропускаются
function available() {
  const out = new Set();
  for (const it of goodItems()) Object.keys(info.routes[it.fmt] || {}).forEach((f) => out.add(f));
  return out;
}

function skipped(it) {
  return mode === "convert" && !!target && !!it.fmt && !problem(it) && !(info.routes[it.fmt] || {})[target];
}

function ready() {
  const good = goodItems();
  if (!good.length || good.length !== items.length) return false;
  if (mode === "convert") return !!target && items.some((it) => !skipped(it));
  if (mode === "merge") return good.length >= 2;
  return good.length === 1;
}

function chainHops() {
  const out = {};
  for (const f of available()) {
    let best = 0;
    for (const it of goodItems()) {
      const r = (info.routes[it.fmt] || {})[f];
      if (r && r.length > 2) best = Math.max(best, r.length - 1);
    }
    if (best) out[f] = best;
  }
  return out;
}

function sources() {
  const by = new Map();
  for (const it of goodItems()) {
    const s = by.get(it.fmt) || { fmt: it.fmt, n: 0, name: it.file.name };
    s.n++;
    by.set(it.fmt, s);
  }
  return [...by.values()].map((s) => ({
    fmt: s.fmt,
    label: s.n > 1 ? plural(s.n, "файл", "файла", "файлов") : s.name,
  }));
}

// Маршруты для поездки: по одному на каждый исходный формат
function journeys() {
  const by = new Map();
  for (const it of goodItems()) {
    const dst = mode === "merge" ? "pdf" : target;
    if (it.fmt === dst && mode === "convert") continue;
    const route = it.fmt === dst ? [dst] : (info.routes[it.fmt] || {})[dst];
    if (!route) continue;
    const key = route.join(">");
    const j = by.get(key) || { route, n: 0 };
    j.n++;
    by.set(key, j);
  }
  return [...by.values()].map((j) => ({ route: j.route, label: j.n > 1 ? "×" + j.n : "" }));
}

/* ---------- отрисовка ---------- */

function pushMap() {
  const m = MODES[mode];
  let avail = new Set(), focus = null;
  if (mode === "convert") avail = available();
  else if (mode === "merge") { avail = new Set(["pdf"]); focus = new Set(["pdf", ...goodItems().map((i) => i.fmt)]); }
  else if (mode === "split") { focus = new Set(["pdf"]); }
  else { focus = new Set(m.only); }

  Metro.setView({
    sources: sources(),
    avail,
    chain: mode === "convert" ? chainHops() : {},
    focus,
    target: mode === "convert" ? target : mode === "merge" ? "pdf" : null,
  });
}

function hop(fmt) {
  const s = el("span", "hop", fmt);
  s.style.setProperty("--c", fcolor(fmt));
  return s;
}

function routeLine(route, count, lossy) {
  const line = el("div", "line");
  route.forEach((f, i) => {
    if (i) line.appendChild(el("span", "arrow", "→"));
    line.appendChild(hop(f));
  });
  if (count > 1) line.appendChild(el("span", "arrow", "× " + count));
  if (route.length > 2) {
    const word = route.length - 2 === 1 ? "пересадку" : "пересадки";
    line.appendChild(el("span", "note",
      "через " + word + (lossy ? ", оформление может потеряться" : "")));
  }
  return line;
}

function renderRoute() {
  routeBox.innerHTML = "";
  if (mode !== "convert" || !target) return;
  const seen = new Map();
  for (const it of goodItems()) {
    if (it.fmt === target) continue;
    const route = (info.routes[it.fmt] || {})[target];
    if (!route) continue;
    const key = route.join(">");
    if (!seen.has(key)) seen.set(key, { route, lossy: (info.lossy[it.fmt] || []).includes(target), n: 0 });
    seen.get(key).n++;
  }
  [...seen.values()].slice(0, 3).forEach((v) => routeBox.appendChild(routeLine(v.route, items.length > 1 ? v.n : 1, v.lossy)));
}

function mini(text, label, disabled, fn) {
  const b = el("button", "", text);
  b.type = "button";
  b.disabled = disabled;
  b.setAttribute("aria-label", label);
  b.addEventListener("click", (e) => { e.stopPropagation(); fn(); });
  return b;
}

function renderFiles() {
  filesBox.innerHTML = "";
  items.forEach((it, i) => {
    const li = el("li", skipped(it) ? "skip" : "");
    const tag = el("span", "tag", it.fmt || "?");
    tag.style.setProperty("--c", fcolor(it.fmt));
    const name = el("span", "nm", it.file.name + " · " + fmtSize(it.file.size));
    name.title = it.file.name;
    const bad = problem(it);
    if (bad) name.appendChild(el("small", "", bad));
    else if (skipped(it)) name.appendChild(el("small", "", "нет маршрута, пропустим"));
    else if (it.note) name.appendChild(el("small", "ok", it.note));
    li.append(tag, name);
    if (mode === "merge") {
      li.append(mini("▲", "Выше", i === 0 || busy, () => move(i, -1)),
                mini("▼", "Ниже", i === items.length - 1 || busy, () => move(i, 1)));
    }
    li.append(mini("×", "Убрать", busy, () => removeAt(i)));
    filesBox.appendChild(li);
  });
  hint.classList.toggle("gone", items.length > 0);
  $("addText").textContent = items.length && MODES[mode].multi ? "Ещё" : MODES[mode].add;
}

function renderTools() {
  toolsBox.innerHTML = "";
  toolsBox.hidden = mode === "convert";
  if (mode === "merge") {
    toolsBox.appendChild(el("p", "", "Порядок задаётся списком слева: стрелки ▲▼ меняют очерёдность."));
  } else if (mode === "split") {
    toolsBox.appendChild(el("p", "", "На выходе ZIP: page-001.pdf, page-002.pdf и так далее."));
  } else if (mode === "compress") {
    const q = el("label");
    q.innerHTML = '<span>Качество <span class="val"></span></span>';
    const val = q.querySelector(".val");
    const range = el("input");
    range.type = "range"; range.min = 5; range.max = 100; range.value = quality;
    val.textContent = quality + "%";
    range.addEventListener("input", () => { quality = +range.value; val.textContent = quality + "%"; clearResult(); });
    q.appendChild(range);

    const s = el("label");
    s.appendChild(el("span", "", "Длинная сторона"));
    const sel = el("select");
    [[0, "Без изменений"], [3840, "до 3840 px"], [1920, "до 1920 px"], [1280, "до 1280 px"], [800, "до 800 px"]]
      .forEach(([v, t]) => { const o = el("option", "", t); o.value = v; o.selected = v === maxSide; sel.appendChild(o); });
    sel.addEventListener("change", () => { maxSide = +sel.value; clearResult(); });
    s.appendChild(sel);
    toolsBox.append(q, s, el("div", "compare"));
  }
}

function render() {
  pushMap();
  renderFiles();
  renderRoute();
  go.disabled = busy || !ready();
}

function idleStatus() {
  const bad = items.find((it) => problem(it));
  if (!items.length) return status("", MODES[mode].multi ? "Ждём файлы" : "Ждём файл");
  if (bad) return status("bad", bad.file.name + ": " + problem(bad));
  if (mode === "convert") {
    if (!target) return status("", "Выберите станцию назначения");
    const skip = items.filter(skipped).length;
    if (skip) return status("ready", plural(skip, "файл", "файла", "файлов") + " пропустим: нет маршрута в " + target.toUpperCase());
    const what = items.length > 1 ? plural(items.length, "файл", "файла", "файлов") : items[0].file.name;
    return status("ready", what + " → " + target.toUpperCase() + ". Можно в путь");
  }
  if (mode === "merge" && items.length < 2) return status("", "Добавьте ещё хотя бы один файл");
  status("ready", "Всё готово, можно запускать");
}

/* ---------- действия ---------- */

function clearResult() {
  if (resultUrl) URL.revokeObjectURL(resultUrl);
  resultUrl = null;
  save.hidden = true;
  Metro.reset();
  const cmp = toolsBox.querySelector(".compare");
  if (cmp) cmp.textContent = "";
}

function pick(f) {
  if (busy || mode !== "convert") return;
  if (!available().has(f)) return;
  target = target === f ? null : f;
  clearResult();
  render();
  idleStatus();
}

function ghostFor(fmt) {
  if (!fmt || busy || mode !== "convert" || !available().has(fmt)) return Metro.ghost(null);
  const it = goodItems().find((x) => (info.routes[x.fmt] || {})[fmt]);
  Metro.ghost(it ? info.routes[it.fmt][fmt] : null);
}

async function addFiles(list) {
  const incoming = [...list];
  if (!incoming.length || !info || busy) return;
  clearResult();
  const m = MODES[mode];
  const base = m.multi ? items : [];
  const take = incoming.slice(0, m.multi ? Math.max(info.max_files - base.length, 0) : 1);
  const added = [];
  for (const file of take) added.push({ file, ...(await detect(file)) });
  items = base.concat(added);
  render();
  if (incoming.length > take.length && m.multi) {
    return status("bad", "Принято " + take.length + ", лимит — " + info.max_files + " файлов");
  }
  idleStatus();
}

function removeAt(i) {
  if (busy) return;
  clearResult();
  items.splice(i, 1);
  render();
  idleStatus();
}

function move(i, d) {
  if (busy) return;
  clearResult();
  [items[i], items[i + d]] = [items[i + d], items[i]];
  render();
}

function setMode(next) {
  if (busy || next === mode) return;
  mode = next;
  items = [];
  target = null;
  clearResult();
  Metro.ghost(null);
  document.querySelectorAll(".mode").forEach((b) => {
    const on = b.dataset.mode === mode;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", on);
  });
  $("hintTitle").textContent = MODES[mode].hint[0];
  $("hintText").innerHTML = MODES[mode].hint[1];
  go.textContent = MODES[mode].go;
  fileInput.multiple = MODES[mode].multi;
  renderTools();
  render();
  idleStatus();
}

function request() {
  const body = new FormData();
  const files = items.map((it) => it.file);
  const stem = (n) => n.replace(/\.[^.]+$/, "") || "file";

  if (mode === "convert" && files.length === 1) {
    body.append("file", files[0]);
    body.append("target", target);
    return { url: "/api/convert", body, name: stem(files[0].name) + "." + target, work: "Файл в пути…" };
  }
  if (mode === "convert") {
    files.forEach((f) => body.append("files", f));
    body.append("target", target);
    return { url: "/api/batch", body, name: "converted_" + target + ".zip", work: "Пачка в пути…" };
  }
  if (mode === "merge") {
    files.forEach((f) => body.append("files", f));
    return { url: "/api/merge", body, name: "merged.pdf", work: "Склеиваем…" };
  }
  if (mode === "split") {
    body.append("file", files[0]);
    return { url: "/api/split", body, name: stem(files[0].name) + "_pages.zip", work: "Разбираем на страницы…" };
  }
  body.append("file", files[0]);
  body.append("quality", quality);
  body.append("max_side", maxSide);
  return { url: "/api/compress", body, name: stem(files[0].name) + "_small." + items[0].fmt, work: "Обжимаем…" };
}

async function send(req) {
  const res = await fetch(req.url, { method: "POST", body: req.body });
  if (!res.ok) {
    let msg = "Сервер ответил ошибкой " + res.status;
    try { msg = (await res.json()).error || msg; } catch (_) {}
    throw new Error(msg);
  }
  return { res, blob: await res.blob() };
}

function doneMessage(res, blob) {
  const h = (k) => res.headers.get(k);
  if (mode === "compress") {
    const before = +h("X-Before"), after = +h("X-After");
    const cut = before ? Math.round((1 - after / before) * 100) : 0;
    const cmp = toolsBox.querySelector(".compare");
    if (cmp) {
      cmp.innerHTML = "";
      cmp.append("Было " + fmtSize(before) + " → стало ", el("strong", "", fmtSize(after)),
        cut > 0 ? " (−" + cut + "%)" : " (не уменьшилось)");
    }
    return cut > 0 ? "Готово · −" + cut + "% (" + fmtSize(after) + ")" : "Готово, но размер не уменьшился";
  }
  if (mode === "merge") return "Готово · " + plural(+h("X-Pages"), "страница", "страницы", "страниц") + " · " + fmtSize(blob.size);
  if (mode === "split") return "Готово · " + plural(+h("X-Pages"), "страница", "страницы", "страниц") + " в архиве";
  if (items.length > 1) {
    const failed = +h("X-Failed");
    const done = plural(+h("X-Done"), "файл", "файла", "файлов");
    return failed ? "Готово: " + done + ", ошибки в ОШИБКИ.txt (" + failed + ")" : "Готово · " + done + " в ZIP";
  }
  const note = h("X-Note");
  return "Готово · " + fmtSize(blob.size) + (note ? " · " + decodeURIComponent(note) : "");
}

async function run() {
  if (busy || !ready()) return;
  busy = true;
  go.disabled = true;
  clearResult();
  Metro.ghost(null);
  Metro.lock(true);
  renderFiles();
  const req = request();
  status("work", req.work);

  let outcome = null, error = null;
  const job = send(req).then((r) => { outcome = r; }, (e) => { error = e; throw e; });

  let anim;
  if (mode === "split") anim = Metro.fanOut("pdf", job);
  else if (mode === "compress") anim = Metro.squeeze(items[0].fmt, job);
  else anim = Metro.travel(journeys(), job);

  try { await anim; } catch (_) {}
  try { await job; } catch (_) {}

  if (error) {
    status("bad", error.message);
  } else if (outcome) {
    resultUrl = URL.createObjectURL(outcome.blob);
    save.href = resultUrl;
    save.download = req.name;
    save.hidden = false;
    status(+outcome.res.headers.get("X-Failed") ? "ready" : "ok", doneMessage(outcome.res, outcome.blob));
  }

  busy = false;
  Metro.lock(false);
  renderFiles();
  go.disabled = !ready();
}

/* ---------- события ---------- */

addBtn.addEventListener("click", () => { if (!busy) fileInput.click(); });
fileInput.addEventListener("change", () => {
  addFiles(fileInput.files);
  fileInput.value = "";
});
document.querySelectorAll(".mode").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
go.addEventListener("click", run);

let dragDepth = 0;
window.addEventListener("dragenter", (e) => {
  if (!e.dataTransfer || ![...e.dataTransfer.types].includes("Files")) return;
  e.preventDefault();
  dragDepth++;
  veil.classList.add("on");
});
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) veil.classList.remove("on");
});
window.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  veil.classList.remove("on");
  if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.target.closest("button, a, .st, select, input")) run();
  if (e.key === "Escape" && target && !busy) { target = null; clearResult(); render(); idleStatus(); }
});

fetch("/api/formats")
  .then((r) => r.json())
  .then((data) => {
    info = data;
    Metro.init($("mapWrap"), info.edges, { onPick: pick, onHover: ghostFor });
    const routes = Object.values(info.routes).reduce((s, d) => s + Object.keys(d).length, 0);
    $("stats").textContent = Object.keys(Metro.NODES).length + " форматов · " + routes + " маршрутов" + (info.ocr ? " · OCR" : "");
    render();
  })
  .catch(() => status("bad", "Не удалось связаться с сервером"));
