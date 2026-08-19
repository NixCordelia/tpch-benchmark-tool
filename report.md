# TPC-H 基准测试执行与结果汇总工具 - 测试报告

## 1. 方案设计

### 1.1 要解决的问题

FDE 在客户现场经常需要做性能 PoC 和竞品对比：同一套 SQL、两套库、多轮执行，最后给出可复核的耗时和失败原因。手工复制粘贴 psql 输出容易出错，也难以做 p95 和成功率。本工具把「配置 → 执行 → 统计 → 报告」收成最小闭环。

### 1.2 整体架构

```
config.yaml
    → config_loader.load_config()
    → SQLExecutor.execute_sql_files()   # 每线程独立连接
    → stats.compute_stats()             # avg / min / max / p95 / success_rate
    → reporter.generate_csv / generate_markdown
    → 若 compare.enabled：对 target 再跑一遍，generate_compare_markdown()
```

模块划分：

| 模块 | 职责 |
| ---- | ---- |
| `src/config_loader.py` | 读取 YAML，缺字段回退到与 `config.example.yaml` 一致的默认值 |
| `src/executor.py` | 发现 `*.sql`、按文件名数字序执行、超时、warmup、并发 |
| `src/stats.py` | 按 `query_id` 分组统计；`compare_stats` 按 query 对齐两套结果 |
| `src/reporter.py` | CSV 明细、Markdown 汇总、双库对比报告 |
| `src/main.py` | 命令行入口、多轮循环、日志、非零退出码（根目录 `main.py` 为启动器） |

### 1.3 数据流

配置文件 → 加载配置 → 连接数据库 → 读取 SQL 目录 →（可选 warmup）→ 按轮次并发执行 → 记录每条结果 → 统计 → 写出 `results/`。

## 2. 实现说明

- **语言**：Python 3.9+
- **驱动**：`psycopg2-binary`。未选异步驱动，因为瓶颈在数据库而不是 Python 事件循环。
- **配置**：YAML。`session_params` 在连接后执行 `SET`，对应题目中的「不同数据库参数设置」。
- **并发**：`ThreadPoolExecutor`。每个任务单独 `connect` / `close`，避免多线程共享一个连接。
- **超时**：`SET statement_timeout`。`timeout=0` 表示不限制；超时记为 `error_message=TIMEOUT`，不中断其余 SQL。
- **统计**：仅用成功记录算 avg/min/max/p95；无成功记录时 `success_rate=0`，耗时字段为 `-`。
- **TPC-C**：未实现。后续可把外部 TPC-C 工具的吞吐量结果接到同一套 reporter。

本次作业实测：PostgreSQL 15（多轮 + 补测）以及 MatrixDB 4.8.12 Docker demo（单轮对比）。对比细节见 `results/compare_report.md`。**不能**据此声称「YMatrix 全面更快」或「已验证 5.2.1 社区版」。

## 3. 测试过程

### 3.1 测试环境

- 操作系统：Windows 10
- 数据库：PostgreSQL 15（Docker 容器 `tpch-postgres`）
- 数据规模：TPC-H SF=1（约 1GB）
- SQL：`sql/1.sql` … `sql/22.sql`
- `lineitem` 上已有索引 `idx_lineitem_combo (l_partkey, l_suppkey, l_shipdate)`

### 3.2 分阶段执行

| 阶段 | 配置 | 目的 |
| ---- | ---- | ---- |
| 自动化 | `rounds=3`，`concurrency=2`，`timeout=300`，`warmup=false` | 覆盖 22 条查询，暴露超时 |
| 补测 | `timeout=0`，Q17 / Q20 / Q21 在 psql 单独执行 | 拿到真实耗时，而不是只写 TIMEOUT |
| 双库对比 | `config.compare.yaml`：`rounds=1`，`concurrency=1`，`timeout=300` | 同一套 SQL 对 PostgreSQL 与 MatrixDB 4.8.12 demo |

Q20 第一次不限时补测因停电中断（约 20 小时未结束）。之后在确认 `idx_lineitem_combo` 存在的条件下重跑，`\timing` 得到 129549.190 ms。

对比前用 `python scripts/copy_tpch_to_ymatrix.py` 把 SF=1 从 PostgreSQL COPY 到 YMatrix。再次运行会覆盖 `results/results.csv` 与 `results/report.md`，多轮基线在 `results/pg_multirun_*`。

### 3.3 验证方法

