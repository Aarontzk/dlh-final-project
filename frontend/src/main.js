import "./style.css";
import { initDb, query } from "./db.js";
import {
  buildExploreSql,
  buildSummarySql,
  buildMapSql,
  PRESETS,
  RISIKO_ORDER,
  RISIKO_COLOR,
} from "./queries.js";
import { renderBar } from "./charts.js";
import { renderMap, renderLegend } from "./map.js";

const $ = (sel) => document.querySelector(sel);

// Status indikator: cuma muncul saat memuat / error. Data lokal kecil, query
// instan, jadi tidak ada teks status "selesai" yang berisik.
const statusEl = $("#status");
function showBusy(msg = "memuat") {
  statusEl.textContent = msg;
  statusEl.classList.add("busy");
  statusEl.classList.remove("err");
  statusEl.hidden = false;
}
function showIdle() {
  statusEl.hidden = true;
  statusEl.classList.remove("busy", "err");
}
function showError(msg) {
  statusEl.textContent = msg;
  statusEl.classList.add("err");
  statusEl.classList.remove("busy");
  statusEl.hidden = false;
}

const state = {
  kabupaten: "",
  risiko: [],
  cuaca: "",
  suhuMin: null,
  suhuMax: null,
  tanggal: "",
  groupBy: "kabupaten",
};

let mapLoaded = false;

// ---------- util render ----------
function renderTable(el, rows) {
  if (!rows.length) {
    el.innerHTML = "<caption class='muted'>Tidak ada data untuk filter ini.</caption>";
    return;
  }
  const cols = Object.keys(rows[0]);
  const head = `<thead><tr>${cols
    .map((c) => `<th>${c.replace(/_/g, " ")}</th>`)
    .join("")}</tr></thead>`;
  const body = rows
    .map(
      (r) =>
        `<tr>${cols.map((c) => `<td>${fmt(r[c], c)}</td>`).join("")}</tr>`,
    )
    .join("");
  el.innerHTML = head + `<tbody>${body}</tbody>`;
}

function fmt(v, col) {
  if (v == null) return "-";
  if (col === "kategori_risiko" || col === "risiko_tertinggi") {
    const c = RISIKO_COLOR[v] ?? "#94a3b8";
    return `<span class="pill" style="background:${c}22;color:${c};border-color:${c}55">${v}</span>`;
  }
  if (typeof v === "number") return v.toLocaleString("id-ID");
  return v;
}

// ---------- init filters ----------
async function populateFilters() {
  const kab = await query(
    "SELECT DISTINCT kabupaten FROM dim_wilayah ORDER BY kabupaten",
  );
  $("#f-kabupaten").insertAdjacentHTML(
    "beforeend",
    kab.map((r) => `<option>${r.kabupaten}</option>`).join(""),
  );

  const cuaca = await query(
    "SELECT DISTINCT deskripsi FROM dim_cuaca ORDER BY deskripsi",
  );
  $("#f-cuaca").insertAdjacentHTML(
    "beforeend",
    cuaca.map((r) => `<option>${r.deskripsi}</option>`).join(""),
  );

  const tgl = await query(
    "SELECT DISTINCT tanggal FROM dim_waktu ORDER BY tanggal",
  );
  $("#f-tanggal").insertAdjacentHTML(
    "beforeend",
    tgl.map((r) => `<option>${r.tanggal}</option>`).join(""),
  );

  // chips risiko
  $("#f-risiko").innerHTML = RISIKO_ORDER.map(
    (r) =>
      `<button type="button" class="chip" data-risiko="${r}" style="--c:${RISIKO_COLOR[r]}">${r}</button>`,
  ).join("");

  // suhu range
  const [{ lo, hi }] = await query(
    "SELECT MIN(suhu) AS lo, MAX(suhu) AS hi FROM fact_prakiraan_cuaca",
  );
  const mn = $("#f-suhu-min");
  const mx = $("#f-suhu-max");
  for (const el of [mn, mx]) {
    el.min = lo;
    el.max = hi;
    el.step = 1;
  }
  mn.value = lo;
  mx.value = hi;
  state.suhuMin = lo;
  state.suhuMax = hi;
  updateSuhuLabel();
}

function updateSuhuLabel() {
  $("#suhu-label").textContent = `${state.suhuMin}-${state.suhuMax}`;
}

