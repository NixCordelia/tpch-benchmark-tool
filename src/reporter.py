from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from stats import sort_by_query_id

StatRecord = dict[str, Any]
ResultRecord = dict[str, Any]

CSV_FIELDS = [
    "query_id",
    "start_time",
    "end_time",
    "elapsed_ms",
    "success",
    "error_message",
]


def generate_csv(results: list[ResultRecord], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = sort_by_query_id(results)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "query_id": row["query_id"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "elapsed_ms": row["elapsed_ms"],
                    "success": row["success"],
                    "error_message": row.get("error_message") or "",
                }
            )


def generate_markdown(stats: list[StatRecord], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sorted_stats = sort_by_query_id(stats)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_queries = len(sorted_stats)
    total_runs = sum(item["count"] for item in sorted_stats)

    lines = [
        "# TPC-H 基准测试报告",
        "",
        "## 测试环境说明",
        "",
        f"- 报告生成时间：{generated_at}",
        f"- 测试 Query 数量：{total_queries}",
        f"- 总执行次数：{total_runs}",
        "",
        "## 各 Query 性能汇总",
        "",
        _stats_table(sorted_stats),
        "",
        "## Top 5 慢查询",
        "",
        _top_slow_queries_table(sorted_stats, top_n=5),
        "",
        "## 失败分类",
        "",
        _failure_section(sorted_stats),
        "",
        "## 测试限制说明",
        "",
        "- 统计仅用成功记录计算 avg / min / max / p95；超时或报错计入失败，不进均值",
        "- 本文件会被下一次运行覆盖；需要保留的基线请另存（例如 `pg_multirun_*`）",
        "- 轮数、并发、超时以当时 YAML 为准；自动生成的环境说明不含数据库版本",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def generate_compare_markdown(
    stats1: list[StatRecord],
    stats2: list[StatRecord],
    output_path: str | Path,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    comparisons = _compare_stat_lists(stats1, stats2)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    analysis = _compare_analysis(comparisons)

    lines = [
        "# TPC-H 双库对比报告",
        "",
        "## 测试环境说明",
        "",
        f"- 报告生成时间：{generated_at}",
        f"- 对比 Query 数量：{len(comparisons)}",
        f"- 数据库 1 标签：baseline",
        f"- 数据库 2 标签：target",
        "",
        "## 对比汇总",
        "",
        analysis["summary"],
        "",
        "## 性能对比表",
        "",
        _compare_table(comparisons),
        "",
        "## 性能差异分析",
        "",
        analysis["details"],
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def _stats_table(stats: list[StatRecord]) -> str:
    headers = [
        "query_id",
        "count",
        "avg_ms",
        "min_ms",
        "max_ms",
        "p95_ms",
        "success_rate",
    ]
    rows = [
        [
            item["query_id"],
            str(item["count"]),
            _format_ms(item["avg_ms"]),
            _format_ms(item["min_ms"]),
            _format_ms(item["max_ms"]),
            _format_ms(item["p95_ms"]),
            _format_rate(item["success_rate"]),
        ]
        for item in stats
    ]
    return _markdown_table(headers, rows)


def _top_slow_queries_table(stats: list[StatRecord], top_n: int) -> str:
    candidates = [item for item in stats if item["avg_ms"] is not None]
    if not candidates:
        return "无成功执行的 Query。"

    top_items = sorted(candidates, key=lambda item: item["avg_ms"], reverse=True)[:top_n]
    headers = ["排名", "query_id", "avg_ms", "p95_ms", "success_rate"]
    rows = [
        [
            str(index),
            item["query_id"],
            _format_ms(item["avg_ms"]),
            _format_ms(item["p95_ms"]),
            _format_rate(item["success_rate"]),
        ]
        for index, item in enumerate(top_items, start=1)
    ]
    return _markdown_table(headers, rows)


def _failure_section(stats: list[StatRecord]) -> str:
    fully_failed = [item for item in stats if item["success_rate"] == 0]
    partially_failed = [item for item in stats if 0 < item["success_rate"] < 1]
    all_success = [item for item in stats if item["success_rate"] == 1]

    sections = [
        f"- 全部成功：{len(all_success)} 个 Query",
        f"- 部分失败：{len(partially_failed)} 个 Query",
        f"- 完全失败：{len(fully_failed)} 个 Query",
        "",
    ]

    if fully_failed:
        sections.extend(
            [
                "### 完全失败（success_rate = 0）",
                "",
                _markdown_table(
                    ["query_id", "count", "success_rate"],
                    [
                        [item["query_id"], str(item["count"]), _format_rate(item["success_rate"])]
                        for item in fully_failed
                    ],
                ),
                "",
            ]
        )
    else:
        sections.extend(["### 完全失败（success_rate = 0）", "", "无。", ""])

    if partially_failed:
        sections.extend(
            [
                "### 部分失败（0 < success_rate < 1）",
                "",
                _markdown_table(
                    ["query_id", "count", "success_rate"],
                    [
                        [item["query_id"], str(item["count"]), _format_rate(item["success_rate"])]
                        for item in partially_failed
                    ],
                ),
            ]
        )
    else:
        sections.extend(["### 部分失败（0 < success_rate < 1）", "", "无。"])

    return "\n".join(sections)


def _compare_stat_lists(
    stats1: list[StatRecord],
    stats2: list[StatRecord],
) -> list[StatRecord]:
    map1 = {item["query_id"]: item for item in stats1}
    map2 = {item["query_id"]: item for item in stats2}
    query_ids = sort_by_query_id(
        [{"query_id": query_id} for query_id in map1.keys() | map2.keys()]
    )

    comparisons: list[StatRecord] = []
    for item in query_ids:
        query_id = item["query_id"]
        left = map1.get(query_id)
        right = map2.get(query_id)

        avg_ms_1 = left["avg_ms"] if left else None
        avg_ms_2 = right["avg_ms"] if right else None

        if avg_ms_1 is not None and avg_ms_2 is not None:
            diff_ms = round(avg_ms_2 - avg_ms_1, 2)
            diff_percentage = (
                round((diff_ms / avg_ms_1) * 100, 2) if avg_ms_1 != 0 else None
            )
        else:
            diff_ms = None
            diff_percentage = None

        comparisons.append(
            {
                "query_id": query_id,
                "stats1": left,
                "stats2": right,
                "avg_ms_1": avg_ms_1,
                "avg_ms_2": avg_ms_2,
                "p95_ms_1": left["p95_ms"] if left else None,
                "p95_ms_2": right["p95_ms"] if right else None,
                "diff_ms": diff_ms,
                "diff_percentage": diff_percentage,
            }
        )

    return comparisons


def _compare_table(comparisons: list[StatRecord]) -> str:
    headers = [
        "query_id",
        "avg_ms (baseline)",
        "avg_ms (target)",
        "diff_ms",
        "diff_percentage",
        "p95_ms (baseline)",
        "p95_ms (target)",
    ]
    rows = [
        [
            item["query_id"],
            _format_ms(item["avg_ms_1"]),
            _format_ms(item["avg_ms_2"]),
            _format_ms(item["diff_ms"]),
            _format_percentage(item["diff_percentage"]),
            _format_ms(item["p95_ms_1"]),
            _format_ms(item["p95_ms_2"]),
        ]
        for item in comparisons
    ]
    return _markdown_table(headers, rows)


def _compare_analysis(comparisons: list[StatRecord]) -> dict[str, str]:
    comparable = [
        item for item in comparisons if item["diff_ms"] is not None
    ]
    if not comparable:
        return {
            "summary": "无可对比的有效 Query（两侧均缺少成功执行的统计数据）。",
            "details": "无。",
        }

    faster_on_target = [item for item in comparable if item["diff_ms"] < 0]
    slower_on_target = [item for item in comparable if item["diff_ms"] > 0]
    unchanged = [item for item in comparable if item["diff_ms"] == 0]

    avg_diff = round(
        sum(item["diff_ms"] for item in comparable) / len(comparable),
        2,
    )
    max_regression = max(comparable, key=lambda item: item["diff_ms"])
    max_improvement = min(comparable, key=lambda item: item["diff_ms"])

    summary_lines = [
        f"- 可对比 Query 数量：{len(comparable)}",
        f"- target 更快：{len(faster_on_target)} 个 Query",
        f"- target 更慢：{len(slower_on_target)} 个 Query",
        f"- 性能持平：{len(unchanged)} 个 Query",
        f"- 平均 diff_ms（target - baseline）：{avg_diff} ms",
    ]

    detail_lines = [
        "### 最大性能回退",
        "",
        (
            f"- Query `{max_regression['query_id']}`："
            f"baseline {_format_ms(max_regression['avg_ms_1'])} ms，"
            f"target {_format_ms(max_regression['avg_ms_2'])} ms，"
            f"回退 {_format_ms(max_regression['diff_ms'])} ms"
            f"（{_format_percentage(max_regression['diff_percentage'])}）"
        ),
        "",
        "### 最大性能提升",
        "",
        (
            f"- Query `{max_improvement['query_id']}`："
            f"baseline {_format_ms(max_improvement['avg_ms_1'])} ms，"
            f"target {_format_ms(max_improvement['avg_ms_2'])} ms，"
            f"变化 {_format_ms(max_improvement['diff_ms'])} ms"
            f"（{_format_percentage(max_improvement['diff_percentage'])}）"
        ),
        "",
        "### 重点关注（target 更慢 Top 3）",
        "",
    ]

    regressions = sorted(
        [item for item in comparable if item["diff_ms"] > 0],
        key=lambda item: item["diff_ms"],
        reverse=True,
    )[:3]
    if regressions:
        for item in regressions:
            detail_lines.append(
                f"- Query `{item['query_id']}`：慢 {_format_ms(item['diff_ms'])} ms"
                f"（{_format_percentage(item['diff_percentage'])}）"
            )
    else:
        detail_lines.append("- 无。")

    return {
        "summary": "\n".join(summary_lines),
        "details": "\n".join(detail_lines),
    }


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, separator_line, *body_lines])


def _format_ms(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _format_rate(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_percentage(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}%"
