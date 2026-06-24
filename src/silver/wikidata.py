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

import pandas as pd
from deltalake import DeltaTable, write_deltalake

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("silver_wikidata")

BRONZE_LATEST = "wikidata/jatim_kelurahan_latest.json"
PARQUET_OBJECT = "wikidata/parquet/jatim_adm4.parquet"
DELTA_URI = f"s3://{config.BUCKET_SILVER}/wikidata/delta"

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
    write_parquet(df)
    write_delta(df)
    log.info("silver done: %d ADM4 rows | with_pop=%d with_coord=%d",
             len(df), int(df["populasi"].notna().sum()), int(df["lat"].notna().sum()))


if __name__ == "__main__":
    run()
