# AI 使用说明

## 1. 使用了哪些 AI 工具

- **Cursor**（主要）：按模块生成代码、根据运行错误修改、补文档
- 未使用独立的 ChatGPT / Claude 网页作为主开发环境
- 使用deepseek网页端做前期方案分析

## 2. 关键 Prompt 示例

开发时按模块拆开提需求，而不是一次「生成整个项目」：

1. 配置加载：要求 dataclass 覆盖 `database` / `test` / `compare`，缺字段用 `config.example.yaml` 默认值，路径不存在抛 `FileNotFoundError`。
2. 执行引擎：要求每线程独立连接、`ThreadPoolExecutor`、超时记为 `TIMEOUT`、失败不中断整批、返回固定字段。
3. 统计与报告：要求 `numpy.percentile` 算 p95、无成功记录时成功率为 0、CSV + Markdown + 对比报告。
4. 主入口：要求 `--config`、逐步日志、`compare.enabled` 时跑第二套库、失败非零退出。

这些 Prompt 的共同点是：**约束输入输出和失败行为**，而不是只说：写一个压测工具。

## 3. AI 帮助完成了哪些部分

- 五个 Python 模块的初稿：现位于 `src/`（`config_loader`、`executor`、`stats`、`reporter`、`main`）；根目录 `main.py` 只是启动器
- 最小依赖的 `requirements.txt` 选型说明
- Markdown 报告模板（环境说明、汇总表、Top 5、失败分类）

我负责的部分：

- 在真实 PostgreSQL + TPC-H SF=1 上跑 22 条查询
- 处理 Q17 / Q20 / Q21 超时；Q20 第一次补测因停电中断，后来在 `idx_lineitem_combo` 下重跑得到 129549.19 ms
- 核对 CSV 与汇总表数字，删掉文档里编造或互相矛盾的表述
- 决定哪些结论不能写（例如未做公平对比时不能写「MPP 一定更快」；对比 11 快 10 慢时不能写「全面领先」）
- 在 Docker 中拉起 MatrixDB 4.8.12 并完成一轮 `config.compare.yaml` 对比

## 4. AI 生成内容中出现过哪些问题

1. **文档与代码不一致**：早期 `report.md` 写「超时使用 `func_timeout` / `signal.alarm`」，实际代码用的是 PostgreSQL `statement_timeout`。已按代码改文档。
2. **依赖遗漏**：统计模块用了 `numpy.percentile`，最初 `requirements.txt` 没有 numpy，本机 import 会失败。已补上。
3. **Windows 命令**：生成的一键验证用了 `cd dir && python`，当前 PowerShell 不支持 `&&`，需要改成 `;`。
4. **把「设计意图」写成「已经发生的 bug」**：例如有一份草稿写「多线程同时写同一个 CSV」。当前实现是全部执行完后由 `reporter` 一次写文件，并不存在这个竞态。不能把 AI 想象中的 bug 写进作业。
5. **回归结论写过头**：草稿里曾出现「修正后 22 条全部成功」，当时 Q20 其实还没跑完。现在 Q20 已补测成功（129549.19 ms），22 条都有成功耗时；自动化阶段这三条仍是 TIMEOUT，不能写成「工具一轮就 22/22」。

## 5. 如何验证和修正

- 每加一个模块后用真实配置跑 `python main.py --config config.yaml`，看日志里的成功/失败计数
- 用 `results/pg_multirun_results.csv` 反算 avg，核对 `results/pg_multirun_report.md` 表格
- 对照 `results/compare_report.md` 与 `results/target_results.csv` 核对双库结果
- 对 TIMEOUT 条目在 psql 里单独执行，确认是查询本身慢，而不是工具计时错误
- 故意传入不存在的配置文件，确认退出码为 1
- 对照题目清单检查：配置项、结果字段、多轮统计、对比开关、CSV/Markdown、失败分类、限制说明

## 6. 如果不使用 AI，预计需要多久完成

- 纯手写代码 + 联调 + 跑 SF=1：大约 3～4 天（不含 Q17/Q20/Q21 那种小时级等待）
- 实际：模块骨架约 1 天，真实跑数和补测、改文档又用了数天（长查询和停电占了大部分墙钟时间）
- AI 主要缩短的是「从零搭文件结构和样板代码」，没有缩短数据库跑数时间，也不能替代对结果的核对

