本目录已放入提交用截图。在 Markdown 预览中应直接显示图片，不要把 `![](...)` 包进代码块。

| 文件 | 内容 | 注意 |
| ---- | ---- | ---- |
| `run-success.png` | `python main.py --config config.yaml` 自动化 3 轮跑完 | 拍于重构前，日志目录是 `output/`；当时 `warmup=True`，每轮 19 成功 / 3 TIMEOUT |
| `report-top5.png` | `pg_multirun_report.md` 的 Top 5：Q17 → Q21 → Q20 → Q2 → Q18 | 补测后的汇总，不要和对比当轮的 Top 5 搞混 |
| `docker-restart.png` | `tpch-postgres`：Exited → start → Up，`\dt` 仍有 8 张表 | 数据在 volume `tpch-data`，`docker stop` 不会删库 |
| `compare-run.png` | `python main.py --config config.compare.yaml` | 拍于重构前；baseline 21/1，target 22/0 |

终端日志里的 `output/` 等于现在的 `results/`。不要为了对齐路径再整包重跑（会覆盖结果）。
