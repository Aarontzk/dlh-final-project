"""Silver layer: flatten + clean Bronze BMKG ADM4 -> Parquet + Delta Lake on MinIO.

Steps:
- List all adm4/raw/*.json objects from bronze bucket
- Parse each envelope: extract lokasi + iterate data[].cuaca[][] for forecast rows
- Flatten to tabular: one row per (adm4, datetime) slot
- Handle nulls + anomalies, enforce types (t->float, datetime->timestamp)
- Write Parquet snapshot to s3://silver/bmkg/parquet/data.parquet
- Write Delta Lake table to s3://silver/bmkg/delta/ (versioning via _delta_log)

Run: py -m src.silver.bmkg
"""
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from deltalake import DeltaTable, write_deltalake

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("silver_bmkg")

BRONZE_PREFIX = "adm4/raw/"
PARQUET_OBJECT = "bmkg/data.parquet"
DELTA_URI = f"s3://{config.BUCKET_SILVER}/bmkg"
MAX_WORKERS = 16

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL": f"http://{config.MINIO_ENDPOINT}",
    "AWS_ACCESS_KEY_ID": config.MINIO_ACCESS_KEY,
    "AWS_SECRET_ACCESS_KEY": config.MINIO_SECRET_KEY,
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

# Reasonable bounds for Jawa Timur weather — values outside are anomalies
TEMP_MIN, TEMP_MAX = -5.0, 55.0
HUMIDITY_MIN, HUMIDITY_MAX = 0.0, 100.0
WIND_SPEED_MIN = 0.0
PRECIP_MIN = 0.0


def _list_bronze_objects(client) -> list[str]:
    objects = client.list_objects(config.BUCKET_BRONZE, prefix=BRONZE_PREFIX, recursive=True)
    names = [obj.object_name for obj in objects if obj.object_name.endswith(".json")]
    log.info("found %d bronze ADM4 objects", len(names))
    return names


def _fetch_one(client, obj_name: str) -> list[dict]:
    """Fetch one bronze object and return flattened forecast rows."""
    raw = client.get_object(config.BUCKET_BRONZE, obj_name).read()
    envelope = json.loads(raw)
    payload = envelope.get("data", envelope)  # unwrap _metadata envelope

    top_lokasi = payload.get("lokasi", {})
    adm4 = top_lokasi.get("adm4", "")
    adm1 = top_lokasi.get("adm1", "")
    adm2 = top_lokasi.get("adm2", "")
    adm3 = top_lokasi.get("adm3", "")
    provinsi = top_lokasi.get("provinsi", "")
    kotkab = top_lokasi.get("kotkab", "")
    kecamatan = top_lokasi.get("kecamatan", "")
    desa = top_lokasi.get("desa", "")
    lat = top_lokasi.get("lat")
    lon = top_lokasi.get("lon")

    rows = []
    for day_block in payload.get("data", []):
        cuaca_groups = day_block.get("cuaca", [])
        for group in cuaca_groups:
            if not isinstance(group, list):
                group = [group]
            for slot in group:
                if not isinstance(slot, dict):
                    continue
                rows.append({
                    "adm4": adm4,
                    "adm1": adm1,
                    "adm2": adm2,
                    "adm3": adm3,
                    "provinsi": provinsi,
                    "kotkab": kotkab,
                    "kecamatan": kecamatan,
                    "desa": desa,
                    "lat": lat,
                    "lon": lon,
                    "datetime": slot.get("datetime"),
                    "local_datetime": slot.get("local_datetime"),
                    "t": slot.get("t"),
                    "tcc": slot.get("tcc"),
                    "tp": slot.get("tp"),
                    "weather": slot.get("weather"),
                    "weather_desc": slot.get("weather_desc"),
                    "weather_desc_en": slot.get("weather_desc_en"),
                    "wd_deg": slot.get("wd_deg"),
                    "wd": slot.get("wd"),
                    "wd_to": slot.get("wd_to"),
                    "ws": slot.get("ws"),
                    "hu": slot.get("hu"),
                    "vs": slot.get("vs"),
                    "vs_text": slot.get("vs_text"),
                    "analysis_date": slot.get("analysis_date"),
                })
    return rows


