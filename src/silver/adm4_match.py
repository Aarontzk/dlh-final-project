"""Enrich Silver Wikidata with BMKG ADM4 code.

Wikidata tidak punya kode ADM4 resmi. Untuk join Gold dengan BMKG, kita tambahkan
kolom adm4 ke Silver Wikidata via pencocokan ke master ADM4 BMKG:

  1. Exact match: (nama_desa, kecamatan) dinormalisasi
  2. Fallback: koordinat terdekat (euclidean lat/lon) dalam ambang ~5km

Master dibangun dari folder 'Data ADM4/' (8369 file JSON BMKG).
"""
import json
from pathlib import Path

import pandas as pd

from logger import get_logger

log = get_logger("adm4_match")

ADM4_DATA_DIR = Path("Data ADM4")
COORD_THRESHOLD = 0.05  # derajat (~5.5 km), batas fallback koordinat


def _norm(s) -> str:
    return str(s).strip().lower() if s is not None else ""


def build_master() -> pd.DataFrame:
    """Master ADM4 dari file BMKG: adm4, desa, kecamatan, kotkab, lat, lon."""
    rows = []
    for fp in ADM4_DATA_DIR.glob("*.json"):
        try:
            loc = json.loads(fp.read_text(encoding="utf-8")).get("lokasi", {})
        except Exception:
            continue
        if not loc.get("adm4"):
            continue
        rows.append({
            "adm4": loc["adm4"],
            "m_desa": _norm(loc.get("desa")),
            "m_kec": _norm(loc.get("kecamatan")),
            "m_lat": loc.get("lat"),
            "m_lon": loc.get("lon"),
        })
    master = pd.DataFrame(rows)
    log.info("ADM4 master: %d rows from %s", len(master), ADM4_DATA_DIR)
    return master


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Tambah kolom adm4 + match_method ke df Silver Wikidata."""
    if not ADM4_DATA_DIR.exists():
        log.warning("'%s' tidak ada - lewati enrichment adm4", ADM4_DATA_DIR)
        df["adm4"] = None
        df["match_method"] = "skipped"
        return df

    master = build_master()
    if master.empty:
        df["adm4"] = None
        df["match_method"] = "no_master"
        return df

    # index exact (desa, kecamatan) -> list adm4 candidates
    exact = {}
    for r in master.itertuples(index=False):
        exact.setdefault((r.m_desa, r.m_kec), []).append(r)

    m_lat = master["m_lat"].to_numpy(dtype="float64")
    m_lon = master["m_lon"].to_numpy(dtype="float64")
    m_adm4 = master["adm4"].to_numpy()

    adm4_out, method_out = [], []
    for r in df.itertuples(index=False):
        nama, kec = _norm(r.nama_wilayah), _norm(r.kecamatan)
        lat, lon = r.lat, r.lon
        cands = exact.get((nama, kec))

        if cands and len(cands) == 1:
            adm4_out.append(cands[0].adm4); method_out.append("exact")
            continue
        if cands and len(cands) > 1 and pd.notna(lat):
            # banyak kandidat nama sama -> pilih terdekat koordinat
            best = min(cands, key=lambda c: (c.m_lat - lat) ** 2 + (c.m_lon - lon) ** 2)
            adm4_out.append(best.adm4); method_out.append("exact_coord")
            continue
        if pd.notna(lat) and pd.notna(lon):
            d2 = (m_lat - lat) ** 2 + (m_lon - lon) ** 2
            i = int(d2.argmin())
            if d2[i] <= COORD_THRESHOLD ** 2:
                adm4_out.append(m_adm4[i]); method_out.append("coord")
                continue
        adm4_out.append(None); method_out.append("unmatched")

    df = df.copy()
    df["adm4"] = adm4_out
    df["match_method"] = method_out

    vc = df["match_method"].value_counts().to_dict()
    matched = int(df["adm4"].notna().sum())
    log.info("adm4 match: %d/%d (%.1f%%) | breakdown=%s",
             matched, len(df), 100 * matched / len(df), vc)
    return df
