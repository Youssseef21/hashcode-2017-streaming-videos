const $ = (id) => document.getElementById(id);

let datasets = [];
let currentId = null;
let stats = null;
let solve = null;
let playTimer = null;
let frame = 0;

function fmt(n) {
  return Number(n).toLocaleString("fr-FR");
}

function pct(x) {
  return (100 * x).toFixed(1) + " %";
}

async function loadDatasets() {
  const res = await fetch("/api/datasets");
  const data = await res.json();
  datasets = data.datasets;
  const box = $("dataset-list");
  box.innerHTML = "";
  datasets.forEach((ds) => {
    const btn = document.createElement("button");
    btn.className = "ds";
    btn.type = "button";
    btn.innerHTML = `<strong>${ds.fichier}</strong><small>${ds.famille} · V=${ds.V} E=${ds.E} R=${fmt(ds.R)} C=${ds.C} X=${ds.X}${ds.lourd ? " · 1er calcul lent" : ""}</small>`;
    btn.onclick = () => selectDataset(ds.id);
    box.appendChild(btn);
  });
}

function setActive(id) {
  document.querySelectorAll(".ds").forEach((el, i) => {
    el.classList.toggle("active", datasets[i].id === id);
  });
}

async function selectDataset(id) {
  currentId = id;
  setActive(id);
  $("empty").classList.add("hidden");
  $("work").classList.remove("hidden");
  $("btn-solve").disabled = true;
  $("btn-solve").textContent = "Chargement…";
  stopPlay();
  solve = null;
  const ds = datasets.find((d) => d.id === id);
  $("ds-name").textContent = ds.fichier;
  $("ds-meta").textContent = ds.chemin + " · " + ds.famille;
  stats = await (await fetch("/api/stats/" + encodeURIComponent(id))).json();
  renderStats();
  $("btn-solve").disabled = false;
  $("btn-solve").textContent = ds.lourd ? "Lancer le greedy (peut etre long)" : "Lancer le greedy";
  $("step-label").textContent = "pas encore resolu";
  $("score-cards").innerHTML = "";
  $("event").textContent = "";
  $("caches").innerHTML = "";
  ["chart-score", "chart-fillbars"].forEach((id) => {
    const cv = $(id);
    if (cv) clearCanvas(cv);
  });
}

function card(label, value) {
  return `<div class="card"><b>${value}</b><span>${label}</span></div>`;
}

function renderStats() {
  const s = stats;
  const v = s.videos;
  const c = s.connectivite;
  $("header-cards").innerHTML = [
    card("Videos", fmt(s.V)),
    card("Endpoints", fmt(s.E)),
    card("Demandes", fmt(s.R)),
    card("Caches", fmt(s.C)),
    card("Capacite", fmt(s.X) + " Mo"),
    card("Gini", v.gini_popularite.toFixed(2)),
  ].join("");

  $("insight").textContent =
    `Trafic : les 10 % de videos les plus vues portent ${pct(v.part_top_10pct)} des requetes. ` +
    `Reseau : densite ${pct(c.densite)} (un endpoint voit en moyenne ${c.degre_endpoint.moyenne.toFixed(1)} caches).` +
    (c.endpoints_isoles ? ` ${c.endpoints_isoles} endpoint(s) sans cache.` : "");

  drawZipf($("chart-zipf"), s.graphiques.zipf);
  drawHeat($("chart-heat"), s.heatmap);
}

function clearCanvas(cv) {
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, cv.width, cv.height);
}

function sizeCanvas(cv) {
  const w = cv.clientWidth || 400;
  const h = Number(cv.getAttribute("height")) || 140;
  cv.width = Math.floor(w * devicePixelRatio);
  cv.height = Math.floor(h * devicePixelRatio);
  const ctx = cv.getContext("2d");
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  return { ctx, w, h };
}

function drawHist(cv, values, color) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  if (!values || !values.length) return;
  const bins = 24;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const counts = new Array(bins).fill(0);
  values.forEach((x) => {
    const i = Math.min(bins - 1, Math.floor(((x - min) / span) * bins));
    counts[i] += 1;
  });
  const m = Math.max(...counts, 1);
  const bw = w / bins;
  ctx.fillStyle = color;
  counts.forEach((c, i) => {
    const bh = (c / m) * (h - 8);
    ctx.fillRect(i * bw + 1, h - bh, bw - 2, bh);
  });
}

