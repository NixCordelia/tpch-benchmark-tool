from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2 import errors as pg_errors
from psycopg2 import sql as pg_sql


class SQLExecutor:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        session_params: dict[str, Any] | None = None,
    ) -> None:
        self._conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "dbname": database,
        }
        self._session_params = session_params or {}

    def execute_sql_files(
        self,
        sql_dir: str | Path,
        concurrency: int,
        timeout: int,
        warmup: bool,
    ) -> list[dict]:
        sql_files = self._discover_sql_files(sql_dir)
        workers = max(1, concurrency)

        if warmup:
            self._run_batch(sql_files, workers, timeout, record=False)

        return self._run_batch(sql_files, workers, timeout, record=True)

    def _discover_sql_files(self, sql_dir: str | Path) -> list[Path]:
        directory = Path(sql_dir)
        if not directory.is_dir():
            raise FileNotFoundError(f"SQL 目录不存在: {directory}")

        return sorted(directory.glob("*.sql"), key=self._sql_sort_key)

    @staticmethod
    def _sql_sort_key(path: Path) -> tuple[int, int | str]:
        stem = path.stem
        if stem.isdigit():
            return (0, int(stem))
        return (1, stem)

    def _run_batch(
        self,
        sql_files: list[Path],
        workers: int,
        timeout: int,
        record: bool,
    ) -> list[dict]:
        if not sql_files:
            return []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            if record:
                futures = [
                    executor.submit(self._execute_timed, path, timeout)
                    for path in sql_files
                ]
                return [future.result() for future in futures]

            futures = [
                executor.submit(self._execute_warmup, path, timeout)
                for path in sql_files
            ]
            for future in futures:
                future.result()
            return []

    def _execute_warmup(self, path: Path, timeout: int) -> None:
        try:
            self._run_sql(path, timeout)
        except Exception:
            pass

    def _execute_timed(self, path: Path, timeout: int) -> dict:
        query_id = path.stem
        start_time = datetime.now()

        try:
            self._run_sql(path, timeout)
            end_time = datetime.now()
            return self._build_result(
                query_id=query_id,
                start_time=start_time,
                end_time=end_time,
                success=True,
                error_message=None,
            )
        except Exception as exc:
            end_time = datetime.now()
            return self._build_result(
                query_id=query_id,
                start_time=start_time,
                end_time=end_time,
                success=False,
                error_message="TIMEOUT" if self._is_timeout_error(exc) else str(exc),
            )

    @staticmethod
    def _build_result(
        query_id: str,
        start_time: datetime,
        end_time: datetime,
        success: bool,
        error_message: str | None,
    ) -> dict:
        elapsed_ms = (end_time - start_time).total_seconds() * 1000
        return {
            "query_id": query_id,
            "start_time": start_time.isoformat(timespec="milliseconds"),
            "end_time": end_time.isoformat(timespec="milliseconds"),
            "elapsed_ms": round(elapsed_ms, 2),
            "success": success,
            "error_message": error_message,
        }

    def _run_sql(self, path: Path, timeout: int) -> None:
        sql = path.read_text(encoding="utf-8").strip()
        if not sql:
            raise ValueError(f"SQL 文件为空: {path}")

        conn = psycopg2.connect(**self._conn_params)
        try:
            conn.autocommit = True
            with conn.cursor() as cursor:
                timeout_ms = max(0, int(timeout)) * 1000
                cursor.execute("SET statement_timeout = %s", (timeout_ms,))
                for key, value in self._session_params.items():
                    cursor.execute(
                        pg_sql.SQL("SET {} = %s").format(pg_sql.Identifier(str(key))),
                        (str(value),),
                    )
                cursor.execute(sql)
                if cursor.description is not None:
                    cursor.fetchall()
        finally:
            conn.close()

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        if isinstance(exc, pg_errors.QueryCanceled):
            return True
        message = str(exc).lower()
        return "statement timeout" in message or "canceling statement due to statement timeout" in message