- 对照 `results/pg_multirun_results.csv` 与 `results/pg_multirun_report.md`：19 条 Query 各 3 条成功明细，统计值由成功 `elapsed_ms` 计算。
- Q17 / Q20 / Q21 的耗时来自不限时补测，已写入汇总表。
- 对照 `results/compare_report.md` 与 `results/target_results.csv`：可对比 21 条，11 快 10 慢；Q21 仅 target 成功。
- 配置文件缺失时 `python main.py --config missing.yaml` 以退出码 1 结束，并打印 `配置文件不存在`。
- 运行截图见 [screenshots/](screenshots/)（终端日志拍于重构前，路径仍显示 `output/`）。

## 4. 测试结果

数据来源：多轮基线 [results/pg_multirun_report.md](results/pg_multirun_report.md)；对比当轮 [results/compare_report.md](results/compare_report.md)、[results/target_results.csv](results/target_results.csv)。`results/report.md` / `results/results.csv` 为对比运行覆盖后的 PostgreSQL **1 轮**结果。

### 4.1 总体统计

- 测试 Query 数量：22
- 计入报告的执行次数：60
- 全部成功：22 个 Query
- 完全失败：0 个 Query
- 部分失败：0 个 Query

### 4.2 各 Query 性能汇总

| query_id | count | avg_ms      | min_ms      | max_ms      | p95_ms      | success_rate |
| -------- | ----- | ----------- | ----------- | ----------- | ----------- | ------------ |
| 1        | 3     | 2595.90     | 2474.24     | 2763.29     | 2741.98     | 100.00%      |
| 2        | 3     | 117451.29   | 115099.48   | 119836.23   | 119594.42   | 100.00%      |
| 3        | 3     | 714.67      | 680.49      | 773.95      | 765.51      | 100.00%      |
| 4        | 3     | 1020.29     | 962.14      | 1100.07     | 1089.93     | 100.00%      |
| 5        | 3     | 563.92      | 378.50      | 680.41      | 675.65      | 100.00%      |
| 6        | 3     | 371.60      | 243.36      | 438.14      | 437.65      | 100.00%      |
| 7        | 3     | 572.36      | 353.97      | 690.32      | 688.57      | 100.00%      |
| 8        | 3     | 583.63      | 324.72      | 738.31      | 733.26      | 100.00%      |
| 9        | 3     | 1244.50     | 693.66      | 1520.25     | 1520.18     | 100.00%      |
| 10       | 3     | 736.97      | 431.52      | 900.93      | 898.68      | 100.00%      |
| 11       | 3     | 160.52      | 84.60       | 198.63      | 198.60      | 100.00%      |
| 12       | 3     | 601.77      | 362.46      | 726.98      | 725.87      | 100.00%      |
| 13       | 3     | 612.92      | 371.43      | 755.03      | 750.76      | 100.00%      |
| 14       | 3     | 394.91      | 263.85      | 468.62      | 466.98      | 100.00%      |
| 15       | 3     | 430.55      | 274.65      | 525.00      | 521.70      | 100.00%      |
| 16       | 3     | 341.23      | 199.20      | 415.81      | 415.10      | 100.00%      |
| 17       | 1     | 2887899.71  | 2887899.71  | 2887899.71  | 2887899.71  | 100.00%      |
| 18       | 3     | 6258.40     | 6118.32     | 6409.50     | 6393.29     | 100.00%      |
| 19       | 3     | 623.86      | 609.45      | 640.88      | 638.92      | 100.00%      |
| 20       | 1     | 129549.19   | 129549.19   | 129549.19   | 129549.19   | 100.00%      |
| 21       | 1     | 2594048.56  | 2594048.56  | 2594048.56  | 2594048.56  | 100.00%      |
| 22       | 3     | 351.08      | 337.58      | 363.24      | 362.16      | 100.00%      |

### 4.3 Top 5 慢查询

| 排名 | query_id | avg_ms      | p95_ms      | success_rate |
| ---- | -------- | ----------- | ----------- | ------------ |
| 1    | 17       | 2887899.71  | 2887899.71  | 100.00%      |
| 2    | 21       | 2594048.56  | 2594048.56  | 100.00%      |
| 3    | 20       | 129549.19   | 129549.19   | 100.00%      |
| 4    | 2        | 117451.29   | 119594.42   | 100.00%      |
| 5    | 18       | 6258.40     | 6393.29     | 100.00%      |

### 4.4 失败分类

