"""Silver layer: flatten + clean Bronze BMKG ADM4 -> Parquet + Delta Lake on MinIO.

Steps:
- List bmkg/{adm4_code}/raw_{timestamp}.json objects from bronze bucket
- Select only the latest raw snapshot for each ADM4 code
- Parse each envelope: extract lokasi + iterate data[].cuaca[][] for forecast rows
- Flatten to tabular: one row per (adm4, datetime) slot
- Handle nulls + anomalies, enforce types (t->float, datetime->timestamp)
- Write Parquet snapshot to s3://silver/bmkg/data.parquet
- Write Delta Lake table to s3://silver/bmkg/ (versioning via _delta_log)

Run: py -m src.silver.bmkg
"""
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from deltalake import DeltaTable, write_deltalake

# Bootstrap: allow running this file directly (VS Code Run button), not just via -m
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("silver_bmkg")

BRONZE_PREFIX = "bmkg/"
PARQUET_OBJECT = "bmkg/data.parquet"
DELTA_URI = f"s3://{config.BUCKET_SILVER}/bmkg"
MAX_WORKERS = 16

RAW_OBJECT_PATTERN = re.compile(
    r"^bmkg/(?P<adm4>[^/]+)/raw_(?P<timestamp>\d{8}T\d{6}Z)\.json$"
)

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
    """Return the latest raw snapshot object for every ADM4 code.

    Manifest and malformed object paths are ignored. Snapshot timestamps use
    a sortable UTC format, so lexical comparison selects the latest version.
    """
    objects = client.list_objects(config.BUCKET_BRONZE, prefix=BRONZE_PREFIX, recursive=True)
    latest_by_adm4: dict[str, tuple[str, str]] = {}
    raw_candidates = 0
    ignored = 0

    for obj in objects:
        match = RAW_OBJECT_PATTERN.fullmatch(obj.object_name)
        if not match:
            ignored += 1
            continue

        raw_candidates += 1
        adm4 = match.group("adm4")
        timestamp = match.group("timestamp")
        current = latest_by_adm4.get(adm4)
        if current is None or timestamp > current[0]:
            latest_by_adm4[adm4] = (timestamp, obj.object_name)

    names = sorted(value[1] for value in latest_by_adm4.values())
    log.info(
        "bronze discovery: %d raw snapshots -> %d latest ADM4 objects (%d ignored)",
        raw_candidates,
        len(names),
        ignored,
    )
    return names


def _fetch_one(client, obj_name: str) -> list[dict]:
    """Fetch one bronze object and return flattened forecast rows."""
    raw = client.get_object(config.BUCKET_BRONZE, obj_name).read()
    envelope = json.loads(raw)
    # Bronze uploader wraps the original response in {_metadata, data}.
    # Also accept a bare BMKG response for safer reprocessing/manual imports.
    payload = envelope.get("data") if "_metadata" in envelope else envelope
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid BMKG payload in {obj_name}: expected a JSON object")

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
    if failed:
        raise RuntimeError(
            f"Failed to parse {failed} of {len(obj_names)} latest Bronze BMKG objects; "
            "Silver output was not written to avoid publishing incomplete data."
        )
    return all_rows


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        raise RuntimeError(
            "No BMKG forecast rows found under "
            "bronze/bmkg/{adm4_code}/raw_{timestamp}.json. "
            "Run `py -m src.bronze.adm4` first."
        )
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
