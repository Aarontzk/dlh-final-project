"""Central config for DLH lakehouse pipeline (MinIO + DuckDB)."""
import os

# --- MinIO / S3 ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

BUCKET_BRONZE = "bronze"
BUCKET_SILVER = "silver"
BUCKET_GOLD = "gold"
BUCKETS = [BUCKET_BRONZE, BUCKET_SILVER, BUCKET_GOLD]

# --- DuckDB ---
DUCKDB_PATH = os.getenv("DUCKDB_PATH", os.path.join("data", "lakehouse.duckdb"))

# --- Wikidata (Aka) ---
# ADM4 (kelurahan Q965568 + desa Q26211545) di Provinsi Jawa Timur (Q3586),
# transitif via P131* (kelurahan/desa -> kecamatan -> kabupaten/kota -> provinsi).
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_PROVINCE_QID = "Q3586"  # Jawa Timur
WIKIDATA_QUERY = """
SELECT ?item ?itemLabel ?typeLabel ?parent ?parentLabel ?pop ?area ?lat ?lon WHERE {
  VALUES ?type { wd:Q965568 wd:Q26211545 }   # kelurahan, desa
  ?item wdt:P31 ?type .
  ?item wdt:P131* wd:Q3586 .
  OPTIONAL { ?item wdt:P131 ?parent }
  OPTIONAL { ?item wdt:P1082 ?pop }
  OPTIONAL { ?item wdt:P2046 ?area }
  OPTIONAL {
    ?item p:P625/psv:P625 ?coordNode .
    ?coordNode wikibase:geoLatitude  ?lat .
    ?coordNode wikibase:geoLongitude ?lon .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "id,en" }
}
"""
WIKIDATA_USER_AGENT = "DLH-Lakehouse-Project/1.0 (ITS SI; educational)"

# --- BMKG (Fabio) ---
BMKG_API_BASE = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

# --- BX1: custom metadata ---
SOURCE_API_VERSION = "wikidata-sparql-v1"
OPERATOR_ID = "aka"
