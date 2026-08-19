# TPC-H Benchmark Tool

## 项目目标

面向 FDE / 现场 PoC 场景的轻量级基准测试执行与结果汇总工具：读取 YAML 配置，批量执行 TPC-H 22 条查询，记录每条 SQL 的耗时与成败，计算 avg / min / max / p95 / 成功率，并输出 CSV 明细和 Markdown 汇总。也可对两套数据库做同 SQL 对比（例如 PostgreSQL vs YMatrix）。

本仓库已在 **PostgreSQL 15 + TPC-H SF=1** 上跑通主库测试，并用 Docker 中的 **MatrixDB 4.8.12-community** 做过一轮同 SQL 对比（`config.compare.yaml`）。对比结论见 [results/compare_report.md](results/compare_report.md)：不是全面更快，Q21 在 300s 超时下仅 YMatrix 跑完。

## 目录结构

```
tpch-benchmark-tool/
├── README.md                 # 本文件（题目第三节）
├── report.md                 # 作业书面报告（方案 / 过程 / 结果 / 风险）
├── ai_usage.md               # AI 使用说明
├── design_decision.md        # 核心目标、关键判断、验证场景
├── config.example.yaml       # 配置示例（密码为占位符）
├── config.compare.example.yaml
├── .env.example              # Docker 环境变量示例
├── requirements.txt
├── docker-compose.yml        # 仅 PostgreSQL 15；密码读 .env
├── main.py                   # 启动器（实现在 src/）
├── src/                      # 核心代码
├── scripts/                  # 辅助脚本（拷贝 TPC-H 到 YMatrix）
├── sql/                      # TPC-H Q1–Q22
├── data/                     # 建表 DDL 与数据生成说明
├── results/                  # 运行结果（CSV / Markdown）
└── screenshots/              # 运行截图（run-success / report-top5 / docker-restart / compare-run）
```

对应题目第三节建议的 `src/`（兼 `scripts/`）、`sql/`、`data/`、`results/`。根目录保留 `README.md`、`report.md`、`ai_usage.md`、`config.example.yaml`。`design_decision.md` 为额外要求。必须在项目根执行 `python main.py`。

## 环境依赖

- Python 3.9+
- PostgreSQL 15+（本次实测为 Docker 容器；YMatrix 走 PostgreSQL 协议）
- Docker Desktop（可选）
- TPC-H SF=1 数据集（见 [data/README.md](data/README.md)）

Python 包见 `requirements.txt`：`psycopg2-binary`、`PyYAML`、`numpy`。

## 安装步骤

```bash
git clone <your-repo>
cd tpch-benchmark-tool
pip install -r requirements.txt
copy .env.example .env
copy config.example.yaml config.yaml
```

编辑 `.env` 与 `config.yaml` 中的密码（二者需一致）。`config.yaml` / `config.compare.yaml` / `.env` 已加入 `.gitignore`，不要推进公开仓库。

启动示例数据库：

```bash
docker compose up -d
```

建表与导数据见 [data/README.md](data/README.md)。双库对比再复制：

```bash
copy config.compare.example.yaml config.compare.yaml
```

## 配置说明

| 配置项 | 含义 | 本次实测值 |
| ------ | ---- | ---------- |
| `database.*` | 主库连接信息 | `localhost:5432` / 用户 `tpch`（密码只写在本地 yaml） |
| `database.session_params` | 连接后 `SET` 的会话参数 | 示例：`work_mem=256MB`，`jit=off` |
| `test.sql_dir` | SQL 文件目录 | `./sql`（TPC-H Q1–Q22） |
| `test.rounds` | 测试轮数 | 自动化 3 轮；Q17/Q20/Q21 补测各 1 次 |
| `test.concurrency` | 并发线程数 | 自动化阶段为 2；对比实验为 1 |
| `test.warmup` | 是否先跑一轮不计时 | `false` |
| `test.timeout` | 单条 SQL 超时（秒），`0` 表示不限制 | 自动化 / 对比 `300`；补测 `0` |
| `compare.enabled` | 是否对第二套库再跑一遍 | 对比实验见本地 `config.compare.yaml` |
| `compare.target` | 对比库连接信息 | 本次为 MatrixDB demo：`localhost:5433` |

