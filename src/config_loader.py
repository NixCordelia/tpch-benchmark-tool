from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "user": "tpch",
        "password": "",
        "database": "tpch",
        "session_params": {},
    },
    "test": {
        "sql_dir": "./sql",
        "rounds": 3,
        "concurrency": 2,
        "warmup": True,
        "timeout": 300,
    },
    "compare": {
        "enabled": False,
        "target": {
            "host": "localhost",
            "port": 5433,
            "user": "tpch",
            "password": "",
            "database": "tpch",
            "session_params": {},
        },
    },
}


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    session_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestConfig:
    sql_dir: str
    rounds: int
    concurrency: int
    warmup: bool
    timeout: int


@dataclass
class CompareConfig:
    enabled: bool
    target: DatabaseConfig


@dataclass
class Config:
    database: DatabaseConfig
    test: TestConfig
    compare: CompareConfig


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, default_value in defaults.items():
        if key not in overrides:
            merged[key] = default_value
        elif isinstance(default_value, dict) and isinstance(overrides[key], dict):
            merged[key] = _deep_merge(default_value, overrides[key])
        else:
            merged[key] = overrides[key]
    return merged


def _parse_database(data: dict[str, Any]) -> DatabaseConfig:
    return DatabaseConfig(
        host=data["host"],
        port=data["port"],
        user=data["user"],
        password=data["password"],
        database=data["database"],
        session_params=data.get("session_params") or {},
    )


def _parse_config(data: dict[str, Any]) -> Config:
    return Config(
        database=_parse_database(data["database"]),
        test=TestConfig(
            sql_dir=data["test"]["sql_dir"],
            rounds=data["test"]["rounds"],
            concurrency=data["test"]["concurrency"],
            warmup=data["test"]["warmup"],
            timeout=data["test"]["timeout"],
        ),
        compare=CompareConfig(
            enabled=data["compare"]["enabled"],
            target=_parse_database(data["compare"]["target"]),
        ),
    )


def load_config(config_path: str | Path) -> Config:
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"配置文件格式无效: {path}")

    merged = _deep_merge(DEFAULT_CONFIG, raw)
    return _parse_config(merged)
