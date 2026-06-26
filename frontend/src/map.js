// Peta Leaflet: titik kelurahan/desa diwarnai per kategori risiko tertinggi.
// Pakai canvas renderer biar ribuan titik tetap ringan.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { RISIKO_COLOR, RISIKO_ORDER } from "./queries.js";

let _map = null;
let _layer = null;

const JATIM_CENTER = [-7.75, 112.5];

function ensureMap() {
  if (_map) return _map;
  _map = L.map("map", { preferCanvas: true }).setView(JATIM_CENTER, 8);
  // Tile gelap (CartoDB dark) menyatu dengan tema QuestUI.
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    {
      maxZoom: 19,
      subdomains: "abcd",
      attribution: "© OpenStreetMap © CARTO",
    },
  ).addTo(_map);
  return _map;
}

/**
 * @param {Array<{lat:number,lon:number,nama_desa:string,kecamatan:string,
 *   kabupaten:string,risiko_tertinggi:string,jumlah_prakiraan:number}>} rows
 */
export function renderMap(rows) {
  const map = ensureMap();
  if (_layer) _layer.remove();
  _layer = L.layerGroup();

  for (const r of rows) {
    if (r.lat == null || r.lon == null) continue;
    const color = RISIKO_COLOR[r.risiko_tertinggi] ?? "#94a3b8";
    L.circleMarker([r.lat, r.lon], {
      radius: 4,
      color,
      fillColor: color,
      fillOpacity: 0.75,
      weight: 1,
    })
      .bindPopup(
        `<strong>${r.nama_desa}</strong><br>${r.kecamatan}, ${r.kabupaten}` +
          `<br>Risiko tertinggi: <b>${r.risiko_tertinggi}</b>` +
          `<br>${r.jumlah_prakiraan} prakiraan`,
      )
      .addTo(_layer);
  }
  _layer.addTo(map);
  // Leaflet butuh recalculation kalau container baru tampil.
  setTimeout(() => map.invalidateSize(), 50);
}

export function renderLegend(el) {
  el.innerHTML =
    "<span class='legend-title'>Risiko tertinggi:</span>" +
    RISIKO_ORDER.map(
      (r) =>
        `<span class="legend-item"><i style="background:${RISIKO_COLOR[r]}"></i>${r}</span>`,
    ).join("");
}
