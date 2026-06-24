"""Run a .sql file against DuckDB (wired to MinIO).

Usage: py run_query.py sql/query_silver_wikidata.sql
"""
import sys

from setup_buckets import get_duckdb_connection


if hasattr(sys.stdout, "reconfigure"):
    # DuckDB EXPLAIN plans use Unicode box-drawing characters. Force UTF-8 so
    # they render correctly in Windows terminals that default to CP1252.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    con = get_duckdb_connection()
    df = con.execute(sql).fetchdf()
    print(f"=== {path} ===")
    print(df.to_string(index=False))
    print(f"\n[{len(df)} rows]")
    con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: py run_query.py <file.sql>")
        sys.exit(1)
    main(sys.argv[1])
