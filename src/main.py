from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _SRC_DIR.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config_loader import Config, DatabaseConfig, load_config
from executor import SQLExecutor
from reporter import generate_compare_markdown, generate_csv, generate_markdown
from stats import compute_stats

logger = logging.getLogger("tpch-benchmark")

OUTPUT_DIR = _ROOT_DIR / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TPC-H 数据库基准测试工具")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="配置文件路径（默认: config.yaml）",
    )
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )


def log_database(label: str, db: DatabaseConfig) -> None:
    logger.info(
        "%s: %s@%s:%s/%s",
        label,
        db.user,
        db.host,
        db.port,
        db.database,
    )


def create_executor(db: DatabaseConfig, label: str) -> SQLExecutor:
    logger.info("创建 SQLExecutor（%s）...", label)
    executor = SQLExecutor(
        host=db.host,
        port=db.port,
        user=db.user,
        password=db.password,
        database=db.database,
        session_params=db.session_params,
    )
    log_database(label, db)
    return executor


def run_benchmark(executor: SQLExecutor, config: Config, label: str) -> list[dict]:
    test = config.test
    logger.info(
        "开始执行测试（%s）: sql_dir=%s, rounds=%d, concurrency=%d, warmup=%s, timeout=%ds",
        label,
        test.sql_dir,
        test.rounds,
        test.concurrency,
        test.warmup,
        test.timeout,
    )

    all_results: list[dict] = []
    for round_index in range(1, test.rounds + 1):
        logger.info("[%s] 第 %d/%d 轮执行中...", label, round_index, test.rounds)
        round_results = executor.execute_sql_files(
            sql_dir=test.sql_dir,
            concurrency=test.concurrency,
            timeout=test.timeout,
            warmup=test.warmup if round_index == 1 else False,
        )
        success_count = sum(1 for row in round_results if row["success"])
        logger.info(
            "[%s] 第 %d/%d 轮完成: %d 条 SQL, 成功 %d, 失败 %d",
            label,
            round_index,
            test.rounds,
            len(round_results),
            success_count,
            len(round_results) - success_count,
        )
        all_results.extend(round_results)

    logger.info("[%s] 测试执行完成，共 %d 条记录", label, len(all_results))
    return all_results


def main() -> None:
    setup_logging()
    args = parse_args()

    try:
        logger.info("步骤 1/6: 加载配置文件 %s", args.config)
        config = load_config(args.config)
        log_database("主数据库", config.database)
        logger.info(
            "测试参数: sql_dir=%s, rounds=%d, concurrency=%d, warmup=%s, timeout=%ds",
            config.test.sql_dir,
            config.test.rounds,
            config.test.concurrency,
            config.test.warmup,
            config.test.timeout,
        )
        logger.info("双库对比: %s", "启用" if config.compare.enabled else "未启用")

        logger.info("步骤 2/6: 创建主库 SQLExecutor")
        executor = create_executor(config.database, "baseline")

        logger.info("步骤 3/6: 执行主库基准测试")
        results = run_benchmark(executor, config, "baseline")

        logger.info("步骤 4/6: 计算统计数据")
        stats = compute_stats(results)
        logger.info("统计完成: %d 个 Query", len(stats))

        logger.info("步骤 5/6: 生成 CSV 和 Markdown 报告")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = OUTPUT_DIR / "results.csv"
        markdown_path = OUTPUT_DIR / "report.md"
        generate_csv(results, csv_path)
        logger.info("CSV 报告已生成: %s", csv_path)
        generate_markdown(stats, markdown_path)
        logger.info("Markdown 报告已生成: %s", markdown_path)

        if config.compare.enabled:
            logger.info("步骤 6/6: 执行目标库测试并生成对比报告")
            target_executor = create_executor(config.compare.target, "target")
            target_results = run_benchmark(target_executor, config, "target")

            target_stats = compute_stats(target_results)
            target_csv_path = OUTPUT_DIR / "target_results.csv"
            compare_path = OUTPUT_DIR / "compare_report.md"

            generate_csv(target_results, target_csv_path)
            logger.info("目标库 CSV 报告已生成: %s", target_csv_path)
            generate_compare_markdown(stats, target_stats, compare_path)
            logger.info("对比报告已生成: %s", compare_path)
        else:
            logger.info("步骤 6/6: 跳过双库对比（compare.enabled=false）")

        logger.info("全部步骤完成，报告输出目录: %s", OUTPUT_DIR.resolve())

    except Exception as exc:
        logger.error("执行失败: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