// ---------- explore run ----------
async function runExplore() {
  try {
    const [summary] = await query(buildSummarySql(state));
    renderStatCards(summary);

    const rows = await query(buildExploreSql(state));
    renderBar(
      $("#chart"),
      rows.map((r) => r.grup),
      rows.map((r) => r.jumlah_prakiraan),
      "Jumlah prakiraan",
    );
    renderTable($("#table"), rows);
    showIdle();
  } catch (e) {
    showError("Gagal memuat data");
    console.error(e);
  }
}

function renderStatCards(s) {
  const cards = [
    ["Total prakiraan", s.total_prakiraan?.toLocaleString("id-ID") ?? "-"],
    ["Wilayah unik", s.total_wilayah?.toLocaleString("id-ID") ?? "-"],
    ["Rata suhu", s.rata_suhu != null ? `${s.rata_suhu}°C` : "-"],
    [
      "Risiko tinggi/ekstrem",
      s.persen_risiko_tinggi != null ? `${s.persen_risiko_tinggi}%` : "-",
    ],
  ];
  $("#stat-cards").innerHTML = cards
    .map(([k, v]) => `<div class="card"><span>${k}</span><strong>${v}</strong></div>`)
    .join("");
}

// ---------- presets ----------
function buildPresetCards() {
  $("#question-grid").innerHTML = PRESETS.map(
    (p) =>
      `<button class="qcard" data-id="${p.id}"><h4>${p.judul}</h4><p>${p.desc}</p></button>`,
  ).join("");
}

async function runPreset(id) {
  const p = PRESETS.find((x) => x.id === id);
  if (!p) return;
  $("#preset-title").textContent = p.judul;
  $("#preset-desc").textContent = p.desc;
  try {
    const rows = await query(p.sql);
    renderTable($("#preset-table"), rows);
    showIdle();
  } catch (e) {
    showError("Gagal menjalankan query");
    console.error(e);
  }
}

// ---------- map ----------
async function loadMap() {
  renderLegend($("#map-legend"));
  showBusy("memuat peta");
  try {
    const rows = await query(buildMapSql(state));
    renderMap(rows);
    mapLoaded = true;
    showIdle();
  } catch (e) {
    showError("Gagal memuat peta");
    console.error(e);
  }
}

// ---------- tabs ----------
function switchTab(name) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document
    .querySelectorAll(".panel")
    .forEach((p) => (p.hidden = p.dataset.panel !== name));
  if (name === "peta" && !mapLoaded) loadMap();
}

// ---------- events ----------
function wireEvents() {
  $("#tabs").addEventListener("click", (e) => {
    const t = e.target.closest(".tab");
    if (t) switchTab(t.dataset.tab);
  });

  $("#f-risiko").addEventListener("click", (e) => {
    const b = e.target.closest(".chip");
    if (!b) return;
    b.classList.toggle("on");
    const r = b.dataset.risiko;
    state.risiko = state.risiko.includes(r)
      ? state.risiko.filter((x) => x !== r)
      : [...state.risiko, r];
  });

  $("#f-kabupaten").addEventListener("change", (e) => (state.kabupaten = e.target.value));
  $("#f-cuaca").addEventListener("change", (e) => (state.cuaca = e.target.value));
  $("#f-tanggal").addEventListener("change", (e) => (state.tanggal = e.target.value));
  $("#f-groupby").addEventListener("change", (e) => (state.groupBy = e.target.value));

  $("#f-suhu-min").addEventListener("input", (e) => {
    state.suhuMin = Math.min(Number(e.target.value), state.suhuMax);
    e.target.value = state.suhuMin;
    updateSuhuLabel();
  });
  $("#f-suhu-max").addEventListener("input", (e) => {
    state.suhuMax = Math.max(Number(e.target.value), state.suhuMin);
    e.target.value = state.suhuMax;
    updateSuhuLabel();
  });

  $("#btn-run").addEventListener("click", () => {
    mapLoaded = false; // filter berubah -> peta perlu refresh saat dibuka
    runExplore();
  });
  $("#btn-reset").addEventListener("click", () => location.reload());

  $("#question-grid").addEventListener("click", (e) => {
    const c = e.target.closest(".qcard");
    if (c) runPreset(c.dataset.id);
  });
}

// ---------- boot ----------
async function main() {
  try {
    showBusy("memuat");
    await initDb();
    await populateFilters();
    buildPresetCards();
    wireEvents();
    $("#tabs").hidden = false;
    $("#app").hidden = false;
    await runExplore();
    showIdle();
  } catch (e) {
    showError("Gagal memuat aplikasi");
    console.error(e);
  }
}

main();