def load_bronze(client) -> list[dict]:
    obj_names = _list_bronze_objects(client)
    all_rows: list[dict] = []
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, client, name): name for name in obj_names}
        for i, future in enumerate(as_completed(futures), 1):
            obj_name = futures[future]
            try:
                all_rows.extend(future.result())
            except Exception as exc:
                failed += 1
                log.warning("failed to parse %s: %s", obj_name, exc)
            if i % 500 == 0 or i == len(obj_names):
                log.info("read progress: %d/%d objects, %d rows so far (failed=%d)",
                         i, len(obj_names), len(all_rows), failed)

    log.info("loaded %d total forecast rows from %d objects (%d failed)",
             len(all_rows), len(obj_names), failed)
    return all_rows


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        raise RuntimeError("No rows to process — bronze ADM4 bucket is empty. Run `py -m src.bronze.adm4` first.")
    df = pd.DataFrame(rows)

    # --- type enforcement ---
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df["local_datetime"] = pd.to_datetime(df["local_datetime"], errors="coerce")
    df["analysis_date"] = pd.to_datetime(df["analysis_date"], errors="coerce")

    for col in ("t", "tp", "ws"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in ("hu", "tcc", "weather", "wd_deg", "vs"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in ("lat", "lon"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # --- drop rows missing the primary key (adm4 + datetime) ---
    before = len(df)
    df = df[df["datetime"].notna() & df["adm4"].notna() & (df["adm4"] != "")]
    log.info("dropped %d rows missing adm4/datetime key", before - len(df))

    # --- anomaly handling: clamp out-of-range values to NaN ---
    mask_t = df["t"].notna() & ((df["t"] < TEMP_MIN) | (df["t"] > TEMP_MAX))
    df.loc[mask_t, "t"] = float("nan")
    log.info("nulled %d anomalous temperature values", int(mask_t.sum()))

    mask_hu = df["hu"].notna() & ((df["hu"] < HUMIDITY_MIN) | (df["hu"] > HUMIDITY_MAX))
    df.loc[mask_hu, "hu"] = pd.NA
    log.info("nulled %d anomalous humidity values", int(mask_hu.sum()))

    mask_ws = df["ws"].notna() & (df["ws"] < WIND_SPEED_MIN)
    df.loc[mask_ws, "ws"] = float("nan")
    log.info("nulled %d anomalous wind speed values", int(mask_ws.sum()))

    mask_tp = df["tp"].notna() & (df["tp"] < PRECIP_MIN)
    df.loc[mask_tp, "tp"] = float("nan")
    log.info("nulled %d anomalous precipitation values", int(mask_tp.sum()))

    # --- dedup: keep one row per (adm4, datetime) ---
    before = len(df)
    df = df.drop_duplicates(subset=["adm4", "datetime"], keep="first")
    log.info("deduped: %d -> %d rows (removed %d duplicates)", before, len(df), before - len(df))

    df = df.sort_values(["adm4", "datetime"]).reset_index(drop=True)

    log.info(
        "final shape: %d rows x %d cols | adm4_unique=%d | datetime_range=[%s, %s]",
        len(df), len(df.columns),
        df["adm4"].nunique(),
        df["datetime"].min(),
        df["datetime"].max(),
    )
    return df


def write_parquet(df: pd.DataFrame, client) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    size = buf.getbuffer().nbytes
    client.put_object(
        config.BUCKET_SILVER, PARQUET_OBJECT, buf, length=size,
        content_type="application/octet-stream",
    )
    log.info("wrote s3://%s/%s (%d bytes, %.1f MB)", config.BUCKET_SILVER, PARQUET_OBJECT, size, size / 1e6)


def write_delta(df: pd.DataFrame) -> None:
    write_deltalake(DELTA_URI, df, mode="overwrite",
                    storage_options=STORAGE_OPTIONS, schema_mode="overwrite")
    dt = DeltaTable(DELTA_URI, storage_options=STORAGE_OPTIONS)
    log.info("wrote Delta table %s version=%d rows=%d", DELTA_URI, dt.version(), len(df))


def run() -> None:
    client = get_minio_client()
    rows = load_bronze(client)
    df = to_dataframe(rows)
    write_parquet(df, client)
    write_delta(df)
    log.info(
        "silver bmkg done: %d rows | with_t=%d | with_hu=%d | with_ws=%d",
        len(df),
        int(df["t"].notna().sum()),
        int(df["hu"].notna().sum()),
        int(df["ws"].notna().sum()),
    )


if __name__ == "__main__":
    run()