function drawZipf(cv, ranked) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  if (!ranked || !ranked.length) return;
  ctx.strokeStyle = "#c4a574";
  ctx.beginPath();
  ranked.forEach((y, i) => {
    const x = (i / Math.max(ranked.length - 1, 1)) * (w - 8) + 4;
    const py = h - 6 - (Math.log10(y + 1) / Math.log10(ranked[0] + 1)) * (h - 12);
    if (i === 0) ctx.moveTo(x, py);
    else ctx.lineTo(x, py);
  });
  ctx.stroke();
}

function drawLorenz(cv, pts) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#5a6270";
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(8, h - 8);
  ctx.lineTo(w - 8, 8);
  ctx.stroke();
  ctx.setLineDash([]);
  if (!pts || !pts.length) return;
  ctx.strokeStyle = "#c44e52";
  ctx.beginPath();
  pts.forEach((p, i) => {
    const x = 8 + p.x * (w - 16);
    const y = h - 8 - p.y * (h - 16);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawScatter(cv, pts) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  if (!pts || !pts.length) return;
  const maxS = Math.max(...pts.map((p) => p.size), 1);
  const maxV = Math.max(...pts.map((p) => p.vol), 1);
  ctx.fillStyle = "#c4a574";
  pts.forEach((p) => {
    const x = 8 + (p.size / maxS) * (w - 16);
    const y = h - 8 - (p.vol / maxV) * (h - 16);
    ctx.beginPath();
    ctx.arc(x, y, 2.4, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawBars(cv, values, color) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  if (!values || !values.length) return;
  const m = Math.max(...values, 1);
  const bw = w / values.length;
  ctx.fillStyle = color;
  values.forEach((v, i) => {
    const bh = (v / m) * (h - 6);
    ctx.fillRect(i * bw, h - bh, Math.max(1, bw - 0.5), bh);
  });
}

function drawLine(cv, values, color, key) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  if (!values || !values.length) return;
  const ys = values.map((p) => (key ? p[key] : p));
  const maxS = Math.max(...ys, 1);
  ctx.strokeStyle = color;
  ctx.beginPath();
  ys.forEach((y, i) => {
    const x = (i / Math.max(ys.length - 1, 1)) * (w - 10) + 5;
    const py = h - 8 - (y / maxS) * (h - 16);
    if (i === 0) ctx.moveTo(x, py);
    else ctx.lineTo(x, py);
  });
  ctx.stroke();
  if (frame != null && solve && values === solve.courbe && values.length) {
    const i = Math.min(frame, values.length - 1);
    const x = (i / Math.max(values.length - 1, 1)) * (w - 10) + 5;
    const py = h - 8 - (ys[i] / maxS) * (h - 16);
    ctx.fillStyle = "#ece7dc";
    ctx.beginPath();
    ctx.arc(x, py, 3.5, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawHeat(cv, matrix) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  if (!matrix || !matrix.length) {
    ctx.fillStyle = "#9aa3b5";
    ctx.fillText("Trop grand pour afficher la matrice, ou aucun lien.", 12, 24);
    return;
  }
  const rows = matrix.length;
  const cols = matrix[0].length;
  let max = 1;
  matrix.forEach((row) => row.forEach((v) => { if (v > max) max = v; }));
  const cw = w / cols;
  const rh = h / rows;
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const v = matrix[r][c];
      if (!v) {
        ctx.fillStyle = "#10131a";
      } else {
        const t = v / max;
        ctx.fillStyle = `rgb(${40 + t * 160}, ${90 - t * 40}, ${80 + (1 - t) * 80})`;
      }
      ctx.fillRect(c * cw, r * rh, Math.ceil(cw), Math.ceil(rh));
    }
  }
}

function buildCaches() {
  const C = solve.C;
  const box = $("caches");
  box.innerHTML = "";
  for (let i = 0; i < C; i += 1) {
    const row = document.createElement("div");
    row.className = "cache-row";
    row.id = "crow-" + i;
    row.innerHTML = `<span>cache ${i}</span><div class="track"><div class="fill" id="fill-${i}"></div></div><span id="lab-${i}">0 / ${solve.X} Mo</span>`;
    box.appendChild(row);
  }
}

function applyFrame(n) {
  if (!solve) return;
  const steps = solve.steps;
  const last = steps[n];
  if (!last) return;
  document.querySelectorAll(".cache-row").forEach((el) => el.classList.remove("hot"));
  const hot = document.getElementById("crow-" + last.c);
  if (hot) hot.classList.add("hot");
  const snapshot = last.used || [];
  snapshot.forEach((u, c) => {
    const pctFill = solve.X ? (100 * u) / solve.X : 0;
    const el = document.getElementById("fill-" + c);
    if (el) el.style.width = Math.min(100, pctFill) + "%";
    const lab = document.getElementById("lab-" + c);
    if (lab) lab.textContent = `${u} / ${solve.X} Mo`;
  });
  $("event").textContent =
    `OUI #${last.n} : video ${last.v} dans cache ${last.c} (${last.size} Mo) · score ${fmt(last.score)}`;
  $("step-label").textContent = `${last.n} / ${solve.placements} placements`;
  if ($("chart-score")) drawLine($("chart-score"), solve.courbe, "#c4a574", "score");
}

function stopPlay() {
  if (playTimer) {
    clearInterval(playTimer);
    playTimer = null;
  }
  $("btn-play").textContent = "Lecture";
}

function play() {
  if (!solve || !solve.steps.length) return;
  if (playTimer) {
    stopPlay();
    return;
  }
  $("btn-play").textContent = "Pause";
  const speed = Number($("speed").value);
  playTimer = setInterval(() => {
    if (frame >= solve.steps.length - 1) {
      stopPlay();
      return;
    }
    frame += 1;
    $("scrub").value = String(frame);
    applyFrame(frame);
  }, Math.max(20, 420 / speed));
}

function renderSolveCharts() {
  drawLine($("chart-score"), solve.courbe, "#c4a574", "score");
  drawBars($("chart-fillbars"), solve.remplissage_Mo, "#3d6b8c");
}

async function runSolve() {
  if (!currentId) return;
  $("btn-solve").disabled = true;
  $("btn-solve").textContent = "Calcul en cours…";
  $("event").textContent = "Le greedy range les couples video+cache par densite, puis pose les OUI un par un.";
  solve = await (await fetch("/api/solve/" + encodeURIComponent(currentId))).json();
  $("btn-solve").disabled = false;
  $("btn-solve").textContent = "Relancer (cache)";
  $("btn-play").disabled = false;
  $("btn-reset").disabled = false;
  $("scrub").disabled = false;
  $("scrub").max = String(Math.max(0, solve.steps.length - 1));
  $("score-cards").innerHTML = [
    card("Score", fmt(solve.score)),
    card("% du mieux possible*", pct(solve.part_plafond)),
    card("Caches remplis", `${solve.caches_utilises} / ${solve.C}`),
    card("Occupation", solve.moyenne_occupation_pct + " %"),
    card("Temps", solve.temps_s + " s"),
  ].join("");
  $("score-legend").textContent =
    "* Mieux possible = chaque endpoint utilise son cache le plus proche, sans limite de Mo. Score = ms gagnees × 1000 / nombre de requetes.";
  renderSolveCharts();
  buildCaches();
  frame = 0;
  $("scrub").value = "0";
  applyFrame(0);
  play();
}

$("btn-solve").onclick = runSolve;
$("btn-play").onclick = play;
$("btn-reset").onclick = () => {
  stopPlay();
  frame = 0;
  $("scrub").value = "0";
  applyFrame(0);
};
$("scrub").oninput = () => {
  stopPlay();
  frame = Number($("scrub").value);
  applyFrame(frame);
};

loadDatasets();
window.addEventListener("resize", () => {
  if (stats) renderStats();
  if (solve) {
    renderSolveCharts();
    applyFrame(frame);
  }
});
