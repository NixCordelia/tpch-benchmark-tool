# 运行结果目录（题目建议的 results/）

根目录的 `report.md` 是作业书面报告，**不是**本目录里的 `report.md`。

| 文件 | 是哪一次实验 |
| ---- | ---- |
| `pg_multirun_results.csv` | PostgreSQL 多轮自动化 + Q17/Q20/Q21 补测明细（60 行） |
| `pg_multirun_report.md` | 上述实验的汇总（含 Top 5、失败分类、补测说明） |
| `results.csv` | **最近一次** `python main.py` 写出的 baseline 明细（当前为对比实验的 PostgreSQL 1 轮） |
| `report.md` | 最近一次 baseline 的 Markdown 汇总 |
| `target_results.csv` | 对比实验：MatrixDB 4.8.12 明细（22 成功） |
| `compare_report.md` | PostgreSQL vs MatrixDB 对比报告 |

再次运行 `python main.py` 会覆盖 `results.csv` 和 `report.md`，不会覆盖 `pg_multirun_*`。对比前请自行备份，或改用带日期的拷贝。
