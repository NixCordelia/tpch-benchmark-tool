# 辅助脚本

| 脚本 | 作用 |
| ---- | ---- |
| `copy_tpch_to_ymatrix.py` | 按 YAML 里的 `database` / `compare.target`，从 PostgreSQL COPY 8 张表到 MatrixDB |

先复制 `config.compare.example.yaml` 为 `config.compare.yaml` 并填写密码（该文件已加入 `.gitignore`）。在**项目根目录**：

```powershell
python scripts\copy_tpch_to_ymatrix.py --config config.compare.yaml
```

前提：源库已导入 SF=1；目标库可连。脚本会核对两边行数，并创建 `idx_lineitem_combo`。

然后再跑对比：

```powershell
python main.py --config config.compare.yaml
```
