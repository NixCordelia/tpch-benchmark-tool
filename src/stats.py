from __future__ import annotations

from typing import Any

import numpy as np

StatRecord = dict[str, Any]


def _query_id_sort_key(query_id: str) -> tuple[int, int | str]:
    if query_id.isdigit():
        return (0, int(query_id))
    return (1, query_id)


def sort_by_query_id(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: _query_id_sort_key(item["query_id"]))


def compute_stats(results: list[dict]) -> list[StatRecord]:
    grouped: dict[str, list[dict]] = {}
    for row in results:
        grouped.setdefault(row["query_id"], []).append(row)

    stats_list: list[StatRecord] = []
    for query_id, rows in grouped.items():
        count = len(rows)
        successful = [row for row in rows if row.get("success")]
        success_count = len(successful)

        if success_count == 0:
            stats_list.append(
                {
                    "query_id": query_id,
                    "count": count,
                    "avg_ms": None,
                    "min_ms": None,
                    "max_ms": None,
                    "p95_ms": None,
                    "success_rate": 0.0,
                }
            )
            continue

        elapsed = np.array([row["elapsed_ms"] for row in successful], dtype=float)
        stats_list.append(
            {
                "query_id": query_id,
                "count": count,
                "avg_ms": round(float(np.mean(elapsed)), 2),
                "min_ms": round(float(np.min(elapsed)), 2),
                "max_ms": round(float(np.max(elapsed)), 2),
                "p95_ms": round(float(np.percentile(elapsed, 95)), 2),
                "success_rate": round(success_count / count, 4),
            }
        )

    return sort_by_query_id(stats_list)


def compare_stats(results1: list[dict], results2: list[dict]) -> list[StatRecord]:
    stats_map1 = {item["query_id"]: item for item in compute_stats(results1)}
    stats_map2 = {item["query_id"]: item for item in compute_stats(results2)}
    query_ids = sort_by_query_id(
        [{"query_id": query_id} for query_id in stats_map1.keys() | stats_map2.keys()]
    )

    comparisons: list[StatRecord] = []
    for item in query_ids:
        query_id = item["query_id"]
        stats1 = stats_map1.get(query_id)
        stats2 = stats_map2.get(query_id)

        avg_ms_1 = stats1["avg_ms"] if stats1 else None
        avg_ms_2 = stats2["avg_ms"] if stats2 else None

        if avg_ms_1 is not None and avg_ms_2 is not None:
            diff_ms = round(avg_ms_2 - avg_ms_1, 2)
            diff_percentage = round((diff_ms / avg_ms_1) * 100, 2) if avg_ms_1 != 0 else None
        else:
            diff_ms = None
            diff_percentage = None

        comparisons.append(
            {
                "query_id": query_id,
                "stats1": stats1,
                "stats2": stats2,
                "diff_ms": diff_ms,
                "diff_percentage": diff_percentage,
            }
        )

    return comparisons