| 类别 | 数量 | Query |
| ---- | ---- | ----- |
| 全部成功 | 22 | Q1–Q22 |
| 部分失败 | 0 | 无 |
| 完全失败 | 0 | 无 |

自动化阶段（`timeout=300s`）Q17 / Q20 / Q21 均为 TIMEOUT。补测耗时：Q17 = 2887899.71 ms（≈ 48.1 min），Q21 = 2594048.56 ms（≈ 43.2 min），Q20 = 129549.19 ms（≈ 2.16 min，在 `idx_lineitem_combo` 下）。

### 4.5 双库对比（2026-08-19，独立实验）

配置：`rounds=1`，`concurrency=1`，`timeout=300s`。baseline = PostgreSQL 15，target = MatrixDB 4.8.12-community（端口 5433）。

| 库 | 成功 | 失败 |
| -- | ---- | ---- |
| PostgreSQL（本轮） | 21 | Q21 TIMEOUT（301163.63 ms） |
| MatrixDB（本轮） | 22 | 无 |

可对比 21 条：target 更快 11 条，更慢 10 条。平均 `diff_ms` = -7651.88，主要由 Q2（-121832.78 ms，-96.80%）拉动。

| 观察 | Query | 说明 |
| ---- | ----- | ---- |
| target 提升最大 | Q2 | 125865.28 → 4032.50 ms |
| target 提升较大 | Q20 | 47681.57 → 6402.52 ms（-86.57%） |
| target 回退最大 | Q12 | 1558.61 → 6374.13 ms（+308.96%） |
| 无法算加速比 | Q21 | PG 超时；YMatrix 6414.01 ms 完成 |

完整表见 [results/compare_report.md](results/compare_report.md)。

本轮 PostgreSQL Q17 = 2569.46 ms，与补测 2887899.71 ms **不是同一次实验**，禁止合并宣传。

### 4.6 运行截图

![自动化跑完](screenshots/run-success.png)

![多轮基线 Top 5](screenshots/report-top5.png)

![容器退出后恢复](screenshots/docker-restart.png)

![双库对比跑完](screenshots/compare-run.png)

## 5. 问题和风险

### 5.1 已证实的问题

- 单机 PostgreSQL 上 Q17 / Q21 补测仍需 40 分钟以上；Q20 在已有 `idx_lineitem_combo` 下为 129549.19 ms。
- `timeout=300` 只能证明「超时了」，不能回答「到底多慢」。PoC 若要给客户调优基线，必须允许超长查询跑完或单独补测。
- Docker 容器重启后未 `docker start` 会让 22 条全部连接失败。工具会把错误写进 `error_message`，但不会自动拉起数据库。
- 没有断点续跑：Q20 第一次补测因停电中断，只能事后重跑。

### 5.2 不能从本次结果推出的结论

- 不能推出 YMatrix 全面更快：对比轮次里 11 条更快、10 条更慢；均值被 Q2 主导。
- 不能把对比轮的 PostgreSQL Q17（2569 ms）和补测 Q17（48 min）当成同一基线。
- 不能把「约 20 小时未跑完」和「129549.19 ms」写成同一条件下的索引加速比。
- 不能把本次 target 写成 MatrixDB 5.2.1：实际是 4.8.12 Docker demo。
- Q17 / Q20 / Q21 的 p95 在单次样本下没有分布意义。

### 5.3 现场使用风险

- 长查询占满 I/O / CPU，可能影响客户同实例上的其他业务。
- 并发 > 1 时大查询互相抢资源，单条耗时会被污染。
- 没有断点续跑：停电或 SSH 断开后，已跑完的结果若未落盘就会丢失。

## 6. 后续改进方向

1. **对比加深**：对 Q6 / Q12 / Q15 / Q21 做两边 EXPLAIN；必要时 `timeout=0` 重跑 Q21 的 PostgreSQL 成功耗时（可能 >5 分钟）。
2. **Q20 无索引对照**：若要证明索引贡献，需 `DROP INDEX idx_lineitem_combo` 后再跑完一次，用两次成功耗时对比。
3. **断点续跑**：按 `query_id + round` 跳过 CSV 里已成功的记录；对比运行不要覆盖多轮基线（本次已另存 `results/pg_multirun_*`）。
4. **TPC-C 扩展**：包装外部工具，把 tpmC / 延迟写入同一套报告模板。
5. **结果归档**：把每次 run 的配置快照和 CSV 一并保存，便于客户现场做趋势对比。
