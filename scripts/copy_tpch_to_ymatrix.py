from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import psycopg2
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "data" / "schema_ymatrix.sql"

TABLES = [
    "nation",
    "region",
    "part",
    "supplier",
    "partsupp",
    "customer",
    "orders",
    "lineitem",
]


def _psycopg_kw(db: dict) -> dict:
    return {
        "host": db["host"],
        "port": int(db["port"]),
        "user": db["user"],
        "password": db["password"],
        "dbname": db["database"],
    }


def load_endpoints(config_path: Path) -> tuple[dict, dict]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    src = _psycopg_kw(raw["database"])
    dst = _psycopg_kw(raw["compare"]["target"])
    return src, dst


def ensure_database(dst: dict) -> None:
    admin = {**dst, "dbname": "postgres"}
    conn = psycopg2.connect(**admin)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'tpch'")
            if cur.fetchone() is None:
                cur.execute("CREATE DATABASE tpch")
                print("created database tpch")
            else:
                print("database tpch already exists")
    finally:
        conn.close()


def apply_schema(dst: dict) -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    conn = psycopg2.connect(**dst)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        print(f"applied {SCHEMA.name}")
    finally:
        conn.close()


def copy_tables(src: dict, dst: dict) -> None:
    src_conn = psycopg2.connect(**src)
    dst_conn = psycopg2.connect(**dst)
    dst_conn.autocommit = True
    try:
        for table in TABLES:
            buf = io.BytesIO()
            with src_conn.cursor() as cur:
                cur.copy_expert(f"COPY {table} TO STDOUT WITH (FORMAT csv)", buf)
            payload = buf.getvalue()
            buf.seek(0)
            with dst_conn.cursor() as cur:
                cur.execute(f"TRUNCATE {table} CASCADE")
                cur.copy_expert(f"COPY {table} FROM STDIN WITH (FORMAT csv)", buf)
            print(f"copied {table}: {len(payload)} bytes")
    finally:
        src_conn.close()
        dst_conn.close()


def verify_and_index(src: dict, dst: dict) -> None:
    src_conn = psycopg2.connect(**src)
    dst_conn = psycopg2.connect(**dst)
    dst_conn.autocommit = True
    try:
        print("row counts (postgres -> ymatrix):")
        with src_conn.cursor() as sc, dst_conn.cursor() as dc:
            for table in TABLES:
                sc.execute(f"SELECT COUNT(*) FROM {table}")
                dc.execute(f"SELECT COUNT(*) FROM {table}")
                left, right = sc.fetchone()[0], dc.fetchone()[0]
                mark = "OK" if left == right else "MISMATCH"
                print(f"  {table}: {left} -> {right} [{mark}]")
                if left != right:
                    raise SystemExit(f"row count mismatch on {table}")
            dc.execute(
                "CREATE INDEX IF NOT EXISTS idx_lineitem_combo "
                "ON lineitem (l_partkey, l_suppkey, l_shipdate)"
            )
            dc.execute("ANALYZE")
        print("created idx_lineitem_combo and ANALYZE")
    finally:
        src_conn.close()
        dst_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="从 PostgreSQL COPY TPC-H 表到 YMatrix")
    parser.add_argument(
        "--config",
        default="config.compare.yaml",
        help="含 database 与 compare.target 的 YAML（默认: config.compare.yaml）",
    )
    args = parser.parse_args()
    config_path = Path(args.config)
    if not config_path.is_file():
        raise FileNotFoundError(
            f"配置文件不存在: {config_path}。请先复制 config.compare.example.yaml"
        )
    src, dst = load_endpoints(config_path)
    ensure_database(dst)
    apply_schema(dst)
    copy_tables(src, dst)
    verify_and_index(src, dst)
    print("done")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"failed: {exc}", file=sys.stderr)
        sys.exit(1)
