// Карта форматов: станции, линии, "поезда" с файлами и анимации поездки.
// Ничего не знает про сервер — приложение (app.js) только отдаёт ей состояние.

const Metro = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const W = 1000, VB_Y = 30, VB_H = 530;
  const RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  const GROUP = {
    doc: { color: "#FF5A36", name: "документы" },
    data: { color: "#0AA58C", name: "данные" },
    img: { color: "#6B4DFF", name: "картинки" },
  };
  const INK = "#14182B", GOLD = "#FFC21A", RED = "#E5213C";

  // Координаты подобраны вручную, чтобы линии пересекались как можно реже
  const NODES = {
    txt:  { x: 300, y: 300, g: "doc" },
    docx: { x: 110, y: 160, g: "doc" },
    html: { x: 300, y: 110, g: "doc" },
    pdf:  { x: 545, y: 300, g: "doc" },
    json: { x: 100, y: 340, g: "data" },
    csv:  { x: 420, y: 500, g: "data" },
    xlsx: { x: 650, y: 500, g: "data" },
    png:  { x: 810, y: 170, g: "img" },
    jpg:  { x: 922, y: 262, g: "img" },
    webp: { x: 880, y: 400, g: "img" },
    bmp:  { x: 740, y: 400, g: "img" },
    gif:  { x: 698, y: 262, g: "img" },
  };
  const RING = ["png", "jpg", "webp", "bmp", "gif"];
  const colorOf = (fmt) => GROUP[NODES[fmt].g].color;

  let svg, layers = {}, stations = {}, handlers = {}, chips = new Map();
  let locked = false, view = { avail: new Set(), chain: {}, focus: null, target: null, sources: [] };

  /* ---------- утилиты ---------- */

  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const dur = (ms) => (RM ? Math.min(ms, 120) : ms);

  function tween(ms, fn) {
    ms = dur(ms);
    return new Promise((resolve) => {
      const t0 = performance.now();
      (function frame(now) {
        const p = Math.min(1, (now - t0) / ms);
        fn(p);
        if (p < 1) requestAnimationFrame(frame); else resolve();
      })(t0);
    });
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, dur(ms)));

  function mk(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  const at = (e, x, y, s = 1) => e.setAttribute("transform", `translate(${x},${y}) scale(${s})`);

  /* ---------- построение карты ---------- */

  function init(container, edges, h) {
    handlers = h;
    svg = mk("svg", { viewBox: `0 ${VB_Y} ${W} ${VB_H}`, class: "metro", role: "group", "aria-label": "Карта форматов" });
    container.appendChild(svg);
    for (const name of ["edges", "flow", "route", "ghost", "stations", "chips", "tokens", "fx"]) {
      layers[name] = mk("g", { class: "L-" + name }, svg);
    }
    buildEdges(edges);
    buildStations();
  }

  function buildEdges(edges) {
    const dir = new Set(edges.map(([a, b]) => a + ">" + b));
    const done = new Set();
    // кольцо картинок: между ними можно ехать напрямую, рисуем только контур
    const ring = RING.map((f) => NODES[f]);
    mk("path", {
      d: "M" + ring.map((p) => p.x + "," + p.y).join("L") + "Z",
      class: "edge ring", stroke: GROUP.img.color,
    }, layers.edges);

    for (const [a, b] of edges) {
      const key = [a, b].sort().join("-");
      if (done.has(key)) continue;
      done.add(key);
      if (NODES[a].g === "img" && NODES[b].g === "img") continue;

      const two = dir.has(a + ">" + b) && dir.has(b + ">" + a);
      const [from, to] = dir.has(a + ">" + b) ? [a, b] : [b, a];
      const p = NODES[from], q = NODES[to];
      const same = NODES[a].g === NODES[b].g;
      const color = same ? colorOf(a) : INK;
      const d = `M${p.x},${p.y}L${q.x},${q.y}`;
      mk("path", { d, class: "edge" + (same ? "" : " bridge"), stroke: color }, layers.edges);
      const flow = mk("path", { d, class: "flow" + (two ? " two" : ""), }, layers.flow);
      flow.style.animationDelay = (-Math.random() * 6).toFixed(2) + "s";
      if (!two) {
        const mx = (p.x + q.x) / 2, my = (p.y + q.y) / 2;
        const ang = Math.atan2(q.y - p.y, q.x - p.x) * 180 / Math.PI;
        mk("path", {
          d: "M-6,-6L6,0L-6,6Z", class: "arrow", fill: color,
          transform: `translate(${mx},${my}) rotate(${ang})`,
        }, layers.flow);
      }
    }
  }

  function buildStations() {
    for (const fmt in NODES) {
      const n = NODES[fmt], color = colorOf(fmt);
      const g = mk("g", {
        class: "st", tabindex: 0, role: "button", "data-fmt": fmt,
        "aria-label": "Формат " + fmt.toUpperCase(), transform: `translate(${n.x},${n.y})`,
      }, layers.stations);
      mk("circle", { class: "halo", r: 27, stroke: color }, g);
      mk("circle", { class: "hit", r: 34 }, g);
      mk("circle", { class: "ring", r: 15, stroke: color }, g);
      mk("circle", { class: "core", r: 7, fill: color }, g);
      const lbl = mk("text", { class: "lbl", y: n.y > 440 ? -30 : 38 }, g);
      lbl.textContent = fmt;
      const badge = mk("g", { class: "badge", transform: "translate(21,-21)" }, g);
      mk("circle", { r: 10, fill: INK }, badge);
      mk("text", { class: "badge-n", y: 4 }, badge);

      g.addEventListener("click", () => { if (!locked) handlers.onPick && handlers.onPick(fmt); });
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!locked) handlers.onPick && handlers.onPick(fmt); }
      });
      const enter = () => { if (!locked) handlers.onHover && handlers.onHover(fmt); };
      const leave = () => handlers.onHover && handlers.onHover(null);
      g.addEventListener("mouseenter", enter);
      g.addEventListener("mouseleave", leave);
      g.addEventListener("focus", enter);
      g.addEventListener("blur", leave);
      stations[fmt] = g;
    }
  }

  /* ---------- состояние ---------- */

  // opts: sources [{fmt, label}], avail Set, chain {fmt: hops}, focus Set|null, target
  function setView(opts) {
    view = Object.assign({ avail: new Set(), chain: {}, focus: null, target: null, sources: [] }, opts);
    svg.classList.toggle("focused", !!view.focus);
    const srcSet = new Set(view.sources.map((s) => s.fmt));
    for (const fmt in stations) {
      const st = stations[fmt];
      const inFocus = !view.focus || view.focus.has(fmt);
      const live = view.avail.has(fmt) && inFocus;
      const hops = view.chain[fmt];
      const dim = (view.sources.length || view.focus) && !srcSet.has(fmt) && !live;
      st.classList.toggle("src", srcSet.has(fmt));
      st.classList.toggle("avail", live && !srcSet.has(fmt));
      st.classList.toggle("chain", live && !!hops);
      st.classList.toggle("target", view.target === fmt);
      st.classList.toggle("off", !!dim);
      st.classList.remove("done");
      st.setAttribute("aria-disabled", String(!live));
      st.querySelector(".badge").style.display = live && hops ? "" : "none";
      if (hops) st.querySelector(".badge-n").textContent = hops;
    }
    syncChips();
  }

  function syncChips() {
    const wanted = new Map(view.sources.map((s) => [s.fmt, s]));
    for (const [fmt, c] of chips) {
      if (!wanted.has(fmt)) { c.remove(); chips.delete(fmt); }
    }
    for (const [fmt, s] of wanted) {
      let c = chips.get(fmt);
      const text = s.label.length > 16 ? s.label.slice(0, 15) + "…" : s.label;
      if (!c) {
        c = mk("g", { class: "chip" }, layers.chips);
        mk("rect", { rx: 11, height: 22, stroke: colorOf(fmt) }, c);
        mk("text", { y: 15, "text-anchor": "middle" }, c);
        chips.set(fmt, c);
        const n = NODES[fmt];
        c._pos = [n.x, n.y - 46];
        c.style.opacity = 0;
        tween(650, (p) => {
          const e = easeOut(p);
          at(c, W / 2 + (c._pos[0] - W / 2) * e, VB_Y + VB_H + 30 + (c._pos[1] - VB_Y - VB_H - 30) * e);
          c.style.opacity = Math.min(1, p * 3);
        });
      }
      const t = c.querySelector("text");
      t.textContent = text;
      const w = Math.max(44, text.length * 7.2 + 18);
      const r = c.querySelector("rect");
      r.setAttribute("width", w);
      r.setAttribute("x", -w / 2);
      r.setAttribute("y", 0);
    }
  }

  function lock(on) {
    locked = on;
    svg.classList.toggle("locked", on);
  }

  /* ---------- призрак маршрута при наведении ---------- */

  function ghost(route) {
    layers.ghost.innerHTML = "";
    if (!route || route.length < 2) return;
    const d = pathOf(route);
    mk("path", { d, class: "ghost-case" }, layers.ghost);
    mk("path", { d, class: "ghost" }, layers.ghost);
  }

  function pathOf(route) {
    return "M" + route.map((f) => NODES[f].x + "," + NODES[f].y).join("L");
  }

  function clearRoutes() {
    layers.route.innerHTML = "";
    layers.tokens.innerHTML = "";
    layers.fx.innerHTML = "";
  }

  /* ---------- эффекты ---------- */

  function ripple(fmt, color, from = 18, to = 70, ms = 700) {
    const n = NODES[fmt];
    const c = mk("circle", { cx: n.x, cy: n.y, r: from, class: "ripple", stroke: color }, layers.fx);
    return tween(ms, (p) => {
      c.setAttribute("r", from + (to - from) * easeOut(p));
      c.style.opacity = 1 - p;
    }).then(() => c.remove());
  }

  function burst(x, y, color, count = 34) {
    if (RM) return Promise.resolve();
    const palette = [color, color, INK, GOLD, "#fff"];
    const parts = [];
    for (let i = 0; i < count; i++) {
      const a = Math.random() * Math.PI * 2, v = 90 + Math.random() * 210;
      const sq = Math.random() < 0.45;
      const e = sq
        ? mk("rect", { x: -4, y: -2.5, width: 8, height: 5, rx: 1 }, layers.fx)
        : mk("circle", { r: 2.5 + Math.random() * 3 }, layers.fx);
      e.setAttribute("fill", palette[i % palette.length]);
      parts.push({ e, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 60, rot: Math.random() * 360, vr: (Math.random() - 0.5) * 900 });
    }
    return tween(1100, (p) => {
      const t = p * 1.1;
      for (const q of parts) {
        const px = x + q.vx * t, py = y + q.vy * t + 380 * t * t;
        q.e.setAttribute("transform", `translate(${px},${py}) rotate(${q.rot + q.vr * t})`);
        q.e.style.opacity = 1 - Math.pow(p, 2.2);
      }
    }).then(() => parts.forEach((q) => q.e.remove()));
  }

  function makeToken(fmt, color, label) {
    const g = mk("g", { class: "token" }, layers.tokens);
    mk("rect", { x: -38, y: -16, width: 76, height: 32, rx: 16, stroke: color, class: "token-body" }, g);
    const t = mk("text", { y: 5, "text-anchor": "middle", class: "token-fmt" }, g);
    t.textContent = fmt;
    let badge = null;
    if (label) {
      badge = mk("g", { transform: "translate(34,-16)" }, g);
      mk("circle", { r: 11, fill: INK }, badge);
      const bt = mk("text", { y: 4, class: "badge-n", "text-anchor": "middle" }, badge);
      bt.textContent = label;
    }
    return { g, t };
  }

  function orbit(token) {
    const dots = [0, 1, 2].map(() => mk("circle", { r: 3.6, fill: INK }, token.g));
    let alive = true;
    (function spin(now) {
      if (!alive) return;
      const a = now / 260;
      dots.forEach((d, i) => {
        const k = a + (i * Math.PI * 2) / 3;
        d.setAttribute("cx", Math.cos(k) * 46);
        d.setAttribute("cy", Math.sin(k) * 24);
      });
      requestAnimationFrame(spin);
    })(performance.now());
    return () => { alive = false; dots.forEach((d) => d.remove()); };
  }

  async function flip(token, text) {
    await tween(130, (p) => token.t.setAttribute("transform", `scale(1,${1 - p})`));
    token.t.textContent = text;
    await tween(130, (p) => token.t.setAttribute("transform", `scale(1,${p})`));
  }

  /* ---------- поездка ---------- */

  // journeys: [{route:[fmt...], label:"×3"|""}], done: Promise (resolve — успех, reject — ошибка)
  async function travel(journeys, done) {
    const settled = done.then(() => null, (e) => e || new Error("fail"));
    const results = await Promise.all(journeys.map((j) => ride(j, settled)));
    const ok = results.every(Boolean);
    if (ok) {
      const dst = journeys[0].route[journeys[0].route.length - 1];
      await arrive(dst, journeys);
    }
    return ok;
  }

  async function ride(j, settled) {
    const route = j.route;
    const color = colorOf(route[route.length - 1]);
    const token = makeToken(route[0], colorOf(route[0]), j.label);

    if (route.length < 2) {
      const n = NODES[route[0]];
      at(token.g, n.x, n.y);
      const stop = orbit(token);
      const err = await settled;
      stop();
      if (err) { await fail(token); return false; }
      token.g.remove();
      return true;
    }

    const d = pathOf(route);
    const glowCase = mk("path", { d, class: "glow-case" }, layers.route);
    const glow = mk("path", { d, class: "glow", stroke: color }, layers.route);
    const total = glow.getTotalLength();
    for (const p of [glow, glowCase]) {
      p.style.strokeDasharray = total;
      p.style.strokeDashoffset = total;
    }

    const cum = [0];
    for (let i = 1; i < route.length; i++) {
      const a = NODES[route[i - 1]], b = NODES[route[i]];
      cum.push(cum[i - 1] + Math.hypot(b.x - a.x, b.y - a.y));
    }
    const place = (len) => {
      const pt = glow.getPointAtLength(len);
      at(token.g, pt.x, pt.y);
      glow.style.strokeDashoffset = total - len;
      glowCase.style.strokeDashoffset = total - len;
    };
    place(0);
    ripple(route[0], colorOf(route[0]), 14, 50, 500);

    for (let i = 0; i < route.length - 1; i++) {
      const last = i === route.length - 2;
      const seg = cum[i + 1] - cum[i];
      const reach = last ? 0.8 : 1;
      await tween(950, (p) => place(cum[i] + seg * reach * ease(p)));
      if (last) {
        const stop = orbit(token);
        const err = await settled;
        stop();
        if (err) { await fail(token, glow); return false; }
        await tween(380, (p) => place(cum[i] + seg * (reach + (1 - reach) * easeOut(p))));
      } else {
        const next = route[i + 1];
        ripple(next, colorOf(next));
        await flip(token, next);
        await wait(120);
      }
    }
    return true;
  }

  async function fail(token, glow) {
    const body = token.g.querySelector(".token-body");
    body.setAttribute("stroke", RED);
    const m = token.g.getAttribute("transform");
    const [x, y] = m.match(/-?[\d.]+/g).map(Number);
    await tween(420, (p) => at(token.g, x + Math.sin(p * 30) * 8 * (1 - p), y));
    if (glow) { glow.setAttribute("stroke", RED); }
    token.g.classList.add("failed");
    await wait(900);
    token.g.remove();
    if (glow) glow.parentNode && (layers.route.innerHTML = "");
  }

  async function arrive(fmt, journeys) {
    const n = NODES[fmt], color = colorOf(fmt);
    layers.tokens.querySelectorAll(".token").forEach((t) => {
      tween(260, (p) => { t.style.opacity = 1 - p; });
    });
    ripple(fmt, color, 16, 110, 900);
    ripple(fmt, GOLD, 16, 70, 700);
    stations[fmt].classList.add("done");
    await burst(n.x, n.y, color);
    layers.tokens.innerHTML = "";
  }

  // разбиение PDF: страницы веером разлетаются из станции
  async function fanOut(fmt, done, pages = 6) {
    const settled = done.then(() => null, (e) => e || new Error("fail"));
    const n = NODES[fmt], color = colorOf(fmt);
    const token = makeToken(fmt, color);
    at(token.g, n.x, n.y);
    const stop = orbit(token);
    await ripple(fmt, color, 18, 80, 600);
    const err = await settled;
    stop();
    if (err) { await fail(token); return false; }
    token.g.remove();
    const sheets = [];
    for (let i = 0; i < 7; i++) {
      const s = mk("g", {}, layers.fx);
      mk("rect", { x: -11, y: -15, width: 22, height: 30, rx: 3, fill: "#fff", stroke: color, "stroke-width": 2.5 }, s);
      mk("path", { d: "M-6,-6H6M-6,0H6M-6,6H2", stroke: color, "stroke-width": 2, fill: "none" }, s);
      sheets.push(s);
    }
    stations[fmt].classList.add("done");
    await tween(1100, (p) => {
      const e = easeOut(p);
      sheets.forEach((s, i) => {
        const a = (-Math.PI / 2) + (i - 3) * 0.42;
        const r = 30 + 150 * e;
        at(s, n.x + Math.cos(a) * r, n.y + Math.sin(a) * r, 0.6 + 0.4 * e);
        s.setAttribute("transform", s.getAttribute("transform") + ` rotate(${(i - 3) * 14 * e})`);
        s.style.opacity = p < 0.7 ? 1 : 1 - (p - 0.7) / 0.3;
      });
    });
    sheets.forEach((s) => s.remove());
    await burst(n.x, n.y, color, 20);
    return true;
  }

  // сжатие: станция "обжимает" файл
  async function squeeze(fmt, done) {
    const settled = done.then(() => null, (e) => e || new Error("fail"));
    const n = NODES[fmt], color = colorOf(fmt);
    const token = makeToken(fmt, color);
    at(token.g, n.x, n.y);
    let running = true;
    const pump = (async () => {
      while (running) {
        const ring = mk("circle", { cx: n.x, cy: n.y, class: "ripple", stroke: color }, layers.fx);
        await tween(650, (p) => {
          ring.setAttribute("r", 90 - 70 * ease(p));
          ring.style.opacity = p < 0.8 ? 0.9 : (1 - p) * 4.5;
          at(token.g, n.x, n.y, 1 - 0.28 * Math.sin(p * Math.PI));
        });
        ring.remove();
      }
    })();
    const err = await settled;
    running = false;
    await pump;
    if (err) { await fail(token); return false; }
    await tween(380, (p) => at(token.g, n.x, n.y, 0.72 + 0.28 * easeOut(p)));
    token.g.remove();
    stations[fmt].classList.add("done");
    ripple(fmt, GOLD, 16, 80, 700);
    await burst(n.x, n.y, color, 24);
    return true;
  }

  function reset() {
    clearRoutes();
    for (const fmt in stations) stations[fmt].classList.remove("done");
  }

  return { init, setView, lock, ghost, travel, fanOut, squeeze, reset, NODES, colorOf, GROUP };
})();