三份 YAML 不要混用：日常主库用 `config.yaml`；对照示例看 `config.example.yaml`；双库对比必须用 `config.compare.yaml`。`--config` 默认值为 `config.yaml`。

## 运行方式

1. 确认 PostgreSQL 可连接，且 8 张 TPC-H 表已导入（见 [data/README.md](data/README.md)）。
2. 按需修改配置（轮数、并发、超时、是否对比）。
3. 在项目根目录执行：

```bash
python main.py --config config.yaml
```

4. 查看 [results/README.md](results/README.md) 了解各结果文件含义。
5. 双库对比：先 `python scripts/copy_tpch_to_ymatrix.py`，再：

```bash
python main.py --config config.compare.yaml
```

会覆盖 `results/results.csv` 与 `results/report.md`，多轮基线在 `results/pg_multirun_*`。

## 示例输出

多轮 PostgreSQL 基线（`timeout=300s`，`concurrency=2`，加上 Q17 / Q20 / Q21 不限时补测）。完整表格见 [results/pg_multirun_report.md](results/pg_multirun_report.md)。

**测试环境**

- 数据库：PostgreSQL 15（Docker 容器 `tpch-postgres`）
- 数据规模：TPC-H SF=1
- Query 数量：22
- 计入报告的执行次数：60

**各 Query 性能汇总**

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

**Top 5 慢查询**（仅统计有成功耗时的 Query）

| 排名 | query_id | avg_ms      | p95_ms      | success_rate |
| ---- | -------- | ----------- | ----------- | ------------ |
| 1    | 17       | 2887899.71  | 2887899.71  | 100.00%      |
| 2    | 21       | 2594048.56  | 2594048.56  | 100.00%      |
| 3    | 20       | 129549.19   | 129549.19   | 100.00%      |
| 4    | 2        | 117451.29   | 119594.42   | 100.00%      |
| 5    | 18       | 6258.40     | 6393.29     | 100.00%      |

双库对比表见 [results/compare_report.md](results/compare_report.md)。作业书面报告见 [report.md](report.md)，判断与验证见 [design_decision.md](design_decision.md)。

## 运行截图

题目第六节要求的运行结果截图在 [screenshots/](screenshots/)。终端图拍于目录重构前，日志里的 `output/` 即现在的 `results/`。

![运行成功](screenshots/run-success.png)

![Top 5 慢查询](screenshots/report-top5.png)

![容器恢复](screenshots/docker-restart.png)

![双库对比](screenshots/compare-run.png)

## 已知限制

- 最小闭环可运行，不是生产级压测平台；没有结果库、没有 Web UI、没有断点续跑。
- 对比是 PostgreSQL 15 vs MatrixDB 4.8.12 Docker demo（非 5.2.1），单轮 timeout=300s。21 条可对比中 target 11 快 10 慢；Q21 仅 YMatrix 成功。不能写成「YMatrix 全面领先」。
- 再次运行会覆盖 `results/results.csv` 与 `results/report.md`。多轮 PostgreSQL 基线在 `results/pg_multirun_report.md`。
- Docker / 外部依赖：PostgreSQL 用本仓库 `docker-compose.yml`（容器 `tpch-postgres`，密码在本地 `.env`）；YMatrix 用已初始化的 `mxdemo`，端口 5433。SF=1 原始 `.tbl` 不进仓库，生成方式见 [data/README.md](data/README.md)。
- 公开仓库不含数据库密码。本地使用 `config.yaml`、`config.compare.yaml`、`.env`（均已 gitignore）。
- Q17 / Q20 / Q21 在自动化阶段（`timeout=300s`）超时；补测后均有成功耗时。Q20 = 129549.19 ms，是在已有索引 `idx_lineitem_combo` 下测得的单次结果。
- Q17 / Q20 / Q21 补测以及对比实验都是单次样本，p95 等于该次耗时，不能代表稳定分布。
- TPC-C 未实现。若要支持，需要包装 `tpcc-mysql` / `BenchmarkSQL` 一类工具，再把吞吐量指标接入现有 reporter。
- `timeout=0` 会把 PostgreSQL `statement_timeout` 设为 0（不限制）。长查询可能跑数小时，现场使用前应显式设置超时。
