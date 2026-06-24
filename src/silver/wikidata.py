"""Silver layer: clean + normalize Bronze Wikidata -> Parquet + Delta Lake on MinIO.

Steps:
- Read bronze latest JSON envelope
- Flatten SPARQL bindings to tabular rows
- Dedup per item (aggregate: take first non-null coord/pop/area, keep parent=kecamatan)
- Type cast (pop int, area/lat/lon float)
- Write Parquet snapshot to s3://silver/wikidata/parquet/
- Write Delta Lake table to s3://silver/wikidata/delta/ (versioning via _delta_log)

Run: py -m src.silver.wikidata
"""
import json
from pathlib import Path

import pandas as pd
from deltalake import DeltaTable, write_deltalake

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("silver_wikidata")

BRONZE_LATEST = "wikidata/latest.json"
PARQUET_OBJECT = "wikidata/data.parquet"
DELTA_URI = f"s3://{config.BUCKET_SILVER}/wikidata"

# Enrichment adm4: master BMKG dari folder lokal 'Data ADM4/'
ADM4_DATA_DIR = Path("Data ADM4")
COORD_THRESHOLD = 0.05  # derajat (~5.5 km), batas fallback koordinat

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL": f"http://{config.MINIO_ENDPOINT}",
    "AWS_ACCESS_KEY_ID": config.MINIO_ACCESS_KEY,
    "AWS_SECRET_ACCESS_KEY": config.MINIO_SECRET_KEY,
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}


def _val(binding: dict, key: str):
    node = binding.get(key)
    return node.get("value") if node else None


def _qid(uri: str | None):
    return uri.rsplit("/", 1)[-1] if uri else None


def load_bronze() -> list[dict]:
    client = get_minio_client()
    raw = json.loads(client.get_object(config.BUCKET_BRONZE, BRONZE_LATEST).read())
    bindings = raw["data"]["results"]["bindings"]
    log.info("loaded %d bronze bindings", len(bindings))
    return bindings


def to_dataframe(bindings: list[dict]) -> pd.DataFrame:
    rows = []
    for b in bindings:
        rows.append({
            "wikidata_id": _qid(_val(b, "item")),
            "nama_wilayah": _val(b, "itemLabel"),
            "tipe": _val(b, "typeLabel"),          # desa / kelurahan
            "parent_id": _qid(_val(b, "parent")),
            "kecamatan": _val(b, "parentLabel"),
            "populasi": _val(b, "pop"),
            "area_km2": _val(b, "area"),
            "lat": _val(b, "lat"),
            "lon": _val(b, "lon"),
        })
    df = pd.DataFrame(rows)

    # numeric casts
    for col in ("populasi",):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in ("area_km2", "lat", "lon"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # drop rows w/o id or w/o name (QID-only labels = no Indonesian label)
    before = len(df)
    df = df[df["wikidata_id"].notna()]
    df = df[~df["nama_wilayah"].fillna("").str.match(r"^Q\d+$")]

    # dedup per item: aggregate to one row, keep first non-null per field
    agg = (
        df.sort_values(["wikidata_id"])
          .groupby("wikidata_id", as_index=False)
          .agg({
              "nama_wilayah": "first",
              "tipe": "first",
              "parent_id": "first",
              "kecamatan": "first",
              "populasi": "first",
              "area_km2": "first",
              "lat": "first",
              "lon": "first",
          })
    )
    log.info("rows: %d bindings -> %d clean -> %d unique items", before, len(df), len(agg))
    return agg


def _norm(s) -> str:
    return str(s).strip().lower() if s is not None else ""


def _build_adm4_master() -> pd.DataFrame:
    """Master ADM4 dari file BMKG: adm4, desa, kecamatan, lat, lon."""
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


def enrich_adm4(df: pd.DataFrame) -> pd.DataFrame:
    """Tambah kolom adm4 (join key ke BMKG/Gold) + match_method.

    Strategi: exact (nama_desa + kecamatan), fallback koordinat terdekat (~5km).
    """
    if not ADM4_DATA_DIR.exists():
        log.warning("'%s' tidak ada - lewati enrichment adm4", ADM4_DATA_DIR)
        df["adm4"] = None
        df["match_method"] = "skipped"
        return df

    master = _build_adm4_master()
    if master.empty:
        df["adm4"] = None
        df["match_method"] = "no_master"
        return df

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

    matched = int(df["adm4"].notna().sum())
    log.info("adm4 match: %d/%d (%.1f%%) | breakdown=%s",
             matched, len(df), 100 * matched / len(df),
             df["match_method"].value_counts().to_dict())
    return df


def write_parquet(df: pd.DataFrame) -> None:
    import io
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    size = buf.getbuffer().nbytes
    get_minio_client().put_object(
        config.BUCKET_SILVER, PARQUET_OBJECT, buf, length=size,
        content_type="application/octet-stream",
    )
    log.info("wrote s3://%s/%s (%d bytes)", config.BUCKET_SILVER, PARQUET_OBJECT, size)


def write_delta(df: pd.DataFrame) -> None:
    write_deltalake(DELTA_URI, df, mode="overwrite",
                    storage_options=STORAGE_OPTIONS, schema_mode="overwrite")
    dt = DeltaTable(DELTA_URI, storage_options=STORAGE_OPTIONS)
    log.info("wrote Delta table %s version=%d rows=%d", DELTA_URI, dt.version(), len(df))


def run() -> None:
    df = to_dataframe(load_bronze())
    df = enrich_adm4(df)            # tambah kolom adm4 (join key ke BMKG/Gold)
    write_parquet(df)
    write_delta(df)
    log.info("silver done: %d ADM4 rows | with_pop=%d with_coord=%d",
             len(df), int(df["populasi"].notna().sum()), int(df["lat"].notna().sum()))


if __name__ == "__main__":
    run()
